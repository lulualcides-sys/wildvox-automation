import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from .main import Base, Channel, User, current_user, db_session, engine, plan_limits

router = APIRouter(prefix="/api/production", tags=["production"])
BASE_DIR = Path(__file__).resolve().parent.parent
PRESETS_PATH = BASE_DIR / "engine" / "presets.json"


class ProductionJob(Base):
    __tablename__ = "production_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    channel_id: Mapped[str] = mapped_column(ForeignKey("channels.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(32), default="queued", index=True)
    engine: Mapped[str] = mapped_column(String(64), default="wildvox-v2")
    topic: Mapped[str] = mapped_column(String(180))
    config_json: Mapped[str] = mapped_column(Text)
    output_url: Mapped[str | None] = mapped_column(String(1200), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


Base.metadata.create_all(bind=engine)


class QueuePreviewInput(BaseModel):
    channel_id: str
    topic: str | None = Field(default=None, max_length=180)


def load_presets() -> dict:
    if not PRESETS_PATH.exists():
        return {}
    return json.loads(PRESETS_PATH.read_text(encoding="utf-8"))


def month_start() -> datetime:
    now = datetime.now(timezone.utc)
    return datetime(now.year, now.month, 1, tzinfo=timezone.utc)


def serialize(job: ProductionJob) -> dict:
    return {
        "id": job.id,
        "channel_id": job.channel_id,
        "status": job.status,
        "engine": job.engine,
        "topic": job.topic,
        "output_url": job.output_url,
        "error_message": job.error_message,
        "attempts": job.attempts,
        "created_at": job.created_at.isoformat(),
        "updated_at": job.updated_at.isoformat(),
    }


@router.get("/status")
def production_status(user: User = Depends(current_user), db: Session = Depends(db_session)):
    rows = db.scalars(
        select(ProductionJob)
        .where(ProductionJob.user_id == user.id)
        .order_by(ProductionJob.created_at.desc())
        .limit(20)
    ).all()
    return {
        "engine": "wildvox-v2",
        "queue": {
            "queued": sum(1 for r in rows if r.status == "queued"),
            "rendering": sum(1 for r in rows if r.status == "rendering"),
            "completed": sum(1 for r in rows if r.status == "completed"),
            "failed": sum(1 for r in rows if r.status == "failed"),
        },
        "worker_required": True,
        "worker_note": "A dedicated render worker is required for production rendering.",
    }


@router.get("/jobs")
def list_jobs(user: User = Depends(current_user), db: Session = Depends(db_session)):
    rows = db.scalars(
        select(ProductionJob)
        .where(ProductionJob.user_id == user.id)
        .order_by(ProductionJob.created_at.desc())
        .limit(50)
    ).all()
    return {"jobs": [serialize(r) for r in rows]}


@router.post("/preview")
def queue_preview(
    payload: QueuePreviewInput,
    user: User = Depends(current_user),
    db: Session = Depends(db_session),
):
    channel = db.get(Channel, payload.channel_id)
    if not channel or channel.user_id != user.id:
        raise HTTPException(status_code=404, detail="Channel not found")

    limits = plan_limits(user.plan)
    used = db.scalar(
        select(func.count(ProductionJob.id)).where(
            ProductionJob.user_id == user.id,
            ProductionJob.created_at >= month_start(),
            ProductionJob.status.in_(["queued", "rendering", "completed"]),
        )
    ) or 0
    if used >= limits["videos_per_month"]:
        raise HTTPException(status_code=403, detail="Monthly video allowance reached")

    presets = load_presets()
    if not presets:
        raise HTTPException(status_code=503, detail="Preview content presets are unavailable")

    # The first real engine connection is intentionally narrow: animal/nature
    # channels can render from verified WildVox-style source packages. Other
    # niches will use the same queue once the content research agent is enabled.
    niche = channel.niche.lower()
    if "animal" not in niche and "nature" not in niche:
        raise HTTPException(
            status_code=409,
            detail="The real preview renderer is currently enabled for Animals & Nature channels first",
        )

    keys = sorted(presets.keys())
    previous = db.scalars(
        select(ProductionJob.topic).where(ProductionJob.channel_id == channel.id)
    ).all()
    preset_key = next((k for k in keys if presets[k]["title"] not in previous), keys[used % len(keys)])
    cfg = presets[preset_key]
    topic = payload.topic.strip() if payload.topic else cfg["title"]

    job = ProductionJob(
        id=str(uuid.uuid4()),
        user_id=user.id,
        channel_id=channel.id,
        status="queued",
        engine="wildvox-v2",
        topic=topic,
        config_json=json.dumps(cfg, ensure_ascii=False),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(job)
    db.commit()
    return {"job": serialize(job)}


@router.post("/jobs/{job_id}/retry")
def retry_job(job_id: str, user: User = Depends(current_user), db: Session = Depends(db_session)):
    job = db.get(ProductionJob, job_id)
    if not job or job.user_id != user.id:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status not in {"failed", "needs_attention"}:
        raise HTTPException(status_code=409, detail="Only failed jobs can be retried")
    job.status = "queued"
    job.error_message = None
    job.updated_at = datetime.now(timezone.utc)
    db.commit()
    return {"job": serialize(job)}

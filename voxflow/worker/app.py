import os
from datetime import datetime, timezone

from fastapi import BackgroundTasks, FastAPI, Header, HTTPException
from sqlalchemy import select

from voxflow.api.main import SessionLocal
from voxflow.api.production_router import ProductionJob
from voxflow.worker.worker import finish, render, storage_ready

app = FastAPI(title="VoxFlow Render Worker", version="1.0.0")
WORKER_SHARED_SECRET = os.getenv("WORKER_SHARED_SECRET", "")


def authorize(value: str | None):
    if not WORKER_SHARED_SECRET or value != WORKER_SHARED_SECRET:
        raise HTTPException(status_code=401, detail="Unauthorized")


def process_job(job_id: str):
    db = SessionLocal()
    try:
        job = db.get(ProductionJob, job_id)
        if not job:
            return
        payload = {
            "id": job.id,
            "user_id": job.user_id,
            "channel_id": job.channel_id,
            "config_json": job.config_json,
        }
    finally:
        db.close()

    try:
        url = render(payload)
        finish(job_id, status="completed", output_url=url)
    except Exception as exc:
        finish(job_id, status="failed", error=str(exc)[:4000])


@app.get("/health")
def health():
    return {
        "ok": True,
        "mode": "on-demand",
        "storage_ready": storage_ready(),
        "engine": "wildvox-v2",
    }


@app.post("/render/{job_id}", status_code=202)
def start_render(
    job_id: str,
    background_tasks: BackgroundTasks,
    x_worker_secret: str | None = Header(default=None),
):
    authorize(x_worker_secret)
    if not storage_ready():
        raise HTTPException(status_code=503, detail="Object storage is not configured")

    db = SessionLocal()
    try:
        job = db.scalar(
            select(ProductionJob).where(ProductionJob.id == job_id)
        )
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        if job.status not in {"queued", "failed", "needs_attention"}:
            raise HTTPException(status_code=409, detail=f"Job is {job.status}")
        job.status = "rendering"
        job.attempts += 1
        job.error_message = None
        job.updated_at = datetime.now(timezone.utc)
        db.commit()
    finally:
        db.close()

    background_tasks.add_task(process_job, job_id)
    return {"accepted": True, "job_id": job_id}

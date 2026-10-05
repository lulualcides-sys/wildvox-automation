import json
import os
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

import boto3
from sqlalchemy import select

from voxflow.api.main import SessionLocal
from voxflow.api.production_router import ProductionJob, WorkerHeartbeat

ROOT = Path(os.getenv("VOXFLOW_REPO_ROOT", "/app"))
POLL_SECONDS = int(os.getenv("WORKER_POLL_SECONDS", "8"))

S3_ENDPOINT_URL = os.getenv("S3_ENDPOINT_URL", "")
S3_BUCKET = os.getenv("S3_BUCKET", "")
S3_ACCESS_KEY_ID = os.getenv("S3_ACCESS_KEY_ID", "")
S3_SECRET_ACCESS_KEY = os.getenv("S3_SECRET_ACCESS_KEY", "")
STORAGE_PUBLIC_BASE_URL = os.getenv("STORAGE_PUBLIC_BASE_URL", "").rstrip("/")


def storage_ready() -> bool:
    return bool(
        S3_ENDPOINT_URL
        and S3_BUCKET
        and S3_ACCESS_KEY_ID
        and S3_SECRET_ACCESS_KEY
        and STORAGE_PUBLIC_BASE_URL
    )


def heartbeat():
    db = SessionLocal()
    try:
        row = db.get(WorkerHeartbeat, "primary-render")
        now = datetime.now(timezone.utc)
        if not row:
            row = WorkerHeartbeat(
                id="primary-render",
                worker_type="render",
                last_seen_at=now,
                version="wildvox-v2",
            )
            db.add(row)
        else:
            row.last_seen_at = now
            row.version = "wildvox-v2"
        db.commit()
    finally:
        db.close()

def claim_job():
    db = SessionLocal()
    try:
        job = db.scalar(
            select(ProductionJob)
            .where(ProductionJob.status == "queued")
            .order_by(ProductionJob.created_at.asc())
            .with_for_update(skip_locked=True)
        )
        if not job:
            db.rollback()
            return None
        job.status = "rendering"
        job.attempts += 1
        job.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(job)
        return {
            "id": job.id,
            "user_id": job.user_id,
            "channel_id": job.channel_id,
            "config_json": job.config_json,
        }
    finally:
        db.close()


def finish(job_id: str, *, status: str, output_url: str | None = None, error: str | None = None):
    db = SessionLocal()
    try:
        job = db.get(ProductionJob, job_id)
        if not job:
            return
        job.status = status
        job.output_url = output_url
        job.error_message = error
        job.updated_at = datetime.now(timezone.utc)
        db.commit()
    finally:
        db.close()


def upload(path: Path, key: str) -> str:
    client = boto3.client(
        "s3",
        endpoint_url=S3_ENDPOINT_URL,
        aws_access_key_id=S3_ACCESS_KEY_ID,
        aws_secret_access_key=S3_SECRET_ACCESS_KEY,
    )
    client.upload_file(
        str(path),
        S3_BUCKET,
        key,
        ExtraArgs={"ContentType": "video/mp4"},
    )
    return f"{STORAGE_PUBLIC_BASE_URL}/{key}"


def render(job: dict):
    if not storage_ready():
        raise RuntimeError("S3/R2 storage is not configured for the render worker")

    config_dir = ROOT / "work" / "voxflow_jobs"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_path = config_dir / f"{job['id']}.json"
    cfg = json.loads(job["config_json"])
    config_path.write_text(
        json.dumps({job["id"]: cfg}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    relative_config = config_path.relative_to(ROOT).as_posix()
    subprocess.run(
        [
            "python",
            "scripts/generate_video.py",
            "--key",
            job["id"],
            "--config",
            relative_config,
        ],
        cwd=ROOT,
        check=True,
    )

    video_path = ROOT / "output" / f"{job['id']}.mp4"
    if not video_path.exists():
        raise RuntimeError("Render completed without an output MP4")

    key = f"users/{job['user_id']}/channels/{job['channel_id']}/{job['id']}.mp4"
    return upload(video_path, key)


def main():
    print("VoxFlow render worker started.", flush=True)
    while True:
        heartbeat()
        job = claim_job()
        if not job:
            time.sleep(POLL_SECONDS)
            continue

        print(f"Rendering {job['id']}", flush=True)
        try:
            url = render(job)
            finish(job["id"], status="completed", output_url=url)
            print(f"Completed {job['id']} -> {url}", flush=True)
        except Exception as exc:
            finish(job["id"], status="failed", error=str(exc)[:4000])
            print(f"Failed {job['id']}: {exc}", flush=True)


if __name__ == "__main__":
    main()

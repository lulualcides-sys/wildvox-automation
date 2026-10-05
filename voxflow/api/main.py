import base64
import os
import secrets
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from pydantic import BaseModel

BASE_DIR = Path(__file__).resolve().parent.parent
app = FastAPI(title="VoxFlow AI API", version="0.1.0")

PREVIEW_USERNAME = os.getenv("VOXFLOW_PREVIEW_USERNAME", "")
PREVIEW_PASSWORD = os.getenv("VOXFLOW_PREVIEW_PASSWORD", "")

@app.middleware("http")
async def security_middleware(request: Request, call_next):
    if PREVIEW_PASSWORD and request.url.path != "/health":
        auth = request.headers.get("authorization", "")
        allowed = False
        if auth.lower().startswith("basic "):
            try:
                raw = base64.b64decode(auth.split(" ", 1)[1]).decode("utf-8")
                username, password = raw.split(":", 1)
                allowed = (
                    secrets.compare_digest(username, PREVIEW_USERNAME or "preview")
                    and secrets.compare_digest(password, PREVIEW_PASSWORD)
                )
            except Exception:
                allowed = False
        if not allowed:
            return Response(
                content="VoxFlow private preview",
                status_code=401,
                headers={"WWW-Authenticate": 'Basic realm="VoxFlow Preview"'},
            )

    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; style-src 'self' 'unsafe-inline'; "
        "script-src 'self' 'unsafe-inline'; img-src 'self' data:; "
        "frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
    )
    return response

class ChannelCreate(BaseModel):
    name: str
    niche: str
    language: str = "en-US"
    videos_per_day: int = 3
    platform: Literal["tiktok", "instagram", "youtube"] = "tiktok"

@app.get("/", include_in_schema=False)
def web_app():
    return FileResponse(BASE_DIR / "index.html")

@app.get("/health")
def health():
    return {"ok": True, "service": "voxflow-api"}

@app.get("/channels")
def list_channels():
    return [{
        "id": "wildvox",
        "name": "WildVox",
        "niche": "animals-and-nature",
        "language": "en-US",
        "videos_per_day": 10,
        "status": "active"
    }]

@app.post("/channels")
def create_channel(payload: ChannelCreate):
    return {
        "id": payload.name.lower().replace(" ", "-"),
        "status": "draft",
        **payload.model_dump()
    }

@app.get("/videos")
def list_videos():
    return [
        {"title": "Blue-ringed octopus", "status": "published", "publish_at": "09:00"},
        {"title": "Blobfish", "status": "rendering", "publish_at": "10:00"},
        {"title": "Goblin shark", "status": "scheduled", "publish_at": "11:00"},
    ]

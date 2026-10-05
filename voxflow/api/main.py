from pathlib import Path
from typing import Literal

from fastapi import FastAPI
from fastapi.responses import FileResponse
from pydantic import BaseModel

BASE_DIR = Path(__file__).resolve().parent.parent
app = FastAPI(title="VoxFlow AI API", version="0.1.0")

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

import hashlib
import os
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Literal

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from fastapi import Cookie, Depends, FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import DateTime, ForeignKey, String, create_engine, select, text as sql_text
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship, sessionmaker

BASE_DIR = Path(__file__).resolve().parent.parent
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./voxflow.db")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+psycopg://", 1)
elif DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1)

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, pool_pre_ping=True, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
ph = PasswordHasher()
SESSION_DAYS = 30
COOKIE_NAME = "voxflow_session"

class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(500))
    plan: Mapped[str] = mapped_column(String(32), default="free")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    channels: Mapped[list["Channel"]] = relationship(back_populates="user", cascade="all, delete-orphan")

class SessionToken(Base):
    __tablename__ = "sessions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

class Channel(Base):
    __tablename__ = "channels"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    niche: Mapped[str] = mapped_column(String(100))
    language: Mapped[str] = mapped_column(String(16), default="en-US")
    videos_per_day: Mapped[int] = mapped_column(default=1)
    platform: Mapped[str] = mapped_column(String(32), default="tiktok")
    status: Mapped[str] = mapped_column(String(32), default="draft")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    user: Mapped[User] = relationship(back_populates="channels")

Base.metadata.create_all(bind=engine)

app = FastAPI(title="VoxFlow AI API", version="0.2.0")

@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; style-src 'self' 'unsafe-inline'; "
        "script-src 'self' 'unsafe-inline'; img-src 'self' data:; "
        "connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
    )
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response

class RegisterInput(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)

class LoginInput(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)

class ChannelCreate(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    niche: str = Field(min_length=2, max_length=100)
    language: str = "en-US"
    videos_per_day: int = Field(default=1, ge=1, le=10)
    platform: Literal["tiktok", "instagram", "youtube"] = "tiktok"

def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()

def set_session_cookie(response: Response, db: Session, user_id: str):
    token = secrets.token_urlsafe(48)
    db.add(SessionToken(
        id=str(uuid.uuid4()),
        user_id=user_id,
        token_hash=token_hash(token),
        expires_at=datetime.now(timezone.utc) + timedelta(days=SESSION_DAYS),
    ))
    db.commit()
    response.set_cookie(
        COOKIE_NAME,
        token,
        max_age=SESSION_DAYS * 86400,
        httponly=True,
        secure=True,
        samesite="lax",
        path="/",
    )

def current_user(
    session_token: str | None = Cookie(default=None, alias=COOKIE_NAME),
    db: Session = Depends(db_session),
) -> User:
    if not session_token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    now = datetime.now(timezone.utc)
    row = db.scalar(select(SessionToken).where(SessionToken.token_hash == token_hash(session_token)))
    if not row:
        raise HTTPException(status_code=401, detail="Invalid session")
    expires = row.expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if expires <= now:
        db.delete(row)
        db.commit()
        raise HTTPException(status_code=401, detail="Session expired")
    user = db.get(User, row.user_id)
    if not user:
        raise HTTPException(status_code=401, detail="Account unavailable")
    return user

@app.get("/", include_in_schema=False)
def web_app():
    return FileResponse(BASE_DIR / "index.html")

@app.get("/health")
def health():
    return {"ok": True, "service": "voxflow-api", "version": "0.2.0"}

@app.post("/api/auth/register")
def register(payload: RegisterInput, response: Response, db: Session = Depends(db_session)):
    email = str(payload.email).strip().lower()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(status_code=409, detail="Email already registered")
    user = User(
        id=str(uuid.uuid4()),
        name=payload.name.strip(),
        email=email,
        password_hash=ph.hash(payload.password),
        plan="free",
    )
    db.add(user)
    db.commit()
    set_session_cookie(response, db, user.id)
    return {"user": {"id": user.id, "name": user.name, "email": user.email, "plan": user.plan}}

@app.post("/api/auth/login")
def login(payload: LoginInput, response: Response, db: Session = Depends(db_session)):
    email = str(payload.email).strip().lower()
    user = db.scalar(select(User).where(User.email == email))
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    try:
        ph.verify(user.password_hash, payload.password)
    except VerifyMismatchError:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    set_session_cookie(response, db, user.id)
    return {"user": {"id": user.id, "name": user.name, "email": user.email, "plan": user.plan}}

@app.post("/api/auth/logout")
def logout(
    response: Response,
    session_token: str | None = Cookie(default=None, alias=COOKIE_NAME),
    db: Session = Depends(db_session),
):
    if session_token:
        row = db.scalar(select(SessionToken).where(SessionToken.token_hash == token_hash(session_token)))
        if row:
            db.delete(row)
            db.commit()
    response.delete_cookie(COOKIE_NAME, path="/")
    return {"ok": True}

@app.get("/api/auth/me")
def me(user: User = Depends(current_user)):
    return {"user": {"id": user.id, "name": user.name, "email": user.email, "plan": user.plan}}

@app.get("/api/channels")
def list_channels(user: User = Depends(current_user), db: Session = Depends(db_session)):
    channels = db.scalars(select(Channel).where(Channel.user_id == user.id).order_by(Channel.created_at.desc())).all()
    return {"channels": [
        {
            "id": c.id,
            "name": c.name,
            "niche": c.niche,
            "language": c.language,
            "videos_per_day": c.videos_per_day,
            "platform": c.platform,
            "status": c.status,
        } for c in channels
    ]}

@app.get("/api/system/status")
def system_status(user: User = Depends(current_user), db: Session = Depends(db_session)):
    db.execute(sql_text("SELECT 1"))
    return {
        "status": "operational",
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "components": [
            {"name": "VoxFlow API", "status": "operational"},
            {"name": "Database", "status": "operational"},
            {"name": "Automation engine", "status": "ready"},
            {"name": "Publishing queue", "status": "ready"},
        ],
    }

@app.post("/api/channels")
def create_channel(payload: ChannelCreate, user: User = Depends(current_user), db: Session = Depends(db_session)):
    channel = Channel(
        id=str(uuid.uuid4()),
        user_id=user.id,
        name=payload.name.strip(),
        niche=payload.niche.strip(),
        language=payload.language,
        videos_per_day=payload.videos_per_day,
        platform=payload.platform,
        status="draft",
    )
    db.add(channel)
    db.commit()
    return {
        "channel": {
            "id": channel.id,
            "name": channel.name,
            "niche": channel.niche,
            "language": channel.language,
            "videos_per_day": channel.videos_per_day,
            "platform": channel.platform,
            "status": channel.status,
        }
    }

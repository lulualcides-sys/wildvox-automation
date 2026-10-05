import hashlib
import os
import secrets
import time
import uuid
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Literal
from urllib.parse import urlencode

import httpx
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from cryptography.fernet import Fernet
from fastapi import Cookie, Depends, FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse, RedirectResponse
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, create_engine, select, text as sql_text
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship, sessionmaker

BASE_DIR = Path(__file__).resolve().parent.parent
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "https://voxflow-web-production-b580.up.railway.app").rstrip("/")
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
OAUTH_STATE_COOKIE = "voxflow_oauth_state"
TOKEN_ENCRYPTION_KEY = os.getenv("TOKEN_ENCRYPTION_KEY", "")
PLAN_LIMITS = {
    "free": {"channels": 1, "videos_per_day": 3, "videos_per_month": 3},
    "starter": {"channels": 1, "videos_per_day": 1, "videos_per_month": 30},
    "creator": {"channels": 2, "videos_per_day": 3, "videos_per_month": 90},
    "pro": {"channels": 3, "videos_per_day": 5, "videos_per_month": 150},
    "owner": {"channels": 1_000_000, "videos_per_day": 1_000_000, "videos_per_month": 1_000_000_000},
}
OWNER_USERNAME = os.getenv("VOXFLOW_OWNER_USERNAME", "").strip().lower()
OWNER_EMAIL = os.getenv("VOXFLOW_OWNER_EMAIL", "").strip().lower()
OWNER_BOOTSTRAP_PASSWORD = os.getenv("VOXFLOW_OWNER_PASSWORD", "")
# One-time bootstrap verifier. Removed after the owner row is created.
OWNER_BOOTSTRAP_HASH = "$argon2id$v=19$m=65536,t=3,p=4$UuOdJk3FZchxoNFJtRCDhQ$L8KLzg4+lO555FQfRZDXHrcQFtLDRmLmHaj/2FOpxAY"

LOGIN_WINDOW_SECONDS = 60
LOGIN_MAX_ATTEMPTS = 10
_attempts: dict[str, deque[float]] = defaultdict(deque)

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

class OAuthIdentity(Base):
    __tablename__ = "oauth_identities"
    __table_args__ = (UniqueConstraint("provider", "provider_user_id", name="uq_oauth_provider_user"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    provider: Mapped[str] = mapped_column(String(32), index=True)
    provider_user_id: Mapped[str] = mapped_column(String(320))
    email: Mapped[str] = mapped_column(String(320))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

class SocialConnection(Base):
    __tablename__ = "social_connections"
    __table_args__ = (UniqueConstraint("user_id", "provider", name="uq_social_user_provider"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    provider: Mapped[str] = mapped_column(String(32), index=True)
    external_account_id: Mapped[str | None] = mapped_column(String(320), nullable=True)
    handle: Mapped[str | None] = mapped_column(String(320), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="connected")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

class OAuthCredential(Base):
    __tablename__ = "oauth_credentials"
    __table_args__ = (UniqueConstraint("user_id", "provider", name="uq_oauth_credential_user_provider"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    provider: Mapped[str] = mapped_column(String(32), index=True)
    access_token_enc: Mapped[str] = mapped_column(String(4096))
    refresh_token_enc: Mapped[str | None] = mapped_column(String(4096), nullable=True)
    scope: Mapped[str | None] = mapped_column(String(1500), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

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

app = FastAPI(title="VoxFlow AI API", version="0.8.0")

@app.on_event("startup")
def bootstrap_owner_account():
    if not OWNER_EMAIL:
        return
    db = SessionLocal()
    try:
        user = db.scalar(select(User).where(User.email == OWNER_EMAIL))
        if not user and (OWNER_BOOTSTRAP_PASSWORD or OWNER_BOOTSTRAP_HASH):
            user = User(
                id=str(uuid.uuid4()),
                name="Lucas",
                email=OWNER_EMAIL,
                password_hash=ph.hash(OWNER_BOOTSTRAP_PASSWORD) if OWNER_BOOTSTRAP_PASSWORD else OWNER_BOOTSTRAP_HASH,
                plan="owner",
            )
            db.add(user)
            db.commit()
        elif user and user.plan != "owner":
            user.plan = "owner"
            db.commit()
    finally:
        db.close()

@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; style-src 'self' 'unsafe-inline'; "
        "script-src 'self' 'unsafe-inline'; img-src 'self' data: https:; "
        "connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
    )
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response

class RegisterInput(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)

class LoginInput(BaseModel):
    email: str = Field(min_length=1, max_length=320)
    password: str = Field(min_length=8, max_length=128)

class ChannelCreate(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    niche: str = Field(min_length=2, max_length=100)
    language: str = "en-US"
    videos_per_day: int = Field(default=1, ge=1, le=100)
    platform: Literal["tiktok", "instagram", "youtube"] = "tiktok"

class DeleteAccountInput(BaseModel):
    confirm: Literal["DELETE"]

def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()

def token_cipher() -> Fernet:
    if not TOKEN_ENCRYPTION_KEY:
        raise HTTPException(status_code=503, detail="Secure token storage is not configured")
    try:
        return Fernet(TOKEN_ENCRYPTION_KEY.encode())
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Secure token storage is invalid") from exc

def encrypt_secret(value: str | None) -> str | None:
    if not value:
        return None
    return token_cipher().encrypt(value.encode()).decode()

def plan_limits(plan: str) -> dict:
    return PLAN_LIMITS.get(plan, PLAN_LIMITS["free"])

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

def enforce_auth_rate_limit(request: Request):
    forwarded = request.headers.get("x-forwarded-for", "")
    ip = forwarded.split(",")[0].strip() if forwarded else (request.client.host if request.client else "unknown")
    now = time.monotonic()
    q = _attempts[ip]
    while q and q[0] < now - LOGIN_WINDOW_SECONDS:
        q.popleft()
    if len(q) >= LOGIN_MAX_ATTEMPTS:
        raise HTTPException(status_code=429, detail="Too many attempts. Try again in a minute.")
    q.append(now)

def provider_configured(provider: str) -> bool:
    if provider == "google":
        return bool(os.getenv("GOOGLE_CLIENT_ID") and os.getenv("GOOGLE_CLIENT_SECRET"))
    if provider == "microsoft":
        return bool(os.getenv("MICROSOFT_CLIENT_ID") and os.getenv("MICROSOFT_CLIENT_SECRET"))
    if provider == "apple":
        return bool(os.getenv("APPLE_CLIENT_ID") and os.getenv("APPLE_CLIENT_SECRET"))
    if provider == "youtube":
        return bool(os.getenv("GOOGLE_CLIENT_ID") and os.getenv("GOOGLE_CLIENT_SECRET"))
    if provider == "tiktok":
        return bool(os.getenv("TIKTOK_CLIENT_ID") and os.getenv("TIKTOK_CLIENT_SECRET"))
    if provider == "instagram":
        return bool(os.getenv("META_APP_ID") and os.getenv("META_APP_SECRET"))
    return False

def oauth_user(db: Session, provider: str, provider_user_id: str, email: str, name: str) -> User:
    identity = db.scalar(
        select(OAuthIdentity).where(
            OAuthIdentity.provider == provider,
            OAuthIdentity.provider_user_id == provider_user_id,
        )
    )
    if identity:
        user = db.get(User, identity.user_id)
        if user:
            return user
    user = db.scalar(select(User).where(User.email == email.lower()))
    if not user:
        user = User(
            id=str(uuid.uuid4()),
            name=name or email.split("@")[0],
            email=email.lower(),
            password_hash=ph.hash(secrets.token_urlsafe(48)),
            plan="free",
        )
        db.add(user)
        db.flush()
    if not identity:
        db.add(OAuthIdentity(
            id=str(uuid.uuid4()),
            user_id=user.id,
            provider=provider,
            provider_user_id=provider_user_id,
            email=email.lower(),
        ))
    db.commit()
    return user

@app.get("/", include_in_schema=False)
def web_app():
    return FileResponse(BASE_DIR / "index.html")

@app.get("/privacy", include_in_schema=False)
def privacy_page():
    return FileResponse(BASE_DIR / "privacy.html")

@app.get("/terms", include_in_schema=False)
def terms_page():
    return FileResponse(BASE_DIR / "terms.html")

@app.get("/health")
def health():
    return {"ok": True, "service": "voxflow-api", "version": "0.8.0"}

@app.get("/api/auth/providers")
def auth_providers():
    return {
        "providers": [
            {"id": "google", "label": "Google", "configured": provider_configured("google")},
            {"id": "microsoft", "label": "Microsoft", "configured": provider_configured("microsoft")},
            {"id": "apple", "label": "Apple", "configured": provider_configured("apple")},
        ]
    }

@app.post("/api/auth/register")
def register(payload: RegisterInput, response: Response, request: Request, db: Session = Depends(db_session)):
    enforce_auth_rate_limit(request)
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
def login(payload: LoginInput, response: Response, request: Request, db: Session = Depends(db_session)):
    enforce_auth_rate_limit(request)
    email = str(payload.email).strip().lower()
    if OWNER_USERNAME and OWNER_EMAIL and email == OWNER_USERNAME:
        email = OWNER_EMAIL
    user = db.scalar(select(User).where(User.email == email))
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    try:
        ph.verify(user.password_hash, payload.password)
    except VerifyMismatchError:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    set_session_cookie(response, db, user.id)
    return {"user": {"id": user.id, "name": user.name, "email": user.email, "plan": user.plan}}

@app.get("/api/auth/oauth/google")
def google_login():
    if not provider_configured("google"):
        raise HTTPException(status_code=503, detail="Google login is not configured yet")
    state = secrets.token_urlsafe(32)
    params = {
        "client_id": os.environ["GOOGLE_CLIENT_ID"],
        "redirect_uri": f"{PUBLIC_BASE_URL}/api/auth/oauth/google/callback",
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "access_type": "online",
        "prompt": "select_account",
    }
    response = RedirectResponse("https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(params))
    response.set_cookie(OAUTH_STATE_COOKIE, state, max_age=600, httponly=True, secure=True, samesite="lax")
    return response

@app.get("/api/auth/oauth/google/callback")
def google_callback(code: str, state: str, oauth_state: str | None = Cookie(default=None, alias=OAUTH_STATE_COOKIE), db: Session = Depends(db_session)):
    if not oauth_state or not secrets.compare_digest(state, oauth_state):
        raise HTTPException(status_code=400, detail="Invalid OAuth state")
    with httpx.Client(timeout=20) as client:
        token = client.post("https://oauth2.googleapis.com/token", data={
            "client_id": os.environ["GOOGLE_CLIENT_ID"],
            "client_secret": os.environ["GOOGLE_CLIENT_SECRET"],
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": f"{PUBLIC_BASE_URL}/api/auth/oauth/google/callback",
        })
        token.raise_for_status()
        access_token = token.json()["access_token"]
        profile = client.get("https://openidconnect.googleapis.com/v1/userinfo", headers={"Authorization": f"Bearer {access_token}"})
        profile.raise_for_status()
        info = profile.json()
    user = oauth_user(db, "google", info["sub"], info["email"], info.get("name", "Google user"))
    response = RedirectResponse(PUBLIC_BASE_URL + "/?login=success")
    set_session_cookie(response, db, user.id)
    response.delete_cookie(OAUTH_STATE_COOKIE, path="/")
    return response

@app.get("/api/auth/oauth/microsoft")
def microsoft_login():
    if not provider_configured("microsoft"):
        raise HTTPException(status_code=503, detail="Microsoft login is not configured yet")
    state = secrets.token_urlsafe(32)
    params = {
        "client_id": os.environ["MICROSOFT_CLIENT_ID"],
        "redirect_uri": f"{PUBLIC_BASE_URL}/api/auth/oauth/microsoft/callback",
        "response_type": "code",
        "response_mode": "query",
        "scope": "openid email profile User.Read",
        "state": state,
    }
    response = RedirectResponse("https://login.microsoftonline.com/common/oauth2/v2.0/authorize?" + urlencode(params))
    response.set_cookie(OAUTH_STATE_COOKIE, state, max_age=600, httponly=True, secure=True, samesite="lax")
    return response

@app.get("/api/auth/oauth/microsoft/callback")
def microsoft_callback(code: str, state: str, oauth_state: str | None = Cookie(default=None, alias=OAUTH_STATE_COOKIE), db: Session = Depends(db_session)):
    if not oauth_state or not secrets.compare_digest(state, oauth_state):
        raise HTTPException(status_code=400, detail="Invalid OAuth state")
    with httpx.Client(timeout=20) as client:
        token = client.post("https://login.microsoftonline.com/common/oauth2/v2.0/token", data={
            "client_id": os.environ["MICROSOFT_CLIENT_ID"],
            "client_secret": os.environ["MICROSOFT_CLIENT_SECRET"],
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": f"{PUBLIC_BASE_URL}/api/auth/oauth/microsoft/callback",
            "scope": "openid email profile User.Read",
        })
        token.raise_for_status()
        access_token = token.json()["access_token"]
        profile = client.get("https://graph.microsoft.com/v1.0/me", headers={"Authorization": f"Bearer {access_token}"})
        profile.raise_for_status()
        info = profile.json()
    email = info.get("mail") or info.get("userPrincipalName")
    if not email:
        raise HTTPException(status_code=400, detail="Microsoft account did not return an email")
    user = oauth_user(db, "microsoft", info["id"], email, info.get("displayName", "Microsoft user"))
    response = RedirectResponse(PUBLIC_BASE_URL + "/?login=success")
    set_session_cookie(response, db, user.id)
    response.delete_cookie(OAUTH_STATE_COOKIE, path="/")
    return response

@app.get("/api/auth/oauth/apple")
def apple_login():
    if not provider_configured("apple"):
        raise HTTPException(status_code=503, detail="Apple login is ready for credentials but is not configured yet")
    raise HTTPException(status_code=501, detail="Apple Sign In credential flow requires Apple developer keys before activation")

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

@app.get("/api/integrations")
def integrations(user: User = Depends(current_user), db: Session = Depends(db_session)):
    connected = {c.provider: c for c in db.scalars(select(SocialConnection).where(SocialConnection.user_id == user.id)).all()}
    providers = []
    for provider, label in [("youtube", "YouTube"), ("tiktok", "TikTok"), ("instagram", "Instagram")]:
        row = connected.get(provider)
        providers.append({
            "id": provider,
            "label": label,
            "configured": provider_configured(provider) and (provider != "youtube" or bool(TOKEN_ENCRYPTION_KEY)),
            "connected": bool(row and row.status == "connected"),
            "handle": row.handle if row else None,
            "recommended": provider == "youtube",
        })
    return {"providers": providers}

@app.get("/api/onboarding")
def onboarding(user: User = Depends(current_user), db: Session = Depends(db_session)):
    google_identity = db.scalar(
        select(OAuthIdentity).where(OAuthIdentity.user_id == user.id, OAuthIdentity.provider == "google")
    )
    youtube = db.scalar(
        select(SocialConnection).where(SocialConnection.user_id == user.id, SocialConnection.provider == "youtube")
    )
    channel_count = len(db.scalars(select(Channel).where(Channel.user_id == user.id)).all())
    steps = [
        {"id": "account", "label": "Create your VoxFlow account", "done": True},
        {"id": "google", "label": "Sign in with Google", "done": bool(google_identity), "optional": True},
        {"id": "youtube", "label": "Connect YouTube Shorts", "done": bool(youtube and youtube.status == "connected")},
        {"id": "channel", "label": "Create your first automated channel", "done": channel_count > 0},
        {"id": "plan", "label": "Choose a launch plan", "done": user.plan != "free", "optional": True},
    ]
    return {"steps": steps, "completed": sum(1 for s in steps if s["done"]), "total": len(steps)}

@app.get("/api/account/usage")
def account_usage(user: User = Depends(current_user), db: Session = Depends(db_session)):
    limits = plan_limits(user.plan)
    channel_count = len(db.scalars(select(Channel).where(Channel.user_id == user.id)).all())
    return {
        "plan": user.plan,
        "unlimited": user.plan == "owner",
        "channels": {"used": channel_count, "limit": None if user.plan == "owner" else limits["channels"]},
        "videos_per_day_limit": None if user.plan == "owner" else limits["videos_per_day"],
        "videos_per_month_limit": None if user.plan == "owner" else limits["videos_per_month"],
    }

@app.get("/api/integrations/connect/youtube")
def connect_youtube(user: User = Depends(current_user)):
    if not provider_configured("youtube"):
        raise HTTPException(status_code=503, detail="Google/YouTube developer credentials are not configured yet")
    if not TOKEN_ENCRYPTION_KEY:
        raise HTTPException(status_code=503, detail="Secure YouTube token storage is not configured yet")
    state = secrets.token_urlsafe(32)
    params = {
        "client_id": os.environ["GOOGLE_CLIENT_ID"],
        "redirect_uri": f"{PUBLIC_BASE_URL}/api/integrations/youtube/callback",
        "response_type": "code",
        "scope": "https://www.googleapis.com/auth/youtube.upload https://www.googleapis.com/auth/youtube.readonly",
        "state": state,
        "access_type": "offline",
        "prompt": "consent",
        "include_granted_scopes": "true",
    }
    response = RedirectResponse("https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(params))
    response.set_cookie(OAUTH_STATE_COOKIE, state, max_age=600, httponly=True, secure=True, samesite="lax")
    return response

@app.get("/api/integrations/youtube/callback")
def youtube_callback(
    code: str,
    state: str,
    response: Response,
    user: User = Depends(current_user),
    oauth_state: str | None = Cookie(default=None, alias=OAUTH_STATE_COOKIE),
    db: Session = Depends(db_session),
):
    if not oauth_state or not secrets.compare_digest(state, oauth_state):
        raise HTTPException(status_code=400, detail="Invalid OAuth state")

    with httpx.Client(timeout=25) as client:
        token_res = client.post("https://oauth2.googleapis.com/token", data={
            "client_id": os.environ["GOOGLE_CLIENT_ID"],
            "client_secret": os.environ["GOOGLE_CLIENT_SECRET"],
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": f"{PUBLIC_BASE_URL}/api/integrations/youtube/callback",
        })
        token_res.raise_for_status()
        token_data = token_res.json()
        access_token = token_data["access_token"]

        channel_res = client.get(
            "https://www.googleapis.com/youtube/v3/channels",
            params={"part": "snippet", "mine": "true"},
            headers={"Authorization": f"Bearer {access_token}"},
        )
        channel_res.raise_for_status()
        items = channel_res.json().get("items", [])

    if not items:
        raise HTTPException(status_code=400, detail="No YouTube channel was found for this Google account")

    channel = items[0]
    snippet = channel.get("snippet", {})
    channel_id = channel.get("id")
    handle = snippet.get("customUrl") or snippet.get("title") or channel_id
    expires_in = int(token_data.get("expires_in", 3600))
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)

    credential = db.scalar(
        select(OAuthCredential).where(
            OAuthCredential.user_id == user.id,
            OAuthCredential.provider == "youtube",
        )
    )
    if not credential:
        credential = OAuthCredential(
            id=str(uuid.uuid4()),
            user_id=user.id,
            provider="youtube",
            access_token_enc=encrypt_secret(access_token),
            refresh_token_enc=encrypt_secret(token_data.get("refresh_token")),
            scope=token_data.get("scope"),
            expires_at=expires_at,
            updated_at=datetime.now(timezone.utc),
        )
        db.add(credential)
    else:
        credential.access_token_enc = encrypt_secret(access_token)
        if token_data.get("refresh_token"):
            credential.refresh_token_enc = encrypt_secret(token_data["refresh_token"])
        credential.scope = token_data.get("scope")
        credential.expires_at = expires_at
        credential.updated_at = datetime.now(timezone.utc)

    connection = db.scalar(
        select(SocialConnection).where(
            SocialConnection.user_id == user.id,
            SocialConnection.provider == "youtube",
        )
    )
    if not connection:
        connection = SocialConnection(
            id=str(uuid.uuid4()),
            user_id=user.id,
            provider="youtube",
            external_account_id=channel_id,
            handle=handle,
            status="connected",
        )
        db.add(connection)
    else:
        connection.external_account_id = channel_id
        connection.handle = handle
        connection.status = "connected"

    db.commit()
    redirect = RedirectResponse(PUBLIC_BASE_URL + "/?youtube=connected")
    redirect.delete_cookie(OAUTH_STATE_COOKIE, path="/")
    return redirect

@app.get("/api/integrations/connect/{provider}")
def connect_platform_placeholder(
    provider: Literal["tiktok", "instagram"],
    user: User = Depends(current_user),
):
    if not provider_configured(provider):
        raise HTTPException(status_code=503, detail=f"{provider.title()} OAuth credentials are not configured yet")
    if provider == "tiktok":
        raise HTTPException(status_code=501, detail="TikTok is next in the connection roadmap and requires app approval")
    raise HTTPException(status_code=501, detail="Instagram connection requires the Meta app credentials and approval")

@app.delete("/api/integrations/{provider}")
def disconnect_platform(
    provider: Literal["youtube", "tiktok", "instagram"],
    user: User = Depends(current_user),
    db: Session = Depends(db_session),
):
    credential = db.scalar(
        select(OAuthCredential).where(
            OAuthCredential.user_id == user.id,
            OAuthCredential.provider == provider,
        )
    )
    if credential:
        db.delete(credential)
    connection = db.scalar(
        select(SocialConnection).where(
            SocialConnection.user_id == user.id,
            SocialConnection.provider == provider,
        )
    )
    if connection:
        db.delete(connection)
    db.commit()
    return {"ok": True}

@app.post("/api/channels")
def create_channel(payload: ChannelCreate, user: User = Depends(current_user), db: Session = Depends(db_session)):
    limits = plan_limits(user.plan)
    existing_channels = len(db.scalars(select(Channel).where(Channel.user_id == user.id)).all())
    if existing_channels >= limits["channels"]:
        raise HTTPException(status_code=403, detail=f"Your {user.plan} plan allows {limits['channels']} channel(s)")
    if payload.videos_per_day > limits["videos_per_day"]:
        raise HTTPException(status_code=403, detail=f"Your {user.plan} plan allows up to {limits['videos_per_day']} video(s) per day")

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

@app.delete("/api/account")
def delete_account(payload: DeleteAccountInput, response: Response, user: User = Depends(current_user), db: Session = Depends(db_session)):
    db.delete(user)
    db.commit()
    response.delete_cookie(COOKIE_NAME, path="/")
    return {"ok": True}


from .support_router import router as support_router
from .auth_extra import router as auth_extra_router
from .billing_router import router as billing_router
from .production_router import router as production_router

app.include_router(support_router)
app.include_router(auth_extra_router)
app.include_router(billing_router)
app.include_router(production_router)

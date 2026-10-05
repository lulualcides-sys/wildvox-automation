import hashlib
import os
import secrets
import uuid
from datetime import datetime, timedelta, timezone

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import DateTime, ForeignKey, String, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from .main import (
    Base,
    OAuthIdentity,
    User,
    current_user,
    db_session,
    enforce_auth_rate_limit,
    engine,
    ph,
)

router = APIRouter(prefix="/api", tags=["account-security"])

PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "").rstrip("/")
RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")
EMAIL_FROM = os.getenv("EMAIL_FROM", "VoxFlow <no-reply@voxflow.app>")


class EmailVerification(Base):
    __tablename__ = "email_verifications"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class PasswordReset(Base):
    __tablename__ = "password_resets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


Base.metadata.create_all(bind=engine)


class ForgotPasswordInput(BaseModel):
    email: EmailStr


class ResetPasswordInput(BaseModel):
    token: str = Field(min_length=20, max_length=300)
    password: str = Field(min_length=8, max_length=128)

class ChangePasswordInput(BaseModel):
    current_password: str = Field(min_length=8, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def email_delivery_configured() -> bool:
    return bool(RESEND_API_KEY and EMAIL_FROM and PUBLIC_BASE_URL)


def send_email(to: str, subject: str, html: str) -> None:
    if not email_delivery_configured():
        raise RuntimeError("Email delivery is not configured")
    with httpx.Client(timeout=20) as client:
        r = client.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {RESEND_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "from": EMAIL_FROM,
                "to": [to],
                "subject": subject,
                "html": html,
            },
        )
        r.raise_for_status()


def email_verified(user: User, db: Session) -> bool:
    # A verified Google identity already provides a verified email signal.
    google = db.scalar(
        select(OAuthIdentity).where(
            OAuthIdentity.user_id == user.id,
            OAuthIdentity.provider == "google",
        )
    )
    if google:
        return True

    verified = db.scalar(
        select(EmailVerification).where(
            EmailVerification.user_id == user.id,
            EmailVerification.verified_at.is_not(None),
        )
    )
    return bool(verified)


@router.get("/account/security-status")
def security_status(user: User = Depends(current_user), db: Session = Depends(db_session)):
    return {
        "email_verified": email_verified(user, db),
        "email_delivery_configured": email_delivery_configured(),
        "password_reset_available": email_delivery_configured(),
        "session_security": "secure-cookie",
        "password_hashing": "argon2",
    }


@router.post("/account/send-verification")
def send_verification(user: User = Depends(current_user), db: Session = Depends(db_session)):
    if email_verified(user, db):
        return {"ok": True, "already_verified": True}

    if not email_delivery_configured():
        return {
            "ok": False,
            "configured": False,
            "detail": "Email delivery is ready in VoxFlow but the transactional email provider is not configured yet.",
        }

    token = secrets.token_urlsafe(48)
    row = EmailVerification(
        id=str(uuid.uuid4()),
        user_id=user.id,
        token_hash=_hash(token),
        expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
    )
    db.add(row)
    db.commit()

    url = f"{PUBLIC_BASE_URL}/api/account/verify-email?token={token}"
    send_email(
        user.email,
        "Verify your VoxFlow email",
        f"""
        <div style="font-family:system-ui;max-width:560px;margin:auto">
          <h2>Verify your VoxFlow email</h2>
          <p>Confirm this address to secure your account and enable recovery features.</p>
          <p><a href="{url}" style="display:inline-block;background:#ff7a66;color:#111;padding:12px 18px;border-radius:10px;text-decoration:none;font-weight:700">Verify email</a></p>
          <p>This link expires in 24 hours.</p>
        </div>
        """,
    )
    return {"ok": True, "configured": True}


@router.get("/account/verify-email")
def verify_email(token: str, db: Session = Depends(db_session)):
    row = db.scalar(
        select(EmailVerification).where(EmailVerification.token_hash == _hash(token))
    )
    if not row or row.verified_at:
        raise HTTPException(status_code=400, detail="Verification link is invalid or already used")
    if _aware(row.expires_at) <= datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Verification link has expired")

    row.verified_at = datetime.now(timezone.utc)
    db.commit()
    from fastapi.responses import RedirectResponse

    return RedirectResponse((PUBLIC_BASE_URL or "/") + "/?email=verified")


@router.post("/account/change-password")
def change_password(
    payload: ChangePasswordInput,
    user: User = Depends(current_user),
    db: Session = Depends(db_session),
):
    try:
        ph.verify(user.password_hash, payload.current_password)
    except Exception:
        raise HTTPException(status_code=401, detail="Current password is incorrect")
    if payload.current_password == payload.new_password:
        raise HTTPException(status_code=400, detail="Choose a different new password")
    user.password_hash = ph.hash(payload.new_password)
    db.commit()
    return {"ok": True}

@router.post("/auth/forgot-password")
def forgot_password(
    payload: ForgotPasswordInput,
    request: Request,
    db: Session = Depends(db_session),
):
    enforce_auth_rate_limit(request)
    email = str(payload.email).strip().lower()
    user = db.scalar(select(User).where(User.email == email))

    # Always return the same public response to avoid account enumeration.
    public = {
        "ok": True,
        "configured": email_delivery_configured(),
        "message": "If an account exists for that email, a recovery message will be sent.",
    }
    if not user or not email_delivery_configured():
        return public

    token = secrets.token_urlsafe(48)
    db.add(
        PasswordReset(
            id=str(uuid.uuid4()),
            user_id=user.id,
            token_hash=_hash(token),
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=30),
        )
    )
    db.commit()

    url = f"{PUBLIC_BASE_URL}/?reset_token={token}"
    send_email(
        user.email,
        "Reset your VoxFlow password",
        f"""
        <div style="font-family:system-ui;max-width:560px;margin:auto">
          <h2>Reset your password</h2>
          <p>Use the button below to choose a new VoxFlow password.</p>
          <p><a href="{url}" style="display:inline-block;background:#ff7a66;color:#111;padding:12px 18px;border-radius:10px;text-decoration:none;font-weight:700">Reset password</a></p>
          <p>This link expires in 30 minutes. If you did not request it, ignore this email.</p>
        </div>
        """,
    )
    return public


@router.post("/auth/reset-password")
def reset_password(payload: ResetPasswordInput, db: Session = Depends(db_session)):
    row = db.scalar(
        select(PasswordReset).where(PasswordReset.token_hash == _hash(payload.token))
    )
    if not row or row.used_at:
        raise HTTPException(status_code=400, detail="Reset link is invalid or already used")
    if _aware(row.expires_at) <= datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Reset link has expired")

    user = db.get(User, row.user_id)
    if not user:
        raise HTTPException(status_code=400, detail="Account no longer exists")

    user.password_hash = ph.hash(payload.password)
    row.used_at = datetime.now(timezone.utc)
    db.commit()
    return {"ok": True}

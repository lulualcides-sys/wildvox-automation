import hashlib
import hmac
import os
import secrets
import uuid
from datetime import datetime, timedelta, timezone

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import DateTime, ForeignKey, String, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from .main import Base, User, current_user, db_session, engine

router = APIRouter(prefix="/api/billing", tags=["billing"])

PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "").rstrip("/")
MP_ACCESS_TOKEN = os.getenv("MERCADOPAGO_ACCESS_TOKEN", "")
MP_WEBHOOK_SECRET = os.getenv("MERCADOPAGO_WEBHOOK_SECRET", "")

PLANS = {
    "starter": {
        "name": "Starter",
        "amount": 39.90,
        "channels": 1,
        "videos_per_month": 30,
        "summary": "Validate one niche with consistent automated publishing.",
    },
    "creator": {
        "name": "Creator",
        "amount": 79.90,
        "channels": 2,
        "videos_per_month": 90,
        "summary": "Run daily content at higher volume across up to two channels.",
    },
    "pro": {
        "name": "Pro",
        "amount": 149.90,
        "channels": 3,
        "videos_per_month": 150,
        "summary": "Scale multiple channels with higher volume and priority processing.",
    },
}


class Subscription(Base):
    __tablename__ = "subscriptions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    provider: Mapped[str] = mapped_column(String(32), default="mercadopago")
    provider_subscription_id: Mapped[str | None] = mapped_column(String(160), nullable=True, unique=True)
    plan: Mapped[str] = mapped_column(String(32), index=True)
    status: Mapped[str] = mapped_column(String(32), default="pending", index=True)
    mode: Mapped[str] = mapped_column(String(32), default="recurring")
    current_period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class PaymentOrder(Base):
    __tablename__ = "payment_orders"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    provider_order_id: Mapped[str | None] = mapped_column(String(160), nullable=True, unique=True)
    plan: Mapped[str] = mapped_column(String(32), index=True)
    status: Mapped[str] = mapped_column(String(32), default="created")
    amount: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


Base.metadata.create_all(bind=engine)


def configured() -> bool:
    return bool(MP_ACCESS_TOKEN and PUBLIC_BASE_URL)


def mp_headers(extra: dict | None = None) -> dict:
    headers = {
        "Authorization": f"Bearer {MP_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }
    if extra:
        headers.update(extra)
    return headers


def external_ref(user_id: str, plan: str, kind: str) -> str:
    # Mercado Pago external_reference has a limited size; UUID + compact plan/kind fits.
    return f"vf-{kind}-{plan}-{user_id}"[:64]


def parse_external_ref(value: str | None):
    if not value or not value.startswith("vf-"):
        return None
    parts = value.split("-", 3)
    if len(parts) != 4:
        return None
    _, kind, plan, user_id = parts
    if plan not in PLANS:
        return None
    return kind, plan, user_id


def verify_webhook(request: Request, data_id: str) -> bool:
    if not MP_WEBHOOK_SECRET:
        return False
    signature = request.headers.get("x-signature", "")
    request_id = request.headers.get("x-request-id", "")
    values = {}
    for part in signature.split(","):
        if "=" in part:
            k, v = part.strip().split("=", 1)
            values[k] = v
    ts = values.get("ts", "")
    v1 = values.get("v1", "")
    if not ts or not v1 or not request_id:
        return False
    manifest = f"id:{data_id};request-id:{request_id};ts:{ts};"
    expected = hmac.new(
        MP_WEBHOOK_SECRET.encode(),
        manifest.encode(),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, v1)


@router.get("/plans")
def plans():
    return {
        "provider": "mercadopago",
        "configured": configured(),
        "plans": [
            {"id": key, **value}
            for key, value in PLANS.items()
        ],
        "currency": "BRL",
    }


@router.get("/status")
def billing_status(user: User = Depends(current_user), db: Session = Depends(db_session)):
    latest = db.scalar(
        select(Subscription)
        .where(Subscription.user_id == user.id)
        .order_by(Subscription.created_at.desc())
    )
    return {
        "plan": user.plan,
        "provider": "mercadopago",
        "configured": configured(),
        "subscription": None if not latest else {
            "plan": latest.plan,
            "status": latest.status,
            "mode": latest.mode,
            "current_period_end": latest.current_period_end.isoformat() if latest.current_period_end else None,
        },
    }


@router.post("/subscribe/{plan}")
def subscribe(plan: str, user: User = Depends(current_user), db: Session = Depends(db_session)):
    if user.plan == "owner":
        raise HTTPException(status_code=403, detail="Owner accounts are unlimited and do not require billing")
    if plan not in PLANS:
        raise HTTPException(status_code=404, detail="Unknown plan")
    if not configured():
        raise HTTPException(
            status_code=503,
            detail="Mercado Pago is prepared but production billing credentials are not configured yet",
        )

    data = PLANS[plan]
    ref = external_ref(user.id, plan, "sub")
    payload = {
        "reason": f"VoxFlow {data['name']} monthly",
        "external_reference": ref,
        "payer_email": user.email,
        "back_url": f"{PUBLIC_BASE_URL}/?billing=return",
        "status": "pending",
        "auto_recurring": {
            "frequency": 1,
            "frequency_type": "months",
            "transaction_amount": data["amount"],
            "currency_id": "BRL",
        },
    }

    with httpx.Client(timeout=30) as client:
        r = client.post(
            "https://api.mercadopago.com/preapproval",
            headers=mp_headers(),
            json=payload,
        )
        if r.status_code >= 400:
            raise HTTPException(status_code=502, detail="Mercado Pago could not create the subscription checkout")
        result = r.json()

    provider_id = result.get("id")
    init_point = result.get("init_point")
    if not provider_id or not init_point:
        raise HTTPException(status_code=502, detail="Mercado Pago returned an incomplete subscription response")

    row = Subscription(
        id=str(uuid.uuid4()),
        user_id=user.id,
        provider_subscription_id=provider_id,
        plan=plan,
        status=result.get("status", "pending"),
        mode="recurring",
        updated_at=datetime.now(timezone.utc),
    )
    db.add(row)
    db.commit()
    return {"checkout_url": init_point, "subscription_id": provider_id}


@router.post("/pay-month/{plan}")
def pay_month(plan: str, user: User = Depends(current_user), db: Session = Depends(db_session)):
    if user.plan == "owner":
        raise HTTPException(status_code=403, detail="Owner accounts are unlimited and do not require billing")
    if plan not in PLANS:
        raise HTTPException(status_code=404, detail="Unknown plan")
    if not configured():
        raise HTTPException(
            status_code=503,
            detail="Mercado Pago is prepared but production billing credentials are not configured yet",
        )

    data = PLANS[plan]
    local_id = str(uuid.uuid4())
    ref = external_ref(user.id, plan, "month")
    amount = f"{data['amount']:.2f}"
    payload = {
        "type": "online",
        "processing_mode": "manual",
        "capture_mode": "automatic_async",
        "total_amount": amount,
        "external_reference": ref,
        "description": f"VoxFlow {data['name']} - 30 days",
        "payer": {"email": user.email},
        "items": [{
            "title": f"VoxFlow {data['name']} - 30 days",
            "unit_price": amount,
            "quantity": 1,
            "unit_measure": "unit",
            "total_amount": amount,
        }],
        "config": {
            "online": {
                "success_url": f"{PUBLIC_BASE_URL}/?billing=success",
                "pending_url": f"{PUBLIC_BASE_URL}/?billing=pending",
                "failure_url": f"{PUBLIC_BASE_URL}/?billing=failed",
            }
        },
    }

    with httpx.Client(timeout=30) as client:
        r = client.post(
            "https://api.mercadopago.com/v1/orders",
            headers=mp_headers({"X-Idempotency-Key": local_id}),
            json=payload,
        )
        if r.status_code >= 400:
            raise HTTPException(status_code=502, detail="Mercado Pago could not create the monthly checkout")
        result = r.json()

    provider_id = result.get("id")
    checkout_url = result.get("checkout_url")
    if not provider_id or not checkout_url:
        raise HTTPException(status_code=502, detail="Mercado Pago returned an incomplete checkout response")

    db.add(PaymentOrder(
        id=local_id,
        user_id=user.id,
        provider_order_id=provider_id,
        plan=plan,
        status=result.get("status", "created"),
        amount=amount,
    ))
    db.commit()
    return {"checkout_url": checkout_url, "order_id": provider_id}


@router.post("/cancel")
def cancel_subscription(user: User = Depends(current_user), db: Session = Depends(db_session)):
    row = db.scalar(
        select(Subscription)
        .where(
            Subscription.user_id == user.id,
            Subscription.status.in_(["authorized", "paused", "pending"]),
        )
        .order_by(Subscription.created_at.desc())
    )
    if not row or not row.provider_subscription_id:
        raise HTTPException(status_code=404, detail="No active subscription found")
    if not configured():
        raise HTTPException(status_code=503, detail="Billing provider is not configured")

    with httpx.Client(timeout=30) as client:
        r = client.put(
            f"https://api.mercadopago.com/preapproval/{row.provider_subscription_id}",
            headers=mp_headers(),
            json={"status": "cancelled"},
        )
        if r.status_code >= 400:
            # Some Mercado Pago versions use canceled instead of cancelled.
            r = client.put(
                f"https://api.mercadopago.com/preapproval/{row.provider_subscription_id}",
                headers=mp_headers(),
                json={"status": "canceled"},
            )
        if r.status_code >= 400:
            raise HTTPException(status_code=502, detail="Could not cancel subscription")

    row.status = "canceled"
    row.updated_at = datetime.now(timezone.utc)
    user.plan = "free"
    db.commit()
    return {"ok": True}


@router.post("/webhook")
async def webhook(request: Request, db: Session = Depends(db_session)):
    body = await request.json()
    data = body.get("data") or {}
    data_id = str(data.get("id") or request.query_params.get("data.id") or "")
    if not data_id or not verify_webhook(request, data_id):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    event_type = str(body.get("type") or body.get("topic") or "")
    headers = mp_headers()

    # Subscription/preapproval webhook.
    if "preapproval" in event_type or not data_id.startswith("ORD"):
        with httpx.Client(timeout=30) as client:
            r = client.get(f"https://api.mercadopago.com/preapproval/{data_id}", headers=headers)
        if r.status_code < 400:
            result = r.json()
            parsed = parse_external_ref(result.get("external_reference"))
            if parsed:
                kind, plan, user_id = parsed
                user = db.get(User, user_id)
                row = db.scalar(
                    select(Subscription).where(Subscription.provider_subscription_id == data_id)
                )
                if user:
                    status = result.get("status", "pending")
                    if not row:
                        row = Subscription(
                            id=str(uuid.uuid4()),
                            user_id=user.id,
                            provider_subscription_id=data_id,
                            plan=plan,
                            status=status,
                            mode="recurring",
                        )
                        db.add(row)
                    else:
                        row.status = status
                        row.plan = plan
                        row.updated_at = datetime.now(timezone.utc)
                    if status == "authorized":
                        user.plan = plan
                    elif status in {"canceled", "cancelled"}:
                        user.plan = "free"
                    db.commit()
            return {"ok": True}

    # Checkout Pro Orders webhook for a prepaid 30-day pass.
    with httpx.Client(timeout=30) as client:
        r = client.get(f"https://api.mercadopago.com/v1/orders/{data_id}", headers=headers)
    if r.status_code >= 400:
        return {"ok": True}

    result = r.json()
    parsed = parse_external_ref(result.get("external_reference"))
    if parsed:
        kind, plan, user_id = parsed
        user = db.get(User, user_id)
        row = db.scalar(select(PaymentOrder).where(PaymentOrder.provider_order_id == data_id))
        if row:
            row.status = result.get("status", row.status)
        if user and kind == "month":
            if result.get("status") == "processed" and result.get("status_detail") == "accredited":
                user.plan = plan
                # Store a synthetic non-recurring entitlement record.
                ent = Subscription(
                    id=str(uuid.uuid4()),
                    user_id=user.id,
                    provider_subscription_id=None,
                    plan=plan,
                    status="authorized",
                    mode="prepaid_30d",
                    current_period_end=datetime.now(timezone.utc) + timedelta(days=30),
                )
                db.add(ent)
        db.commit()

    return {"ok": True}

import os
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import DateTime, ForeignKey, String, Text, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from .main import (
    Base,
    Channel,
    OAuthIdentity,
    SocialConnection,
    TOKEN_ENCRYPTION_KEY,
    User,
    db_session,
    engine,
    plan_limits,
    provider_configured,
    current_user,
)

router = APIRouter(prefix="/api/support", tags=["support"])


class SupportMessageLog(Base):
    __tablename__ = "support_messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(16))
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )


Base.metadata.create_all(bind=engine)


class SupportInput(BaseModel):
    message: str = Field(min_length=1, max_length=2000)


def build_context(user: User, db: Session) -> dict:
    google_identity = db.scalar(
        select(OAuthIdentity).where(
            OAuthIdentity.user_id == user.id,
            OAuthIdentity.provider == "google",
        )
    )
    connections = {
        row.provider: row
        for row in db.scalars(
            select(SocialConnection).where(SocialConnection.user_id == user.id)
        ).all()
    }
    channels = db.scalars(select(Channel).where(Channel.user_id == user.id)).all()

    return {
        "google_login": bool(google_identity),
        "google_configured": provider_configured("google"),
        "youtube_connected": bool(
            connections.get("youtube")
            and connections["youtube"].status == "connected"
        ),
        "youtube_configured": provider_configured("youtube")
        and bool(TOKEN_ENCRYPTION_KEY),
        "tiktok_connected": bool(
            connections.get("tiktok") and connections["tiktok"].status == "connected"
        ),
        "tiktok_configured": provider_configured("tiktok"),
        "instagram_connected": bool(
            connections.get("instagram")
            and connections["instagram"].status == "connected"
        ),
        "instagram_configured": provider_configured("instagram"),
        "channel_count": len(channels),
        "plan": user.plan,
        "limits": plan_limits(user.plan),
        "email_delivery_configured": bool(os.getenv("RESEND_API_KEY") and os.getenv("EMAIL_FROM")),
        "billing_configured": bool(os.getenv("MERCADOPAGO_ACCESS_TOKEN")),
        "storage_configured": bool(
            os.getenv("S3_ENDPOINT_URL")
            and os.getenv("S3_BUCKET")
            and os.getenv("S3_ACCESS_KEY_ID")
            and os.getenv("S3_SECRET_ACCESS_KEY")
        ),
    }


def answer(message: str, ctx: dict) -> tuple[str, list[str]]:
    text = message.lower().strip()

    if any(k in text for k in ["google", "gmail", "login google", "entrar com google"]):
        if not ctx["google_configured"]:
            return (
                "O login com Google já está preparado no VoxFlow, mas as credenciais oficiais do Google Cloud ainda precisam ser ativadas no servidor. Enquanto isso, entre por e-mail e senha normalmente.",
                ["Check integrations"],
            )
        if ctx["google_login"]:
            return (
                "Sua conta já está vinculada ao Google. Para publicar no YouTube, a autorização é separada: conecte o YouTube em Connected platforms. Assim o login não concede permissão de publicação automaticamente.",
                ["Connect YouTube"],
            )
        return (
            "O Google está disponível para login. Use Continue with Google na tela de acesso. Depois, conecte o YouTube separadamente no painel.",
            ["Sign in with Google"],
        )

    if any(k in text for k in ["youtube", "shorts", "canal do youtube", "publicar no youtube"]):
        if ctx["youtube_connected"]:
            return (
                "Seu YouTube já está conectado. Agora crie um canal de automação com YouTube Shorts como plataforma para preparar a produção e publicação.",
                ["Create channel", "Check automation"],
            )
        if not ctx["youtube_configured"]:
            return (
                "A integração do YouTube está pronta no código, inclusive com armazenamento criptografado de tokens, mas ainda faltam as credenciais oficiais do Google/YouTube no servidor.",
                ["Check integrations"],
            )
        return (
            "Seu YouTube ainda não está conectado. Vá em Connected platforms e toque em Connect YouTube. O Google pedirá apenas as permissões necessárias; sua senha do YouTube não é entregue ao VoxFlow.",
            ["Connect YouTube"],
        )

    if any(k in text for k in ["tiktok", "instagram", "reels", "meta"]):
        provider = "TikTok" if "tiktok" in text else "Instagram"
        key = provider.lower()
        connected = ctx[f"{key}_connected"]
        configured = ctx[f"{key}_configured"]
        if connected:
            return (f"{provider} já está conectado à sua conta.", ["Check automation"])
        if configured:
            return (
                f"{provider} está preparado para conexão, mas a autorização final da plataforma ainda precisa ser concluída.",
                ["Check integrations"],
            )
        return (
            f"A estrutura do {provider} já existe no VoxFlow, mas o aplicativo oficial ainda precisa das credenciais/aprovação da plataforma.",
            ["Check integrations"],
        )

    if any(k in text for k in ["esqueci", "senha", "password", "email", "verificar", "verificação", "recuperar"]):
        if not ctx["email_delivery_configured"]:
            return (
                "O fluxo de verificação e recuperação de senha já está pronto, mas o provedor de e-mail transacional ainda não está configurado. Por isso o VoxFlow não deve afirmar que enviou uma mensagem. Assim que a credencial de e-mail for ativada, os links terão expiração segura.",
                ["Account security"],
            )
        return (
            "A recuperação de senha e a verificação de e-mail estão ativas. Use Forgot password na tela de login ou Verify email em Account security.",
            ["Account security"],
        )

    if any(k in text for k in ["pagamento", "pagar", "mercado pago", "billing", "assinatura", "pix", "cartão", "cartao"]):
        if not ctx["billing_configured"]:
            return (
                "O billing do Mercado Pago já está implementado, mas ainda não existem credenciais de produção no servidor. Nenhuma cobrança real será iniciada até essa configuração ser feita.",
                ["View pricing"],
            )
        return (
            "O Mercado Pago está configurado. Você pode usar assinatura mensal ou checkout de 30 dias no painel Billing & plan. O plano só é liberado após confirmação autenticada do webhook.",
            ["View pricing"],
        )

    if any(k in text for k in ["worker", "fila", "render não", "render nao", "renderização", "renderizacao"]):
        if not ctx["storage_configured"]:
            return (
                "O motor WildVox v2, a fila e o worker já estão preparados, mas o storage S3/R2 ainda não está configurado. O VoxFlow não enfileira um render real sem worker/storage disponíveis, evitando jobs presos.",
                ["Check automation"],
            )
        return (
            "A produção usa fila isolada do site. Confira Production engine para saber se o render worker está online e se o job está queued, rendering, completed ou failed.",
            ["Check automation"],
        )

    if any(k in text for k in ["preço", "preco", "plano", "starter", "creator", "pro", "limite", "mensal"]):
        limits = ctx["limits"]
        return (
            f"Você está no plano {ctx['plan'].upper()}. Ele permite {limits['channels']} canal(is), até {limits['videos_per_day']} vídeo(s) por dia e {limits['videos_per_month']} vídeo(s) por mês. Os preços planejados são Starter R$39,90, Creator R$79,90 e Pro R$149,90 por mês.",
            ["View pricing"],
        )

    if any(k in text for k in ["canal", "automação", "automacao", "vídeo", "video", "render", "publicação", "publicacao"]):
        if ctx["channel_count"] == 0:
            return (
                "Sua conta ainda não tem um canal. Crie o primeiro canal, escolha nicho, idioma, frequência e plataforma. Para começar com menos atrito, recomendo YouTube Shorts.",
                ["Create channel"],
            )
        return (
            f"Sua conta tem {ctx['channel_count']} canal(is). Se um vídeo não publicou, confira Automation status e Connected platforms. O suporte usa esses estados para separar problema de conta, integração ou produção.",
            ["Check automation", "Check integrations"],
        )

    if any(k in text for k in ["erro", "falhou", "não funciona", "nao funciona", "problema", "502", "fora do ar", "travou"]):
        problems = []
        if not ctx["youtube_connected"]:
            problems.append("YouTube não conectado")
        if ctx["channel_count"] == 0:
            problems.append("nenhum canal criado")
        if not ctx["google_configured"]:
            problems.append("Google OAuth aguardando credenciais")
        if problems:
            return (
                "Encontrei estes pontos pendentes: " + "; ".join(problems) + ". Comece pelo primeiro. Se você me disser a mensagem que apareceu na tela, eu direciono o diagnóstico.",
                ["Check automation", "Check integrations"],
            )
        return (
            "Sua configuração básica parece completa. Diga qual ação falhou — login, conexão, criação de canal, renderização ou publicação — e a mensagem exibida.",
            ["Check automation"],
        )

    return (
        "Sou o suporte do VoxFlow. Posso ajudar com login, Google, YouTube, TikTok, Instagram, criação de canais, planos, automação, renderização e publicação. Descreva o que você tentou fazer e o que aconteceu.",
        ["Google & YouTube", "Automation", "Plans"],
    )


@router.get("/history")
def history(user: User = Depends(current_user), db: Session = Depends(db_session)):
    rows = db.scalars(
        select(SupportMessageLog)
        .where(SupportMessageLog.user_id == user.id)
        .order_by(SupportMessageLog.created_at.desc())
        .limit(30)
    ).all()
    return {
        "messages": [
            {
                "role": row.role,
                "content": row.content,
                "created_at": row.created_at.isoformat(),
            }
            for row in reversed(rows)
        ]
    }


@router.post("/chat")
def chat(payload: SupportInput, user: User = Depends(current_user), db: Session = Depends(db_session)):
    message = payload.message.strip()
    reply, actions = answer(message, build_context(user, db))

    db.add(
        SupportMessageLog(
            id=str(uuid.uuid4()),
            user_id=user.id,
            role="user",
            content=message,
        )
    )
    db.add(
        SupportMessageLog(
            id=str(uuid.uuid4()),
            user_id=user.id,
            role="assistant",
            content=reply,
        )
    )
    db.commit()

    return {"reply": reply, "actions": actions, "context_used": True}

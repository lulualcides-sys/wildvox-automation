# VoxFlow AI

VoxFlow AI is a SaaS for automated short-form content channels.

## Current online private preview

The current build includes:

- Public commercial landing page and founding monthly plans.
- Real user registration and login with Argon2 passwords and secure HttpOnly sessions.
- Google/Microsoft/Apple sign-in UI; Google and Microsoft OAuth backend flows are prepared for official credentials.
- Separate YouTube authorization flow so login access does not automatically grant publishing permission.
- Encrypted server-side storage for YouTube OAuth tokens.
- Contextual VoxFlow Support AI with account-aware troubleshooting and persistent history.
- PostgreSQL on Railway private networking.
- Per-user channel isolation and plan limits.
- Live automation status and onboarding checklist.
- Email verification and password-reset flows with expiring hashed tokens.
- Mercado Pago billing foundation for recurring subscription and 30-day checkout.
- HMAC validation for Mercado Pago webhooks before plan changes.
- Production job queue tied to user/channel and monthly video allowance.
- WildVox v2 render-worker container with FFmpeg/Kokoro.
- S3/R2 upload support for rendered MP4 output.
- Worker heartbeat safety so the UI will not queue videos into an offline renderer.
- Privacy and Terms preview pages.
- HTTPS and baseline security headers.

## Recommended customer journey

1. Create account / sign in with Google.
2. Verify email.
3. Connect YouTube separately for publishing.
4. Create an automated channel.
5. Choose a paid plan.
6. VoxFlow creates production jobs within the plan allowance.
7. A dedicated render worker executes WildVox v2 rendering and uploads output to object storage.
8. Publishing and analytics layers consume the finished output.
9. Support AI diagnoses common account, integration, billing, and production problems.

## Billing

The planned founding prices are:

- Starter — R$39.90/month — 1 channel / 30 videos per month.
- Creator — R$79.90/month — 2 channels / 90 videos per month.
- Pro — R$149.90/month — 3 channels / 150 videos per month.

Billing code is provider-ready for Mercado Pago but no charge occurs until production credentials are configured.

## Production architecture

Browser
→ FastAPI web/API
→ PostgreSQL queue
→ dedicated render worker
→ WildVox v2 generator (Kokoro + FFmpeg)
→ S3-compatible object storage
→ social publishing integration
→ analytics

The worker is intentionally a separate service. Do not run video rendering inside the web process.

## Worker activation

The worker code lives in `voxflow/worker/`.

Build context should be the repository root because the worker reuses `scripts/generate_video.py`.

Required worker variables:

- `DATABASE_URL`
- `S3_ENDPOINT_URL`
- `S3_BUCKET`
- `S3_ACCESS_KEY_ID`
- `S3_SECRET_ACCESS_KEY`
- `STORAGE_PUBLIC_BASE_URL`

The web UI only enables real preview queuing while a recent worker heartbeat exists.

## Still required before a paid public launch

1. Production Google OAuth credentials.
2. Transactional email sender/domain credentials.
3. Mercado Pago production token + webhook secret.
4. S3/R2 bucket credentials.
5. Activate a dedicated render worker after infrastructure cost approval.
6. Complete TikTok and Meta app approval.
7. Add a content-research/generation agent for niches beyond the initial Animals & Nature preview.
8. Move VoxFlow source to a dedicated private repository.
9. Replace preview Terms/Privacy with complete LGPD/commercial documents.
10. Add backups, admin controls, abuse monitoring, and production observability.

## Local web development

```bash
cd voxflow
docker compose up --build
```

Without `DATABASE_URL`, the API falls back to local SQLite for development only.

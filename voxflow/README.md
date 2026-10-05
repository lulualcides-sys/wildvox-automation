# VoxFlow AI

VoxFlow AI is a SaaS for automated short-form content channels.

## Current online MVP

The current private-preview build includes:

- Public landing page and founding pricing.
- Real user registration and login.
- Argon2 password hashing.
- 30-day secure HttpOnly sessions.
- Private PostgreSQL database on Railway.
- User-isolated channel creation and listing.
- FastAPI backend and responsive single-page frontend.
- HTTPS on Railway with security headers.

## Current user flow

1. Open the landing page.
2. Create an account with name, email and password.
3. Sign in and enter a private dashboard.
4. Create a channel with niche, language, frequency and platform.
5. The channel is stored under that user's account.

## Architecture

Browser
→ FastAPI
→ PostgreSQL (private Railway network)

Next:
→ job queue / Redis
→ script + voice + media workers
→ FFmpeg rendering
→ object storage
→ social OAuth + publishing
→ analytics ingestion
→ billing + plan enforcement

## Security baseline

- Passwords are never stored in plaintext.
- Login sessions use random opaque tokens; only token hashes are stored in the database.
- Cookies are Secure, HttpOnly and SameSite=Lax.
- PostgreSQL has no public TCP proxy.
- Basic security headers are enabled.
- Secrets belong in Railway variables, not source code.

## Next production milestones

1. Email verification and password reset.
2. Rate limiting / anti-abuse controls.
3. Social OAuth connections (TikTok first).
4. Generalize the WildVox generation engine into per-user jobs.
5. Redis queue + render worker.
6. Object storage for rendered MP4s.
7. Billing (Pix/card) and plan/usage limits.
8. Video library, calendar and real analytics.
9. Terms, Privacy Policy and LGPD controls.
10. Move VoxFlow source to its own private GitHub repository before commercial launch.

## Local development

```bash
cd voxflow
docker compose up --build
```

Without DATABASE_URL the API falls back to local SQLite for development only.

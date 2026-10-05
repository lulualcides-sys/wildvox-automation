# VoxFlow AI

VoxFlow AI is a SaaS concept for automated short-form content channels.

## MVP goal

A customer should be able to:
1. Create an account.
2. Define a niche, language, style and daily video count.
3. Connect a social account.
4. Let VoxFlow plan, create, render, schedule and publish videos automatically.
5. See production status and performance from one dashboard.

## Current prototype

- `index.html`: responsive landing page + dashboard demo + channel-creation wizard.
- `api/`: minimal FastAPI service skeleton.
- `database/schema.sql`: initial PostgreSQL data model.
- `.env.example`: future integration configuration.

## Product architecture

Frontend
→ API
→ PostgreSQL
→ Queue/workers
→ Script/voice/media engine
→ FFmpeg rendering
→ Object storage
→ Social publishing APIs
→ Analytics ingestion

## Relationship with WildVox

WildVox remains the live test channel. VoxFlow should consume a generalized version of the production patterns proven there, rather than coupling customers directly to the WildVox repository.

## Next implementation milestones

1. Authentication and workspace creation.
2. Real CRUD for channels.
3. Worker queue and render jobs.
4. Generalize the WildVox generator into reusable templates.
5. Storage layer for MP4 output.
6. TikTok connection and publishing.
7. Billing and plan limits.
8. Analytics and automated optimization.

## Local prototype

Open `index.html` directly in a browser.

Run API:
```bash
cd api
pip install -r requirements.txt
uvicorn main:app --reload
```

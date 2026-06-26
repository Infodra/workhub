# Backend (FastAPI)

## Start
- Install: `pip install -r requirements.txt`
- Run: `uvicorn app.main:app --reload`

## Architecture
- API Layer: `app/api/v1/routes`
- Service Layer: `app/services`
- Repository Layer: `app/repositories`
- Core: config, security, DI, logging
- Jobs: APScheduler periodic sync

## Sync Frequency
- Every 15 minutes (`SCHEDULER_INTERVAL_MINUTES`).

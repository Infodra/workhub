# Background Scheduler Options

## Option A: APScheduler (Current)
- Built into FastAPI app.
- Runs every 15 minutes.
- Best for low-medium scale.

## Option B: Azure Function Timer Trigger
- Better for strict reliability and independent scaling.
- Timer expression: `0 */15 * * * *`.
- Function should call backend `/api/v1/sync` with managed identity or client credentials.

## Recommendation
Use APScheduler initially, migrate to Azure Functions as scale grows.

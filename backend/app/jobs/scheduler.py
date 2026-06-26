from __future__ import annotations

import logging
from datetime import datetime, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.core.config import get_settings
from app.core.dependencies import get_attendance_engine, get_graph_client, get_sharepoint_repository
from app.services.sync_service import SyncService

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


async def run_sync_job() -> None:
    graph_client = get_graph_client()
    sync_service = SyncService(
        graph_client=graph_client,
        sharepoint_repository=get_sharepoint_repository(),
        attendance_engine=get_attendance_engine(),
    )

    token = await graph_client.get_application_token()
    result = await sync_service.sync_attendance(token=token)
    logger.info("Attendance sync completed at %s: %s", datetime.now(timezone.utc).isoformat(), result)


def start_scheduler() -> None:
    settings = get_settings()
    if scheduler.running:
        return

    scheduler.add_job(
        run_sync_job,
        IntervalTrigger(minutes=settings.scheduler_interval_minutes),
        id="attendance_sync",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    scheduler.start()
    logger.info("Scheduler started: every %s minutes", settings.scheduler_interval_minutes)


def stop_scheduler() -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped")

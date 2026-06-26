from fastapi import APIRouter, Depends
from datetime import timedelta

from app.core.dependencies import get_graph_client, get_sync_service
from app.core.security import require_roles
from app.models.enums import RoleName
from app.schemas.auth import UserContext
from app.schemas.sync import ManualSyncRequest
from app.services.graph_client import GraphApiClient
from app.services.sync_service import SyncService

router = APIRouter()


@router.post("")
async def trigger_sync(
    payload: ManualSyncRequest,
    current_user: UserContext = Depends(require_roles(RoleName.ADMIN.value, RoleName.MANAGER.value)),
    sync_service: SyncService = Depends(get_sync_service),
    graph_client: GraphApiClient = Depends(get_graph_client),
):
    token = await graph_client.get_application_token()
    if payload.start_date and payload.end_date:
        if payload.end_date < payload.start_date:
            payload.start_date, payload.end_date = payload.end_date, payload.start_date

        max_days = 31
        span_days = (payload.end_date - payload.start_date).days + 1
        if span_days > max_days:
            payload.end_date = payload.start_date + timedelta(days=max_days - 1)

        aggregated = {
            "processed_employees": 0,
            "updated_records": 0,
            "created_records": 0,
            "days": [],
        }
        day = payload.start_date
        while day <= payload.end_date:
            result = await sync_service.sync_attendance(
                token=token,
                target_date=day,
                employee_emails=payload.employee_emails,
            )
            aggregated["processed_employees"] += int(result.get("processed_employees", 0))
            aggregated["updated_records"] += int(result.get("updated_records", 0))
            aggregated["created_records"] += int(result.get("created_records", 0))
            aggregated["days"].append(result)
            day += timedelta(days=1)
        aggregated["run_at"] = aggregated["days"][-1].get("run_at") if aggregated["days"] else None
        return aggregated

    return await sync_service.sync_attendance(
        token=token,
        target_date=payload.target_date,
        employee_emails=payload.employee_emails,
    )

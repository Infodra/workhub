from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query

from app.core.dependencies import get_graph_client, get_sharepoint_repository
from app.core.security import require_roles
from app.models.enums import RoleName
from app.repositories.sharepoint_repository import SharePointRepository
from app.schemas.auth import UserContext
from app.services.graph_client import GraphApiClient

router = APIRouter()


@router.get("")
async def get_reports(
    report_type: str = Query(..., description="daily|monthly|late-login|working-hours|department|meeting-hours|leave|holiday"),
    month: str | None = Query(None, description="YYYY-MM"),
    current_user: UserContext = Depends(require_roles(RoleName.MANAGER.value, RoleName.ADMIN.value)),
    repository: SharePointRepository = Depends(get_sharepoint_repository),
    graph_client: GraphApiClient = Depends(get_graph_client),
):
    token = await graph_client.get_application_token()
    if report_type in {"holiday", "holiday-calendar"}:
        items = await repository.get_holidays(token)
    elif report_type in {"leave", "leave-summary"}:
        items = await repository.get_leaves(token)
    elif report_type in {"daily", "monthly", "late-login", "working-hours", "department", "meeting-hours"}:
        if not month:
            month = datetime.now(timezone.utc).strftime("%Y-%m")
        attendance = await repository.list_items(
            token,
            repository.settings.sp_list_attendance,
            filter_query=f"startswith(fields/AttendanceDate, '{month}')",
            top=999,
        )
        items = [item.get("fields", {}) for item in attendance]

        if report_type == "late-login":
            items = [i for i in items if i.get("AttendanceStatus") == "Late"]
        elif report_type == "meeting-hours":
            items = sorted(items, key=lambda i: float(i.get("MeetingHours", 0) or 0), reverse=True)
        elif report_type == "working-hours":
            items = sorted(items, key=lambda i: float(i.get("WorkingHours", 0) or 0), reverse=True)
    else:
        items = []

    return {
        "report_type": report_type,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "items": [item.get("fields", item) if isinstance(item, dict) else item for item in items],
    }

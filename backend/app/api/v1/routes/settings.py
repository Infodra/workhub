from fastapi import APIRouter, Depends

from app.core.dependencies import get_graph_client, get_sharepoint_repository
from app.core.security import require_roles
from app.models.enums import RoleName
from app.repositories.sharepoint_repository import SharePointRepository
from app.schemas.auth import UserContext
from app.schemas.settings import AttendanceSettings
from app.services.graph_client import GraphApiClient

router = APIRouter()


@router.get("")
async def get_settings(
    current_user: UserContext = Depends(require_roles(RoleName.ADMIN.value, RoleName.MANAGER.value)),
    repository: SharePointRepository = Depends(get_sharepoint_repository),
    graph_client: GraphApiClient = Depends(get_graph_client),
):
    token = await graph_client.get_application_token()
    return await repository.get_settings(token)


@router.put("")
async def update_settings(
    payload: AttendanceSettings,
    current_user: UserContext = Depends(require_roles(RoleName.ADMIN.value)),
    repository: SharePointRepository = Depends(get_sharepoint_repository),
    graph_client: GraphApiClient = Depends(get_graph_client),
):
    token = await graph_client.get_application_token()
    fields = {
        "OfficeStartTime": payload.office_start_time.isoformat(),
        "OfficeEndTime": payload.office_end_time.isoformat(),
        "GracePeriod": payload.grace_period,
        "WorkingHoursPerDay": payload.working_hours_per_day,
        "AttendanceCalculationMethod": payload.attendance_calculation_method,
    }
    return await repository.update_settings(token, fields)

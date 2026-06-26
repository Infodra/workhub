from fastapi import APIRouter, Depends

from app.core.dependencies import get_graph_client, get_sharepoint_repository
from app.core.security import get_current_user, require_roles
from app.models.enums import RoleName
from app.repositories.sharepoint_repository import SharePointRepository
from app.schemas.auth import UserContext
from app.services.graph_client import GraphApiClient

router = APIRouter()


@router.get("")
async def get_employees(
    current_user: UserContext = Depends(require_roles(RoleName.MANAGER.value, RoleName.ADMIN.value)),
    repository: SharePointRepository = Depends(get_sharepoint_repository),
    graph_client: GraphApiClient = Depends(get_graph_client),
):
    token = await graph_client.get_application_token()
    employees = await repository.get_employees(token)
    return [item.get("fields", {}) | {"id": item.get("id")} for item in employees]


@router.get("/me")
async def get_my_profile(
    current_user: UserContext = Depends(get_current_user),
    repository: SharePointRepository = Depends(get_sharepoint_repository),
    graph_client: GraphApiClient = Depends(get_graph_client),
):
    token = await graph_client.get_application_token()
    employees = await repository.get_employees(token)
    for item in employees:
        fields = item.get("fields", {})
        if (fields.get("Email", "").lower() == (current_user.email or "").lower()):
            return fields | {"id": item.get("id")}
    return {}

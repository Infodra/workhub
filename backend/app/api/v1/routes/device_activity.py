from datetime import date

from fastapi import APIRouter, Depends, Query

from app.core.dependencies import get_graph_client, get_sharepoint_repository
from app.core.security import require_roles
from app.models.enums import RoleName
from app.repositories.sharepoint_repository import SharePointRepository
from app.services.device_activity_service import DeviceActivityService
from app.services.graph_client import GraphApiClient

router = APIRouter()
device_activity_service = DeviceActivityService()


@router.get("/device-activity/{employee_email}")
async def get_employee_device_activity(
    employee_email: str,
    activity_date: date = Query(default_factory=date.today),
    _: None = Depends(require_roles(RoleName.ADMIN.value, RoleName.MANAGER.value)),
    repository: SharePointRepository = Depends(get_sharepoint_repository),
    graph_client: GraphApiClient = Depends(get_graph_client),
):
    """Fetch device activity for an employee with company device.
    
    Only available to Admins and Managers.
    Requires the employee to have AssetId and AssetType set to a company device.
    """
    token = await graph_client.get_application_token()
    
    # Get employee record to find device
    employees = await repository.get_employees(token)
    employee_record = None
    for emp_item in employees:
        fields = emp_item.get("fields", {})
        if fields.get("Email", "").lower() == employee_email.lower():
            employee_record = fields
            break
    
    if not employee_record:
        return {"error": "Employee not found", "employee_email": employee_email}
    
    asset_id = employee_record.get("AssetId")
    asset_type = employee_record.get("AssetType")
    
    # Only track if they have a company device
    if not asset_id or not asset_type:
        return {
            "error": "Employee does not have a device assigned",
            "employee_email": employee_email,
            "asset_id": asset_id,
        }
    
    is_company_device = "Company" in asset_type
    if not is_company_device:
        return {
            "error": "Device tracking only available for company-owned devices",
            "asset_type": asset_type,
        }
    
    # Fetch device activity
    activity = await device_activity_service.get_device_activity(
        device_id=asset_id,
        employee_email=employee_email,
        activity_date=activity_date,
    )
    
    # Enrich with employee info
    activity["employee_email"] = employee_email
    activity["asset_id"] = asset_id
    activity["asset_type"] = asset_type
    
    return activity


@router.get("/device-app-usage/{employee_email}")
async def get_device_app_usage(
    employee_email: str,
    activity_date: date = Query(default_factory=date.today),
    _: None = Depends(require_roles(RoleName.ADMIN.value, RoleName.MANAGER.value)),
    repository: SharePointRepository = Depends(get_sharepoint_repository),
    graph_client: GraphApiClient = Depends(get_graph_client),
):
    """Get detailed app usage breakdown for employee's company device."""
    token = await graph_client.get_application_token()
    
    employees = await repository.get_employees(token)
    asset_id = None
    for emp_item in employees:
        fields = emp_item.get("fields", {})
        if fields.get("Email", "").lower() == employee_email.lower():
            asset_id = fields.get("AssetId")
            break
    
    if not asset_id:
        return {"error": "Asset ID not found for employee"}
    
    app_usage = await device_activity_service.get_app_usage(asset_id, activity_date)
    return {
        "employee_email": employee_email,
        "activity_date": activity_date.isoformat(),
        "app_usage": app_usage,
    }


@router.get("/device-idle-periods/{employee_email}")
async def get_device_idle_periods(
    employee_email: str,
    activity_date: date = Query(default_factory=date.today),
    min_idle_minutes: int = Query(15),
    _: None = Depends(require_roles(RoleName.ADMIN.value, RoleName.MANAGER.value)),
    repository: SharePointRepository = Depends(get_sharepoint_repository),
    graph_client: GraphApiClient = Depends(get_graph_client),
):
    """Get idle periods for employee's device (when no activity detected)."""
    token = await graph_client.get_application_token()
    
    employees = await repository.get_employees(token)
    asset_id = None
    for emp_item in employees:
        fields = emp_item.get("fields", {})
        if fields.get("Email", "").lower() == employee_email.lower():
            asset_id = fields.get("AssetId")
            break
    
    if not asset_id:
        return {"error": "Asset ID not found for employee"}
    
    idle_periods = await device_activity_service.get_idle_periods(
        asset_id, activity_date, min_idle_minutes
    )
    return {
        "employee_email": employee_email,
        "activity_date": activity_date.isoformat(),
        "min_idle_minutes": min_idle_minutes,
        "idle_periods": idle_periods,
    }


@router.get("/device-suspicious-activity/{employee_email}")
async def get_suspicious_device_activity(
    employee_email: str,
    activity_date: date = Query(default_factory=date.today),
    _: None = Depends(require_roles(RoleName.ADMIN.value)),
    repository: SharePointRepository = Depends(get_sharepoint_repository),
    graph_client: GraphApiClient = Depends(get_graph_client),
):
    """Detect suspicious activity patterns on company device (Admin only)."""
    token = await graph_client.get_application_token()
    
    employees = await repository.get_employees(token)
    asset_id = None
    for emp_item in employees:
        fields = emp_item.get("fields", {})
        if fields.get("Email", "").lower() == employee_email.lower():
            asset_id = fields.get("AssetId")
            break
    
    if not asset_id:
        return {"error": "Asset ID not found for employee"}
    
    suspicious = await device_activity_service.detect_suspicious_activity(
        asset_id, employee_email, activity_date
    )
    return {
        "employee_email": employee_email,
        "activity_date": activity_date.isoformat(),
        "suspicious_activities": suspicious,
    }

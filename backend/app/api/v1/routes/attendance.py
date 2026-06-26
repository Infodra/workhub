from datetime import date
import logging

from fastapi import APIRouter, Depends, Query

from app.core.dependencies import get_graph_client, get_sharepoint_repository
from app.core.security import get_current_user, require_roles
from app.models.enums import AttendanceStatus
from app.models.enums import RoleName
from app.repositories.sharepoint_repository import SharePointRepository
from app.schemas.auth import UserContext
from app.services.graph_client import GraphApiClient

router = APIRouter()
logger = logging.getLogger(__name__)


async def _resolve_current_user_lookup_id(
    repository: SharePointRepository,
    token: str,
    email: str | None,
    name: str | None,
) -> int | None:
    if email:
        by_email = await repository.get_site_user_lookup_id(token, email)
        if by_email is not None:
            return by_email
    if name:
        by_name = await repository.get_site_user_lookup_id_by_name(token, name)
        if by_name is not None:
            return by_name
        _employee_email, employee_lookup = await repository.resolve_employee_identity_by_name(token, name)
        return employee_lookup
    return None


def _resolve_employee_fields(
    fields: dict,
    employees_by_email: dict[str, dict],
    employees_by_number: dict[str, dict],
    site_users_by_lookup: dict[str, dict],
) -> tuple[str, str]:
    def _clean(value: object) -> str:
        return str(value or "").strip()

    def _looks_like_employee_code(value: str) -> bool:
        compact = value.replace("-", "").replace("_", "")
        return bool(compact) and compact.isdigit()

    employee_value = fields.get("Employee")
    if isinstance(employee_value, str):
        employee_email = employee_value.strip()
    elif isinstance(employee_value, dict):
        employee_email = str(employee_value.get("email") or employee_value.get("EMail") or "").strip()
    else:
        employee_email = ""

    employee_lookup_id = fields.get("EmployeeLookupId")
    if employee_lookup_id in (None, "") and isinstance(employee_value, dict):
        employee_lookup_id = (
            employee_value.get("LookupId")
            or employee_value.get("lookupId")
            or employee_value.get("id")
        )
    employee_item = employees_by_email.get(employee_email.lower()) if employee_email else None

    site_user_fields = {}
    if employee_lookup_id is not None:
        site_user_item = site_users_by_lookup.get(str(employee_lookup_id))
        if site_user_item:
            site_user_fields = site_user_item.get("fields", {})

    employee_fields = employee_item.get("fields", {}) if employee_item else {}
    if not employee_item:
        employee_number = str(fields.get("Title") or fields.get("LinkTitle") or "").strip().lower()
        if employee_number:
            employee_item = employees_by_number.get(employee_number)
            if employee_item:
                employee_fields = employee_item.get("fields", {})
    resolved_email = employee_email or str(employee_fields.get("Email") or site_user_fields.get("EMail") or "")
    preferred_title = _clean(employee_fields.get("Title"))
    if _looks_like_employee_code(preferred_title):
        preferred_title = ""

    resolved_name = (
        _clean(employee_fields.get("EmployeeName"))
        or _clean(employee_fields.get("DisplayName"))
        or _clean(site_user_fields.get("Title"))
        or preferred_title
    )
    if not resolved_name and resolved_email:
        resolved_name = resolved_email.split("@")[0]
    return resolved_email, resolved_name


def _enrich_asset_type(employee_email: str, employees_by_email: dict[str, dict]) -> str | None:
    """Return AssetType from Employee list for a given email (personal vs company device label)."""
    if not employee_email:
        return None
    emp = employees_by_email.get(employee_email.lower())
    if not emp:
        return None
    return emp.get("fields", {}).get("AssetType") or None


def _normalize_attendance_status(fields: dict) -> str:
    status = str(fields.get("AttendanceStatus") or "")
    if status != AttendanceStatus.WEEKEND.value:
        return status

    has_activity = bool(
        fields.get("LoginTime")
        or fields.get("LogoutTime")
        or float(fields.get("WorkingHours", 0) or 0) > 0
        or float(fields.get("MeetingHours", 0) or 0) > 0
    )
    return AttendanceStatus.PRESENT.value if has_activity else AttendanceStatus.ABSENT.value


def _record_score(row: dict) -> tuple[int, float, int, str]:
    total_hours = float(row.get("WorkingHours", 0) or 0) + float(row.get("MeetingHours", 0) or 0)
    last_point = str(row.get("LogoutTime") or row.get("LastActivity") or row.get("LoginTime") or "")
    return (
        1 if row.get("LogoutTime") else 0,
        total_hours,
        1 if row.get("LoginTime") else 0,
        last_point,
    )


def _dedupe_payload_rows(payload: list[dict]) -> list[dict]:
    deduped: dict[tuple[str, str], dict] = {}
    for row in payload:
        date_key = str(row.get("AttendanceDate") or "")[:10]
        employee_key = str(
            row.get("EmployeeEmail")
            or row.get("Employee")
            or row.get("EmployeeName")
            or row.get("EmployeeLookupId")
            or row.get("id")
            or ""
        ).lower()
        key = (date_key, employee_key)
        existing = deduped.get(key)
        if existing is None or _record_score(row) > _record_score(existing):
            deduped[key] = row

    rows = list(deduped.values())
    rows.sort(
        key=lambda item: (
            str(item.get("AttendanceDate") or ""),
            str(item.get("EmployeeName") or item.get("EmployeeEmail") or ""),
        ),
        reverse=True,
    )
    return rows


@router.get("/today")
async def get_today_attendance(
    current_user: UserContext = Depends(get_current_user),
    repository: SharePointRepository = Depends(get_sharepoint_repository),
    graph_client: GraphApiClient = Depends(get_graph_client),
):
    token = await graph_client.get_application_token()
    items = await repository.get_attendance_for_date(token, date.today())
    is_manager_or_admin = (
        RoleName.ADMIN.value in current_user.roles or RoleName.MANAGER.value in current_user.roles
    )

    if not is_manager_or_admin:
        my_email = (current_user.email or "").lower()
        my_name = current_user.name
        if not my_email or not my_name:
            try:
                profile = await graph_client.get_user_profile(current_user.oid)
                my_email = my_email or str(profile.get("mail") or profile.get("userPrincipalName") or "").lower()
                my_name = my_name or str(profile.get("displayName") or "")
            except Exception:  # noqa: BLE001
                pass
        my_lookup_id = await _resolve_current_user_lookup_id(repository, token, my_email or None, my_name)
        if not my_email and my_name:
            resolved_email, _resolved_lookup = await repository.resolve_employee_identity_by_name(token, my_name)
            my_email = (resolved_email or "").lower()
        items = [
            item
            for item in items
            if (
                (my_email and str(item.get("fields", {}).get("Employee", "")).lower() == my_email)
                or (
                    my_lookup_id is not None
                    and str(item.get("fields", {}).get("EmployeeLookupId", "")) == str(my_lookup_id)
                )
            )
        ]
        logger.info(
            "attendance.today employee-filter email=%s name=%s lookup=%s rows=%s",
            my_email,
            my_name,
            my_lookup_id,
            len(items),
        )

    employees = await repository.get_employees(token)
    employees_by_email = {
        str(employee.get("fields", {}).get("Email", "")).lower(): employee for employee in employees
    }
    employees_by_number = {
        str(employee.get("fields", {}).get("Title") or employee.get("fields", {}).get("LinkTitle") or "").strip().lower(): employee
        for employee in employees
        if str(employee.get("fields", {}).get("Title") or employee.get("fields", {}).get("LinkTitle") or "").strip()
    }
    site_users = await repository.list_items(token, "User Information List", top=500)
    site_users_by_lookup = {str(user.get("id")): user for user in site_users}

    payload = []
    for item in items:
        fields = item.get("fields", {})
        employee_email, employee_name = _resolve_employee_fields(fields, employees_by_email, employees_by_number, site_users_by_lookup)
        # Ignore legacy/orphan rows that cannot be mapped to any employee identity.
        if not employee_email and not employee_name:
            continue
        payload.append(
            fields
            | {
                "id": item.get("id"),
                "EmployeeEmail": employee_email,
                "EmployeeName": employee_name,
                "AttendanceStatus": _normalize_attendance_status(fields),
                "AssetType": _enrich_asset_type(employee_email, employees_by_email),
            }
        )
    return _dedupe_payload_rows(payload)


@router.get("/month")
async def get_month_attendance(
    month: str = Query(..., description="Month in YYYY-MM format"),
    employee_email: str | None = None,
    current_user: UserContext = Depends(get_current_user),
    repository: SharePointRepository = Depends(get_sharepoint_repository),
    graph_client: GraphApiClient = Depends(get_graph_client),
):
    token = await graph_client.get_application_token()
    is_manager_or_admin = (
        RoleName.ADMIN.value in current_user.roles or RoleName.MANAGER.value in current_user.roles
    )
    logger.info(
        "attendance.month role-check email=%s roles=%s manager_or_admin=%s month=%s",
        current_user.email,
        current_user.roles,
        is_manager_or_admin,
        month,
    )
    if is_manager_or_admin:
        if employee_email:
            records = await repository.get_employee_attendance_month(token, employee_email, month)
        else:
            items = await repository.list_items(token, repository.settings.sp_list_attendance, top=999)
            records = [
                item
                for item in items
                if str(item.get("fields", {}).get("AttendanceDate", "")).startswith(month)
            ]
        logger.info(
            "attendance.month manager-branch month=%s employee_email=%s rows=%s",
            month,
            employee_email,
            len(records),
        )
    else:
        my_email = (current_user.email or "").lower()
        my_name = current_user.name
        if not my_email or not my_name:
            try:
                profile = await graph_client.get_user_profile(current_user.oid)
                my_email = my_email or str(profile.get("mail") or profile.get("userPrincipalName") or "").lower()
                my_name = my_name or str(profile.get("displayName") or "")
            except Exception:  # noqa: BLE001
                pass
        my_lookup_id = await _resolve_current_user_lookup_id(repository, token, my_email or None, my_name)
        if not my_email and my_name:
            resolved_email, _resolved_lookup = await repository.resolve_employee_identity_by_name(token, my_name)
            my_email = (resolved_email or "").lower()
        if my_email:
            records = await repository.get_employee_attendance_month(token, my_email, month)
        else:
            items = await repository.list_items(token, repository.settings.sp_list_attendance, top=999)
            records = [
                item
                for item in items
                if str(item.get("fields", {}).get("AttendanceDate", "")).startswith(month)
                and (
                    my_lookup_id is not None
                    and str(item.get("fields", {}).get("EmployeeLookupId", "")) == str(my_lookup_id)
                )
            ]
        logger.info(
            "attendance.month employee-filter month=%s email=%s name=%s lookup=%s rows=%s",
            month,
            my_email,
            current_user.name,
            my_lookup_id,
            len(records),
        )

    employees = await repository.get_employees(token)
    employees_by_email = {
        str(employee.get("fields", {}).get("Email", "")).lower(): employee for employee in employees
    }
    employees_by_number = {
        str(employee.get("fields", {}).get("Title") or employee.get("fields", {}).get("LinkTitle") or "").strip().lower(): employee
        for employee in employees
        if str(employee.get("fields", {}).get("Title") or employee.get("fields", {}).get("LinkTitle") or "").strip()
    }
    site_users = await repository.list_items(token, "User Information List", top=500)
    site_users_by_lookup = {str(user.get("id")): user for user in site_users}

    payload = []
    for item in records:
        fields = item.get("fields", {})
        employee_email_resolved, employee_name = _resolve_employee_fields(fields, employees_by_email, employees_by_number, site_users_by_lookup)
        if not employee_email_resolved and not employee_name:
            continue
        payload.append(
            fields
            | {
                "id": item.get("id"),
                "EmployeeEmail": employee_email_resolved,
                "EmployeeName": employee_name,
                "AttendanceStatus": _normalize_attendance_status(fields),
                "AssetType": _enrich_asset_type(employee_email_resolved, employees_by_email),
            }
        )
    return _dedupe_payload_rows(payload)


@router.get("/{employee_email}")
async def get_employee_attendance(
    employee_email: str,
    month: str = Query(..., description="Month in YYYY-MM format"),
    current_user: UserContext = Depends(require_roles(RoleName.MANAGER.value, RoleName.ADMIN.value)),
    repository: SharePointRepository = Depends(get_sharepoint_repository),
    graph_client: GraphApiClient = Depends(get_graph_client),
):
    token = await graph_client.get_application_token()
    records = await repository.get_employee_attendance_month(token, employee_email, month)

    employees = await repository.get_employees(token)
    employees_by_email = {
        str(employee.get("fields", {}).get("Email", "")).lower(): employee for employee in employees
    }
    employees_by_number = {
        str(employee.get("fields", {}).get("Title") or employee.get("fields", {}).get("LinkTitle") or "").strip().lower(): employee
        for employee in employees
        if str(employee.get("fields", {}).get("Title") or employee.get("fields", {}).get("LinkTitle") or "").strip()
    }
    site_users = await repository.list_items(token, "User Information List", top=500)
    site_users_by_lookup = {str(user.get("id")): user for user in site_users}

    payload = []
    for item in records:
        fields = item.get("fields", {})
        employee_email_resolved, employee_name = _resolve_employee_fields(fields, employees_by_email, employees_by_number, site_users_by_lookup)
        if not employee_email_resolved and not employee_name:
            continue
        payload.append(
            fields
            | {
                "id": item.get("id"),
                "EmployeeEmail": employee_email_resolved,
                "EmployeeName": employee_name,
                "AttendanceStatus": _normalize_attendance_status(fields),
                "AssetType": _enrich_asset_type(employee_email_resolved, employees_by_email),
            }
        )
    return _dedupe_payload_rows(payload)

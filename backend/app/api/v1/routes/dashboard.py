from datetime import date
import logging
from collections import defaultdict

from fastapi import APIRouter, Depends

from app.core.dependencies import get_graph_client, get_sharepoint_repository
from app.core.security import get_current_user, require_roles
from app.models.enums import AttendanceStatus, RoleName
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


@router.get("")
async def get_dashboard(
    current_user: UserContext = Depends(get_current_user),
    repository: SharePointRepository = Depends(get_sharepoint_repository),
    graph_client: GraphApiClient = Depends(get_graph_client),
):
    token = await graph_client.get_application_token()
    today_records = await repository.get_attendance_for_date(token, date.today())
    employees = await repository.get_employees(token)
    leaves = await repository.get_leaves(token)
    holidays = await repository.get_holidays(token)
    logger.info(
        "dashboard role-check email=%s roles=%s today_rows=%s",
        current_user.email,
        current_user.roles,
        len(today_records),
    )

    if RoleName.ADMIN.value in current_user.roles:
        audit_logs = await repository.list_items(token, repository.settings.sp_list_audit_logs, top=20)
        return {
            "total_employees": len(employees),
            "todays_attendance": _summary(today_records),
            "synchronization_status": {"last_run": audit_logs[0].get("fields", {}).get("CreatedAt") if audit_logs else None},
            "graph_api_status": "Connected",
            "sharepoint_status": "Connected",
            "attendance_trends": _trend(today_records),
            "audit_logs": [item.get("fields", {}) for item in audit_logs],
        }

    if RoleName.MANAGER.value in current_user.roles:
        employee_departments = {
            item.get("fields", {}).get("Email", "").lower(): item.get("fields", {}).get("Department", "Unknown")
            for item in employees
        }
        month_prefix = date.today().strftime("%Y-%m")
        month_items = await repository.list_items(token, repository.settings.sp_list_attendance, top=999)
        month_records = [
            item for item in month_items if str(item.get("fields", {}).get("AttendanceDate", "")).startswith(month_prefix)
        ]

        total_employees = len(employees)
        active_by_employee: dict[str, bool] = defaultdict(bool)
        for item in month_records:
            fields = item.get("fields", {})
            key = str(fields.get("EmployeeLookupId") or fields.get("Employee") or fields.get("Title") or item.get("id"))
            has_activity = bool(fields.get("LoginTime") or fields.get("LogoutTime") or float(fields.get("WorkingHours", 0) or 0) > 0)
            active_by_employee[key] = active_by_employee[key] or has_activity

        present_employees = sum(1 for value in active_by_employee.values() if value)
        if total_employees:
            present_employees = min(present_employees, total_employees)
        absent_employees = max(total_employees - present_employees, 0)
        attendance_percentage = round((present_employees / total_employees) * 100, 2) if total_employees else 0.0

        logger.info("dashboard manager-branch employees=%s", len(employees))
        return {
            "present_employees": present_employees,
            "absent_employees": absent_employees,
            "late_login": _count_status(month_records, AttendanceStatus.LATE.value),
            "avg_working_hours": _avg_hours(month_records, "WorkingHours"),
            "avg_meeting_hours": _avg_hours(month_records, "MeetingHours"),
            "attendance_percentage": attendance_percentage,
            "monthly_trends": _trend(month_records),
            "department_summary": _department_summary(month_records, employee_departments),
        }

    my_email = current_user.email or ""
    my_name = current_user.name
    if not my_email or not my_name:
        try:
            profile = await graph_client.get_user_profile(current_user.oid)
            my_email = my_email or str(profile.get("mail") or profile.get("userPrincipalName") or "")
            my_name = my_name or str(profile.get("displayName") or "")
        except Exception:  # noqa: BLE001
            pass
    if not my_email and my_name:
        resolved_email, _resolved_lookup = await repository.resolve_employee_identity_by_name(token, my_name)
        my_email = resolved_email or ""
    my_lookup_id = await _resolve_current_user_lookup_id(repository, token, my_email or None, my_name)
    mine = [
        r
        for r in today_records
        if (
            (my_email and r.get("fields", {}).get("Employee", "").lower() == my_email.lower())
            or (
                my_lookup_id is not None
                and str(r.get("fields", {}).get("EmployeeLookupId", "")) == str(my_lookup_id)
            )
        )
    ]
    logger.info(
        "dashboard employee-filter email=%s name=%s lookup=%s today_rows=%s matched=%s",
        my_email,
        my_name,
        my_lookup_id,
        len(today_records),
        len(mine),
    )
    current = mine[0].get("fields", {}) if mine else {}
    return {
        "todays_login": current.get("LoginTime"),
        "todays_logout": current.get("LogoutTime"),
        "working_hours": current.get("WorkingHours", 0),
        "meeting_hours": current.get("MeetingHours", 0),
        "attendance_status": current.get("AttendanceStatus", AttendanceStatus.ABSENT.value),
        "monthly_attendance": 0,
        "leave_balance": 0,
        "upcoming_holidays": [item.get("fields", {}) for item in holidays[:5]],
        "recent_announcements": [],
    }


def _count_status(records: list[dict], status: str) -> int:
    return sum(1 for item in records if item.get("fields", {}).get("AttendanceStatus") == status)


def _avg_hours(records: list[dict], key: str) -> float:
    if not records:
        return 0.0
    values = [float(item.get("fields", {}).get(key, 0) or 0) for item in records]
    return round(sum(values) / max(len(values), 1), 2)


def _attendance_percentage(records: list[dict]) -> float:
    if not records:
        return 0.0
    present_like = 0
    for item in records:
        status = item.get("fields", {}).get("AttendanceStatus")
        if status in {AttendanceStatus.PRESENT.value, AttendanceStatus.LATE.value, AttendanceStatus.HALF_DAY.value}:
            present_like += 1
    return round((present_like / len(records)) * 100, 2)


def _summary(records: list[dict]) -> dict:
    return {
        "present": _count_status(records, AttendanceStatus.PRESENT.value),
        "absent": _count_status(records, AttendanceStatus.ABSENT.value),
        "late": _count_status(records, AttendanceStatus.LATE.value),
        "half_day": _count_status(records, AttendanceStatus.HALF_DAY.value),
    }


def _trend(records: list[dict]) -> list[dict]:
    return [
        {
            "date": item.get("fields", {}).get("AttendanceDate"),
            "working_hours": item.get("fields", {}).get("WorkingHours", 0),
            "meeting_hours": item.get("fields", {}).get("MeetingHours", 0),
        }
        for item in records
    ]


def _department_summary(records: list[dict], email_department_map: dict[str, str]) -> list[dict]:
    grouped: dict[str, list[dict]] = {}
    for item in records:
        email = item.get("fields", {}).get("Employee", "").lower()
        department = email_department_map.get(email, "Unknown")
        grouped.setdefault(department, []).append(item)

    return [
        {
            "department": department,
            "count": len(items),
            "attendance": _attendance_percentage(items),
        }
        for department, items in grouped.items()
    ]

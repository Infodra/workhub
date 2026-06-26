from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from typing import Any

from app.repositories.sharepoint_repository import SharePointRepository
from app.services.attendance_engine import AttendanceEngine
from app.services.graph_client import GraphApiClient

logger = logging.getLogger(__name__)


class SyncService:
    def __init__(
        self,
        graph_client: GraphApiClient,
        sharepoint_repository: SharePointRepository,
        attendance_engine: AttendanceEngine,
    ) -> None:
        self.graph_client = graph_client
        self.sharepoint_repository = sharepoint_repository
        self.attendance_engine = attendance_engine

    async def sync_attendance(
        self,
        token: str,
        target_date: date | None = None,
        employee_emails: list[str] | None = None,
    ) -> dict[str, Any]:
        day = target_date or datetime.now(timezone.utc).date()

        settings = await self.sharepoint_repository.get_settings(token)
        employees = await self.sharepoint_repository.get_employees(token)
        holidays = await self.sharepoint_repository.get_holidays(token)
        graph_users = await self.graph_client.list_users()

        processed_employees = 0
        created_records = 0
        updated_records = 0

        for employee_item in employees:
            fields = employee_item.get("fields", {})
            email = fields.get("Email")
            if not email:
                continue
            if employee_emails and email not in employee_emails:
                continue
            employee_number = str(fields.get("Title") or fields.get("LinkTitle") or "").strip()
            device_type: str | None = fields.get("AssetType") or None

            lookup_id: int | None = None

            graph_user = {
                # SP list column is MicrosoftUserId; fall back to email if not set
                "id": fields.get("MicrosoftUserId") or fields.get("AzureUserId") or email,
                "mail": email,
                "userPrincipalName": email,
            }

            try:
                match = next(
                    (
                        u
                        for u in graph_users
                        if (u.get("mail") or u.get("userPrincipalName", "")).lower() == email.lower()
                    ),
                    None,
                )
                if match:
                    graph_user = match

                timeline = await self.graph_client.get_user_activity_timeline(
                    graph_user,
                    datetime.combine(day, datetime.min.time(), tzinfo=timezone.utc),
                    device_type=device_type,
                )
                graph_user_ref = graph_user.get("userPrincipalName") or graph_user.get("mail") or graph_user["id"]
                calendar_events: list[dict[str, Any]] = []
                try:
                    calendar_events = await self.graph_client.get_user_calendar(
                        graph_user_ref,
                        datetime.combine(day, datetime.min.time(), tzinfo=timezone.utc),
                    )
                except Exception as exc:  # noqa: BLE001
                    logger.warning("Skipping calendar events in sync for %s due to permission/API error: %s", email, exc)
                leaves = await self.sharepoint_repository.get_leaves(token, employee_email=email)

                record = self.attendance_engine.calculate(
                    attendance_date=day,
                    activities=timeline,
                    calendar_events=calendar_events,
                    settings=settings,
                    holidays=holidays,
                    leaves=leaves,
                )
                record["Employee"] = email
                if employee_number:
                    record["Title"] = employee_number
                lookup_id = await self.sharepoint_repository.get_site_user_lookup_id(token, email)
                if lookup_id is not None:
                    record["EmployeeLookupId"] = lookup_id

                mode, _item_id = await self.sharepoint_repository.upsert_attendance(token, record)
                if mode == "created":
                    created_records += 1
                else:
                    updated_records += 1

                logs = [
                    {
                        "Employee": email,
                        "ActivityType": item["activity_type"],
                        "ActivityTime": item["activity_time"],
                        "Source": item["source"],
                        "Details": item.get("details"),
                    }
                    for item in timeline
                ]
                if lookup_id is not None:
                    for entry in logs:
                        entry["EmployeeLookupId"] = lookup_id
                if logs:
                    await self.sharepoint_repository.create_activity_logs(token, logs)

                audit_fields = {
                    "Action": "SyncCompleted",
                    "Entity": "Attendance",
                    "Details": (
                        f"{email}: {mode}; status={record.get('AttendanceStatus')}; "
                        f"working_hours={record.get('WorkingHours', 0)}"
                    ),
                    "CreatedAt": datetime.now(timezone.utc).isoformat(),
                    "Employee": email,
                }
                if lookup_id is not None:
                    audit_fields["EmployeeLookupId"] = lookup_id
                await self.sharepoint_repository.add_audit_log(token, audit_fields)

                processed_employees += 1
            except Exception as exc:
                logger.error("Sync failed for %s on %s: %s: %s", email, day, type(exc).__name__, exc)
                audit_fields = {
                    "Action": "SyncFailed",
                    "Entity": "Attendance",
                    "Details": f"{email}: {str(exc)}",
                    "CreatedAt": datetime.now(timezone.utc).isoformat(),
                    "Employee": email,
                }
                if lookup_id is None:
                    lookup_id = await self.sharepoint_repository.get_site_user_lookup_id(token, email)
                if lookup_id is not None:
                    audit_fields["EmployeeLookupId"] = lookup_id
                await self.sharepoint_repository.add_audit_log(
                    token,
                    audit_fields,
                )

        result = {
            "processed_employees": processed_employees,
            "updated_records": updated_records,
            "created_records": created_records,
            "run_at": datetime.now(timezone.utc).isoformat(),
        }
        return result

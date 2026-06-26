from __future__ import annotations

import logging
from datetime import date
from typing import Any

import httpx

from app.core.config import get_settings

GRAPH_BASE_URL = "https://graph.microsoft.com/v1.0"
logger = logging.getLogger(__name__)


class SharePointRepository:
    def __init__(self) -> None:
        self.settings = get_settings()

    async def _request(
        self,
        token: str,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.request(
                method,
                f"{GRAPH_BASE_URL}{path}",
                params=params,
                json=json,
                headers=headers,
            )
            response.raise_for_status()
            if response.status_code == 204:
                return {}
            return response.json()

    async def list_items(
        self,
        token: str,
        list_name: str,
        filter_query: str | None = None,
        top: int = 500,
    ) -> list[dict[str, Any]]:
        params: dict[str, str] = {"expand": "fields", "$top": str(top)}
        if filter_query:
            params["$filter"] = filter_query
        data = await self._request(
            token,
            "GET",
            f"/sites/{self.settings.sharepoint_site_id}/lists/{list_name}/items",
            params=params,
        )
        return data.get("value", [])

    async def create_item(self, token: str, list_name: str, fields: dict[str, Any]) -> dict[str, Any]:
        return await self._request(
            token,
            "POST",
            f"/sites/{self.settings.sharepoint_site_id}/lists/{list_name}/items",
            json={"fields": fields},
        )

    async def update_item(self, token: str, list_name: str, item_id: str, fields: dict[str, Any]) -> dict[str, Any]:
        return await self._request(
            token,
            "PATCH",
            f"/sites/{self.settings.sharepoint_site_id}/lists/{list_name}/items/{item_id}/fields",
            json=fields,
        )

    async def get_employees(self, token: str) -> list[dict[str, Any]]:
        return await self.list_items(token, self.settings.sp_list_employees)

    async def get_attendance_for_date(self, token: str, attendance_date: date) -> list[dict[str, Any]]:
        items = await self.list_items(token, self.settings.sp_list_attendance, top=999)
        target = attendance_date.isoformat()
        return [
            item
            for item in items
            if str(item.get("fields", {}).get("AttendanceDate", "")).startswith(target)
        ]

    async def get_employee_attendance_month(
        self,
        token: str,
        employee_email: str,
        month_prefix: str,
    ) -> list[dict[str, Any]]:
        items = await self.list_items(token, self.settings.sp_list_attendance, top=999)
        email = employee_email.lower()
        lookup_id = await self.get_site_user_lookup_id(token, employee_email)
        return [
            item
            for item in items
            if str(item.get("fields", {}).get("AttendanceDate", "")).startswith(month_prefix)
            and (
                str(item.get("fields", {}).get("Employee", "")).lower() == email
                or (lookup_id is not None and str(item.get("fields", {}).get("EmployeeLookupId", "")) == str(lookup_id))
            )
        ]

    async def upsert_attendance(self, token: str, record: dict[str, Any]) -> tuple[str, str]:
        employee = record["Employee"]
        attendance_date = record["AttendanceDate"]
        employee_lookup_id = record.get("EmployeeLookupId")
        items = await self.list_items(token, self.settings.sp_list_attendance, top=999)
        existing = [
            item
            for item in items
            if (
                str(item.get("fields", {}).get("Employee", "")).lower() == employee.lower()
                or (
                    employee_lookup_id is not None
                    and str(item.get("fields", {}).get("EmployeeLookupId", "")) == str(employee_lookup_id)
                )
            )
            and str(item.get("fields", {}).get("AttendanceDate", "")).startswith(attendance_date)
        ][:1]

        if existing:
            item_id = existing[0]["id"]
            await self.update_item(token, self.settings.sp_list_attendance, item_id, record)
            return "updated", item_id

        created = await self.create_item(token, self.settings.sp_list_attendance, record)
        return "created", created.get("id", "")

    async def get_site_user_lookup_id(self, token: str, email: str) -> int | None:
        """Resolve a SharePoint site user lookup id from User Information List using email."""
        try:
            items = await self.list_items(token, "User Information List", top=500)
            target = email.lower()
            match = next(
                (
                    item
                    for item in items
                    if str(item.get("fields", {}).get("EMail", "")).lower() == target
                ),
                None,
            )
            if not match:
                return None
            return int(match.get("id"))
        except Exception as exc:  # noqa: BLE001
            logger.warning("Unable to resolve SharePoint lookup id for %s: %s", email, exc)
            return None

    async def get_site_user_lookup_id_by_name(self, token: str, name: str) -> int | None:
        """Resolve a SharePoint site user lookup id from User Information List using display name."""
        try:
            if not name:
                return None
            items = await self.list_items(token, "User Information List", top=500)
            target = name.strip().lower()
            target_normalized = "".join(ch for ch in target if ch.isalnum())

            def _normalized(value: str) -> str:
                return "".join(ch for ch in value.strip().lower() if ch.isalnum())

            match = next(
                (
                    item
                    for item in items
                    if (
                        str(item.get("fields", {}).get("Title", "")).strip().lower() == target
                        or _normalized(str(item.get("fields", {}).get("Title", ""))) == target_normalized
                        or (
                            target_normalized
                            and target_normalized in _normalized(str(item.get("fields", {}).get("Title", "")))
                        )
                    )
                ),
                None,
            )
            if not match:
                return None
            return int(match.get("id"))
        except Exception as exc:  # noqa: BLE001
            logger.warning("Unable to resolve SharePoint lookup id for name %s: %s", name, exc)
            return None

    async def resolve_employee_identity_by_name(self, token: str, name: str) -> tuple[str | None, int | None]:
        """Resolve employee email and site user lookup id using Employees list name matching."""
        if not name:
            return None, None

        def _normalized(value: str) -> str:
            return "".join(ch for ch in value.strip().lower() if ch.isalnum())

        target = _normalized(name)
        if not target:
            return None, None

        try:
            employees = await self.get_employees(token)
            match = next(
                (
                    item
                    for item in employees
                    if (
                        _normalized(str(item.get("fields", {}).get("Name", ""))) == target
                        or (
                            target
                            and target in _normalized(str(item.get("fields", {}).get("Name", "")))
                        )
                    )
                ),
                None,
            )
            if not match:
                return None, None

            fields = match.get("fields", {})
            email = str(fields.get("Email") or "").strip() or None
            lookup_raw = fields.get("UserIDLookupId")
            lookup_id = int(lookup_raw) if lookup_raw not in (None, "") else None

            if lookup_id is None and email:
                lookup_id = await self.get_site_user_lookup_id(token, email)

            return email, lookup_id
        except Exception as exc:  # noqa: BLE001
            logger.warning("Unable to resolve employee identity by name %s: %s", name, exc)
            return None, None

    async def create_activity_logs(self, token: str, logs: list[dict[str, Any]]) -> int:
        count = 0
        lookup_cache: dict[str, int | None] = {}
        for entry in logs:
            employee_value = str(entry.get("Employee") or "").strip().lower()
            if employee_value and entry.get("EmployeeLookupId") in (None, ""):
                if employee_value not in lookup_cache:
                    lookup_cache[employee_value] = await self.get_site_user_lookup_id(token, employee_value)
                cached_lookup_id = lookup_cache[employee_value]
                if cached_lookup_id is not None:
                    entry["EmployeeLookupId"] = cached_lookup_id
            await self.create_item(token, self.settings.sp_list_activity_logs, entry)
            count += 1
        return count

    async def get_settings(self, token: str) -> dict[str, Any]:
        """Read all key-value rows from the Settings list and return as a flat dict.
        Falls back to sensible defaults when the list is empty."""
        defaults: dict[str, Any] = {
            "OfficeStartTime": "09:00:00",
            "OfficeEndTime": "18:00:00",
            "GracePeriod": 15,
            "WorkingHoursPerDay": 8.0,
            "AttendanceCalculationMethod": "ActivityBased",
        }
        items = await self.list_items(token, self.settings.sp_list_settings, top=200)
        if not items:
            return defaults
        result: dict[str, Any] = dict(defaults)
        for item in items:
            fields = item.get("fields", {})
            name = fields.get("SettingsName")
            value = fields.get("SettingValue")
            if name:
                result[name] = value
        return result

    async def update_settings(self, token: str, fields: dict[str, Any]) -> dict[str, Any]:
        """Upsert each key as an individual key-value row in the Settings list."""
        existing_items = await self.list_items(token, self.settings.sp_list_settings, top=200)
        existing_map: dict[str, str] = {
            item.get("fields", {}).get("SettingsName", ""): item["id"]
            for item in existing_items
            if item.get("fields", {}).get("SettingsName")
        }
        for name, value in fields.items():
            row = {"SettingsName": name, "SettingValue": str(value)}
            if name in existing_map:
                await self.update_item(token, self.settings.sp_list_settings, existing_map[name], row)
            else:
                await self.create_item(token, self.settings.sp_list_settings, row)
        return fields

    async def get_holidays(self, token: str, location: str | None = None) -> list[dict[str, Any]]:
        # SharePoint list uses 'State' column for location/region filtering
        if location:
            filter_query = f"fields/State eq '{location}'"
            return await self.list_items(token, self.settings.sp_list_holidays, filter_query=filter_query, top=500)
        return await self.list_items(token, self.settings.sp_list_holidays, top=500)

    async def get_leaves(self, token: str, employee_email: str | None = None) -> list[dict[str, Any]]:
        items = await self.list_items(token, self.settings.sp_list_leave, top=500)
        if not employee_email:
            return items

        email = employee_email.lower()
        return [
            item
            for item in items
            if str(item.get("fields", {}).get("Employee", "")).lower() == email
        ]

    async def add_audit_log(self, token: str, fields: dict[str, Any]) -> None:
        try:
            employee_value = str(fields.get("Employee") or "").strip().lower()
            if employee_value and fields.get("EmployeeLookupId") in (None, ""):
                lookup_id = await self.get_site_user_lookup_id(token, employee_value)
                if lookup_id is not None:
                    fields["EmployeeLookupId"] = lookup_id
            await self.create_item(token, self.settings.sp_list_audit_logs, fields)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Skipping audit log write due to permission/API error: %s", exc)

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
import msal

from app.core.config import get_settings

GRAPH_BASE_URL = "https://graph.microsoft.com/v1.0"
logger = logging.getLogger(__name__)

# Error codes returned when the tenant lacks a required licence (not a misconfiguration).
_PREMIUM_LICENSE_CODES = {
    "Authentication_RequestFromNonPremiumTenantOrB2CTenant",
    "InvalidLicenseForService",
    "RequestNotApplicableToTargetTenant",
    "BadRequest",  # Intune returns BadRequest when not provisioned
}

# Module-level set so the one-time licence warning survives across GraphApiClient instances.
_LICENCE_WARNED: set[str] = set()


class GraphApiClient:
    def __init__(self) -> None:
        self.settings = get_settings()
        self._token_cache: dict[str, Any] = {}
        # Track which premium-gated features have already logged a one-time notice
        self._license_warned: set[str] = set()

    def _is_license_error(self, exc: Exception) -> bool:
        """Return True when an httpx error is caused by a missing licence, not misconfiguration."""
        if not isinstance(exc, httpx.HTTPStatusError):
            return False
        try:
            text = exc.response.text
            return (
                "NonPremiumTenant" in text
                or "premium license" in text.lower()
                or "not applicable to target tenant" in text.lower()
                or "RequestNotApplicableToTargetTenant" in text
                or "InvalidLicenseForService" in text
            )
        except Exception:  # noqa: BLE001
            return False

    def _warn_license_once(self, feature: str, detail: str) -> None:
        """Log a licence-missing warning exactly once per feature per process."""
        if feature not in _LICENCE_WARNED:
            _LICENCE_WARNED.add(feature)
            logger.warning(
                "[LICENCE] %s is unavailable for this tenant (licence not provisioned). "
                "Detail: %s",
                feature,
                detail,
            )

    def _build_msal_client(self) -> msal.ConfidentialClientApplication:
        return msal.ConfidentialClientApplication(
            client_id=self.settings.client_id,
            client_credential=self.settings.client_secret,
            authority=self.settings.authority,
        )

    async def _get_app_token(self) -> str:
        now = datetime.now(tz=timezone.utc).timestamp()
        cached = self._token_cache.get("app")
        if cached and cached["expires_at"] > now + 60:
            return cached["access_token"]

        app = self._build_msal_client()
        token_result = app.acquire_token_for_client(scopes=["https://graph.microsoft.com/.default"])
        access_token = token_result.get("access_token")
        if not access_token:
            raise RuntimeError(f"Unable to acquire Graph token: {token_result}")

        expires_in = int(token_result.get("expires_in", 3600))
        self._token_cache["app"] = {"access_token": access_token, "expires_at": now + expires_in}
        return access_token

    async def get_application_token(self) -> str:
        return await self._get_app_token()

    async def _request(self, method: str, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        token = await self._get_app_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.request(method, f"{GRAPH_BASE_URL}{path}", headers=headers, params=params)
            response.raise_for_status()
            if response.status_code == 204:
                return {}
            return response.json()

    async def list_users(self) -> list[dict[str, Any]]:
        data = await self._request(
            "GET",
            "/users",
            params={
                "$select": "id,displayName,mail,userPrincipalName,department,jobTitle,manager,officeLocation",
                "$top": "999",
            },
        )
        return data.get("value", [])

    async def get_user_profile(self, user_id: str) -> dict[str, Any]:
        return await self._request("GET", f"/users/{user_id}")

    async def get_user_presence(self, user_id: str) -> dict[str, Any]:
        return await self._request("GET", f"/users/{user_id}/presence")

    async def get_user_teams_activity(self, user_id: str) -> dict[str, Any]:
        return await self.get_user_presence(user_id)

    async def get_user_calendar(self, user_id: str, day: datetime) -> list[dict[str, Any]]:
        start = day.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1)
        data = await self._request(
            "GET",
            f"/users/{user_id}/calendarView",
            params={
                "startDateTime": start.isoformat(),
                "endDateTime": end.isoformat(),
                "$select": "subject,start,end,isCancelled,isAllDay",
                "$top": "200",
            },
        )
        return data.get("value", [])

    async def get_user_sign_ins(self, email: str, day: datetime) -> list[dict[str, Any]]:
        start = day.replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=timezone.utc)
        end = start + timedelta(days=1)
        filter_query = (
            f"userPrincipalName eq '{email}' and "
            f"createdDateTime ge {start.isoformat()} and "
            f"createdDateTime lt {end.isoformat()}"
        )
        data = await self._request(
            "GET",
            "/auditLogs/signIns",
            params={"$filter": filter_query, "$top": "200"},
        )
        return data.get("value", [])

    async def get_user_outlook_activity(self, user_id: str, day: datetime) -> list[dict[str, Any]]:
        start = day.replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=timezone.utc)
        end = start + timedelta(days=1)
        data = await self._request(
            "GET",
            f"/users/{user_id}/messages",
            params={
                "$select": "receivedDateTime,sentDateTime,lastModifiedDateTime,subject",
                "$filter": f"lastModifiedDateTime ge {start.isoformat()} and lastModifiedDateTime lt {end.isoformat()}",
                "$orderby": "lastModifiedDateTime asc",
                "$top": "200",
            },
        )
        return data.get("value", [])

    async def get_user_sent_mail_activity(self, user_id: str, day: datetime) -> list[dict[str, Any]]:
        start = day.replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=timezone.utc)
        end = start + timedelta(days=1)
        data = await self._request(
            "GET",
            f"/users/{user_id}/mailFolders/sentitems/messages",
            params={
                "$select": "sentDateTime,lastModifiedDateTime,subject",
                "$filter": f"lastModifiedDateTime ge {start.isoformat()} and lastModifiedDateTime lt {end.isoformat()}",
                "$orderby": "lastModifiedDateTime asc",
                "$top": "200",
            },
        )
        return data.get("value", [])

    async def get_user_sharepoint_activity(self, user_id: str) -> list[dict[str, Any]]:
        data = await self._request(
            "GET",
            f"/users/{user_id}/drive/recent",
            params={"$top": "50"},
        )
        return data.get("value", [])

    async def get_user_onedrive_activity(self, user_id: str) -> list[dict[str, Any]]:
        data = await self._request(
            "GET",
            f"/users/{user_id}/drive/root/children",
            params={"$top": "20", "$select": "name,lastModifiedDateTime"},
        )
        return data.get("value", [])

    async def get_user_managed_devices(self, email: str) -> list[dict[str, Any]]:
        """Get Intune managed devices for a user (requires DeviceManagementManagedDevices.Read.All)."""
        data = await self._request(
            "GET",
            "/deviceManagement/managedDevices",
            params={
                "$filter": f"userPrincipalName eq '{email}'",
                "$select": "id,deviceName,operatingSystem,lastSyncDateTime,complianceState,serialNumber,managementState",
            },
        )
        return data.get("value", [])

    async def get_organization(self) -> list[dict[str, Any]]:
        data = await self._request("GET", "/organization")
        return data.get("value", [])

    async def get_groups(self) -> list[dict[str, Any]]:
        data = await self._request("GET", "/groups", params={"$top": "200"})
        return data.get("value", [])

    async def get_user_activity_timeline(self, user: dict[str, Any], day: datetime, device_type: str | None = None) -> list[dict[str, Any]]:
        user_ref = user.get("userPrincipalName") or user.get("mail") or user["id"]
        email = user.get("mail") or user.get("userPrincipalName")
        timeline: list[dict[str, Any]] = []
        day_start = day.replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=timezone.utc)
        day_end = day_start + timedelta(days=1)

        def _parse_iso(value: str | None) -> datetime | None:
            if not value:
                return None
            try:
                parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=timezone.utc)
                return parsed.astimezone(timezone.utc)
            except ValueError:
                return None

        def _in_day_window(value: str | None) -> bool:
            parsed = _parse_iso(value)
            if parsed is None:
                return False
            return day_start <= parsed < day_end

        sign_ins: list[dict[str, Any]] = []
        try:
            sign_ins = await self.get_user_sign_ins(email, day)
        except httpx.HTTPStatusError as exc:
            if self._is_license_error(exc):
                self._warn_license_once(
                    "auditLogs/signIns",
                    "Requires Azure AD Premium P1/P2. Upgrade at aka.ms/aadlicensing.",
                )
            else:
                logger.warning("Skipping sign-ins for %s due to permission/API error: %s", email, exc)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Skipping sign-ins for %s due to error: %s", email, exc)
        for item in sign_ins:
            timestamp = item.get("createdDateTime")
            if _in_day_window(timestamp):
                timeline.append(
                    {
                        "activity_type": "SignIn",
                        "activity_time": timestamp,
                        "source": "Microsoft Sign In",
                        "details": item.get("appDisplayName") or "Sign-in",
                    }
                )

        calendar_events: list[dict[str, Any]] = []
        try:
            calendar_events = await self.get_user_calendar(user_ref, day)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Skipping calendar for %s due to permission/API error: %s", email, exc)
        for item in calendar_events:
            start = item.get("start", {}).get("dateTime")
            end = item.get("end", {}).get("dateTime")
            if _in_day_window(start):
                timeline.append(
                    {
                        "activity_type": "Calendar",
                        "activity_time": start,
                        "source": "Calendar Activity",
                        "details": item.get("subject") or "Meeting",
                    }
                )
            if _in_day_window(end):
                timeline.append(
                    {
                        "activity_type": "CalendarEnd",
                        "activity_time": end,
                        "source": "Calendar Activity",
                        "details": item.get("subject") or "Meeting end",
                    }
                )

        messages: list[dict[str, Any]] = []
        try:
            messages = await self.get_user_outlook_activity(user_ref, day)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Skipping outlook activity for %s due to permission/API error: %s", email, exc)
        for item in messages:
            timestamp = item.get("lastModifiedDateTime") or item.get("sentDateTime") or item.get("receivedDateTime")
            if _in_day_window(timestamp):
                timeline.append(
                    {
                        "activity_type": "Outlook",
                        "activity_time": timestamp,
                        "source": "Outlook Activity",
                        "details": item.get("subject") or "Mail activity",
                    }
                )

        sent_messages: list[dict[str, Any]] = []
        try:
            sent_messages = await self.get_user_sent_mail_activity(user_ref, day)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Skipping sent mail activity for %s due to permission/API error: %s", email, exc)
        for item in sent_messages:
            timestamp = item.get("lastModifiedDateTime") or item.get("sentDateTime")
            if _in_day_window(timestamp):
                timeline.append(
                    {
                        "activity_type": "Outlook",
                        "activity_time": timestamp,
                        "source": "Sent Mail Activity",
                        "details": item.get("subject") or "Sent mail",
                    }
                )

        presence: dict[str, Any] = {}
        try:
            presence = await self.get_user_presence(user_ref)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Skipping presence for %s due to permission/API error: %s", email, exc)
        availability = presence.get("availability")
        today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        if availability and day_start == today_start:
            timeline.append(
                {
                    "activity_type": "TeamsPresence",
                    "activity_time": datetime.now(timezone.utc).isoformat(),
                    "source": "Teams Sign In",
                    "details": availability,
                }
            )

        sp_items: list[dict[str, Any]] = []
        try:
            sp_items = await self.get_user_sharepoint_activity(user_ref)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Skipping SharePoint activity for %s due to permission/API error: %s", email, exc)
        for item in sp_items:
            remote_item = item.get("remoteItem", {})
            file_meta = remote_item.get("fileSystemInfo", {})
            timestamp = file_meta.get("lastModifiedDateTime") or item.get("lastModifiedDateTime")
            if _in_day_window(timestamp):
                timeline.append(
                    {
                        "activity_type": "SharePoint",
                        "activity_time": timestamp,
                        "source": "SharePoint Activity",
                        "details": remote_item.get("name") or "SharePoint file",
                    }
                )

        onedrive_items: list[dict[str, Any]] = []
        try:
            onedrive_items = await self.get_user_onedrive_activity(user_ref)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Skipping OneDrive activity for %s due to permission/API error: %s", email, exc)
        for item in onedrive_items:
            timestamp = item.get("lastModifiedDateTime")
            if _in_day_window(timestamp):
                timeline.append(
                    {
                        "activity_type": "OneDrive",
                        "activity_time": timestamp,
                        "source": "OneDrive Activity",
                        "details": item.get("name") or "OneDrive file",
                    }
                )

        # Company device activity via Intune (employees with company laptop/desktop)
        if device_type and "company" in device_type.lower():
            intune_devices: list[dict[str, Any]] = []
            try:
                intune_devices = await self.get_user_managed_devices(email)
            except httpx.HTTPStatusError as exc:
                if self._is_license_error(exc):
                    self._warn_license_once(
                        "deviceManagement/managedDevices",
                        "Requires Microsoft Intune licence. Details: aka.ms/intunesetup.",
                    )
                else:
                    logger.warning("Skipping Intune devices for %s due to permission/API error: %s", email, exc)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Skipping Intune devices for %s due to error: %s", email, exc)
            for device in intune_devices:
                last_sync = device.get("lastSyncDateTime")
                if _in_day_window(last_sync):
                    timeline.append(
                        {
                            "activity_type": "CompanyDevice",
                            "activity_time": last_sync,
                            "source": "Company Device (Intune)",
                            "details": f"{device.get('operatingSystem', '')} - {device.get('deviceName', '')} [{device.get('complianceState', '')}]",
                        }
                    )

        return sorted(timeline, key=lambda x: x["activity_time"])

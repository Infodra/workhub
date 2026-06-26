from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Any

from dateutil import parser as date_parser

from app.models.enums import AttendanceStatus


class AttendanceEngine:
    _ACTIVITY_HOURS_GAP_MINUTES = 90
    # Activity types that confirm real user presence and anchor a time session.
    # Calendar/CalendarEnd = meetings attended, Outlook = email read/sent — both user-initiated.
    # SharePoint and OneDrive are background sync processes and excluded intentionally.
    # SignIn and Intune data are optional (require Premium/Intune licences).
    _ANCHOR_ACTIVITY_TYPES = {"SignIn", "TeamsPresence", "CompanyDevice", "Calendar", "CalendarEnd", "Outlook"}

    def _build_reason(
        self,
        activities: list[dict[str, Any]],
        meeting_hours: float,
    ) -> str | None:
        if not activities:
            return "No cloud activity"

        if len(activities) == 1:
            activity_type = activities[0].get("activity_type")
            if activity_type == "TeamsPresence":
                return "Teams presence only"
            if activity_type == "CompanyDevice":
                return "Company device active only"
            return "Single activity only"

        activity_types = {str(item.get("activity_type") or "") for item in activities}
        if activity_types.issubset({"Calendar", "CalendarEnd"}):
            return "Meeting activity only"
        if activity_types.issubset({"Outlook"}):
            return "Email activity only"
        if activity_types.issubset({"CompanyDevice"}):
            return "Company device active (Intune)"
        if "CompanyDevice" in activity_types:
            return "Company device + cloud activity"
        if "SignIn" in activity_types:
            return "Computed from sign-in and cloud activity"
        if meeting_hours > 0:
            return "Computed from meetings and M365 activity"

        return "Computed from M365 activity (email/calendar)"

    def _hours_from_seconds(self, total_seconds: float) -> float:
        if total_seconds <= 0:
            return 0.0
        hours = round(total_seconds / 3600, 2)
        return max(hours, 0.01)

    def _parse_time(self, value: str, fallback: time) -> time:
        if not value:
            return fallback
        try:
            return datetime.strptime(value, "%H:%M:%S").time()
        except ValueError:
            try:
                return datetime.strptime(value, "%H:%M").time()
            except ValueError:
                return fallback

    def _is_holiday(self, day: date, holidays: list[dict[str, Any]]) -> bool:
        for holiday in holidays:
            holiday_date = holiday.get("fields", {}).get("HolidayDate")
            if holiday_date and holiday_date.startswith(day.isoformat()):
                return True
        return False

    def _is_on_leave(self, day: date, leaves: list[dict[str, Any]]) -> bool:
        for leave in leaves:
            fields = leave.get("fields", {})
            start = fields.get("StartDate")
            end = fields.get("EndDate")
            status = fields.get("Status")
            if status != "Approved" or not start or not end:
                continue
            start_date = date.fromisoformat(start[:10])
            end_date = date.fromisoformat(end[:10])
            if start_date <= day <= end_date:
                return True
        return False

    def calculate(
        self,
        attendance_date: date,
        activities: list[dict[str, Any]],
        calendar_events: list[dict[str, Any]],
        settings: dict[str, Any],
        holidays: list[dict[str, Any]],
        leaves: list[dict[str, Any]],
    ) -> dict[str, Any]:
        sorted_activities = sorted(
            [a for a in activities if a.get("activity_time")],
            key=lambda a: a["activity_time"],
        )
        sorted_sign_ins = [a for a in sorted_activities if a.get("activity_type") == "SignIn"]
        sorted_app_activities = [
            a
            for a in sorted_activities
            if a.get("activity_type") in {"SignIn", "Calendar", "CalendarEnd", "Outlook", "SharePoint", "OneDrive", "TeamsPresence", "CompanyDevice"}
        ]

        login: datetime | None = None
        logout: datetime | None = None
        if sorted_app_activities:
            login = date_parser.parse(sorted_app_activities[0]["activity_time"])
            logout = date_parser.parse(sorted_app_activities[-1]["activity_time"])
            if logout < login:
                logout = login

        anchor_activities = [
            a for a in sorted_app_activities
            if a.get("activity_type") in self._ANCHOR_ACTIVITY_TYPES
        ]
        working_hours = self._calculate_activity_hours(sorted_app_activities)
        # Fallback: use login→logout span only when anchor events exist
        # (prevents background-only nights from generating false hours)
        if working_hours == 0 and login and logout and logout > login and anchor_activities:
            working_hours = self._hours_from_seconds((logout - login).total_seconds())
        meeting_hours = self._calculate_meeting_hours(calendar_events)
        reason = self._build_reason(sorted_app_activities, meeting_hours)
        is_weekend = attendance_date.weekday() >= 5

        if self._is_holiday(attendance_date, holidays):
            return self._build_record(
                attendance_date,
                login,
                logout,
                working_hours,
                meeting_hours,
                AttendanceStatus.HOLIDAY.value,
                (sorted_sign_ins[-1]["activity_time"] if sorted_sign_ins else (sorted_app_activities[-1]["activity_time"] if sorted_app_activities else None)),
                "Holiday",
            )

        if self._is_on_leave(attendance_date, leaves):
            return self._build_record(
                attendance_date,
                login,
                logout,
                working_hours,
                meeting_hours,
                AttendanceStatus.ON_LEAVE.value,
                (sorted_sign_ins[-1]["activity_time"] if sorted_sign_ins else (sorted_app_activities[-1]["activity_time"] if sorted_app_activities else None)),
                "Approved leave",
            )

        if not sorted_sign_ins and not sorted_app_activities:
            return self._build_record(attendance_date, None, None, 0.0, 0.0, AttendanceStatus.ABSENT.value, None, "No cloud activity")

        office_start = self._parse_time(settings.get("OfficeStartTime", "09:00:00"), time(9, 0))
        grace_period = int(settings.get("GracePeriod", 15))
        working_hours_per_day = float(settings.get("WorkingHoursPerDay", 8.0))

        status = AttendanceStatus.PRESENT.value

        if not is_weekend:
            login_cutoff = datetime.combine(attendance_date, office_start)
            if login.tzinfo is not None:
                login_cutoff = login_cutoff.replace(tzinfo=login.tzinfo)
            login_cutoff = login_cutoff + timedelta(minutes=grace_period)
            if login and login > login_cutoff:
                status = AttendanceStatus.LATE.value

            if 0 < working_hours < working_hours_per_day / 2:
                status = AttendanceStatus.HALF_DAY.value

        if login and logout and login == logout and working_hours == 0 and meeting_hours == 0:
            logout = None

        return self._build_record(
            attendance_date,
            login,
            logout,
            working_hours,
            meeting_hours,
            status,
            sorted_sign_ins[-1]["activity_time"] if sorted_sign_ins else sorted_app_activities[-1]["activity_time"],
            reason,
        )

    def _calculate_activity_hours(self, activities: list[dict[str, Any]]) -> float:
        if len(activities) < 2:
            return 0.0

        parsed = [
            (date_parser.parse(a["activity_time"]), a.get("activity_type") or "")
            for a in activities
        ]
        max_gap_seconds = self._ACTIVITY_HOURS_GAP_MINUTES * 60

        # Group into contiguous sessions separated by gaps > 90 min.
        sessions: list[list[tuple[datetime, str]]] = []
        current: list[tuple[datetime, str]] = [parsed[0]]
        for i in range(1, len(parsed)):
            gap = (parsed[i][0] - parsed[i - 1][0]).total_seconds()
            if gap <= max_gap_seconds:
                current.append(parsed[i])
            else:
                sessions.append(current)
                current = [parsed[i]]
        sessions.append(current)

        # Only accumulate time for sessions anchored by a real user-presence
        # event (SignIn or TeamsPresence). Background-only sessions (Outlook,
        # SharePoint, OneDrive syncing overnight) are excluded entirely.
        total_seconds = 0.0
        for session in sessions:
            has_anchor = any(t in self._ANCHOR_ACTIVITY_TYPES for _, t in session)
            if not has_anchor:
                continue
            for i in range(1, len(session)):
                gap = (session[i][0] - session[i - 1][0]).total_seconds()
                if 0 < gap <= max_gap_seconds:
                    total_seconds += gap

        return self._hours_from_seconds(total_seconds)

    def _calculate_background_cloud_hours(self, activities: list[dict[str, Any]]) -> float:
        """Calculate hours from background-only cloud activity (no user-presence anchor).
        This detects suspicious overnight OneDrive/Outlook/SharePoint syncs that don't
        correspond to actual user work.
        """
        if len(activities) < 2:
            return 0.0

        parsed = [
            (date_parser.parse(a["activity_time"]), a.get("activity_type") or "")
            for a in activities
        ]
        max_gap_seconds = self._ACTIVITY_HOURS_GAP_MINUTES * 60

        # Group into contiguous sessions.
        sessions: list[list[tuple[datetime, str]]] = []
        current: list[tuple[datetime, str]] = [parsed[0]]
        for i in range(1, len(parsed)):
            gap = (parsed[i][0] - parsed[i - 1][0]).total_seconds()
            if gap <= max_gap_seconds:
                current.append(parsed[i])
            else:
                sessions.append(current)
                current = [parsed[i]]
        sessions.append(current)

        # Only accumulate time for sessions WITHOUT an anchor (background only).
        total_seconds = 0.0
        for session in sessions:
            has_anchor = any(t in self._ANCHOR_ACTIVITY_TYPES for _, t in session)
            if has_anchor:  # Skip anchored sessions; we want background-only.
                continue
            for i in range(1, len(session)):
                gap = (session[i][0] - session[i - 1][0]).total_seconds()
                if 0 < gap <= max_gap_seconds:
                    total_seconds += gap

        return self._hours_from_seconds(total_seconds)

    def _calculate_meeting_hours(self, events: list[dict[str, Any]]) -> float:
        total_seconds = 0
        for event in events:
            if event.get("isCancelled"):
                continue
            start_raw = event.get("start", {}).get("dateTime")
            end_raw = event.get("end", {}).get("dateTime")
            if not start_raw or not end_raw:
                continue
            start = date_parser.parse(start_raw)
            end = date_parser.parse(end_raw)
            if end > start:
                total_seconds += (end - start).total_seconds()
        return round(total_seconds / 3600, 2)

    def _build_record(
        self,
        attendance_date: date,
        login: datetime | None,
        logout: datetime | None,
        working_hours: float,
        meeting_hours: float,
        status: str,
        last_activity: str | None = None,
        remarks: str | None = None,
    ) -> dict[str, Any]:
        return {
            "AttendanceDate": attendance_date.isoformat(),
            "LoginTime": login.isoformat() if login else None,
            "LogoutTime": logout.isoformat() if logout else None,
            "WorkingHours": working_hours,
            "MeetingHours": meeting_hours,
            "AttendanceStatus": status,
            "Source": "Microsoft Graph",
            "LastActivity": last_activity or (logout.isoformat() if logout else None),
            "Remarks": remarks,
        }

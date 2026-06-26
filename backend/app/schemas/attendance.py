from datetime import date, datetime

from pydantic import BaseModel, Field


class AttendanceRecord(BaseModel):
    id: str | None = None
    employee: str
    attendance_date: date
    login_time: datetime | None = None
    logout_time: datetime | None = None
    working_hours: float = Field(default=0.0, ge=0)
    meeting_hours: float = Field(default=0.0, ge=0)
    attendance_status: str
    source: str = "Microsoft Graph"
    last_activity: datetime | None = None
    remarks: str | None = None


class AttendanceSummary(BaseModel):
    present: int
    absent: int
    late: int
    half_day: int
    on_leave: int
    holiday: int
    weekend: int


class SyncResult(BaseModel):
    processed_employees: int
    updated_records: int
    created_records: int
    run_at: datetime

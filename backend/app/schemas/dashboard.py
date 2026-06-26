from pydantic import BaseModel


class EmployeeDashboard(BaseModel):
    todays_login: str | None = None
    todays_logout: str | None = None
    working_hours: float = 0
    meeting_hours: float = 0
    attendance_status: str = "Absent"
    monthly_attendance: float = 0
    leave_balance: float = 0
    upcoming_holidays: list[dict] = []
    recent_announcements: list[dict] = []


class ManagerDashboard(BaseModel):
    present_employees: int
    absent_employees: int
    late_login: int
    avg_working_hours: float
    avg_meeting_hours: float
    attendance_percentage: float
    monthly_trends: list[dict]
    department_summary: list[dict]


class AdminDashboard(BaseModel):
    total_employees: int
    todays_attendance: dict
    synchronization_status: dict
    graph_api_status: str
    sharepoint_status: str
    attendance_trends: list[dict]
    audit_logs: list[dict]

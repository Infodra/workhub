from enum import Enum


class AttendanceStatus(str, Enum):
    PRESENT = "Present"
    ABSENT = "Absent"
    HALF_DAY = "Half Day"
    LATE = "Late"
    ON_LEAVE = "On Leave"
    HOLIDAY = "Holiday"
    WEEKEND = "Weekend"


class RoleName(str, Enum):
    EMPLOYEE = "Employee"
    MANAGER = "Manager"
    ADMIN = "Admin"

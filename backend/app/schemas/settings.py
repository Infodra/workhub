from datetime import time

from pydantic import BaseModel, Field


class AttendanceSettings(BaseModel):
    office_start_time: time
    office_end_time: time
    grace_period: int = Field(default=15, ge=0)
    working_hours_per_day: float = Field(default=8.0, ge=1)
    attendance_calculation_method: str = "ActivityBased"

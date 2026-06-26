from pydantic import BaseModel
from datetime import date


class ManualSyncRequest(BaseModel):
    employee_emails: list[str] | None = None
    target_date: date | None = None
    start_date: date | None = None
    end_date: date | None = None

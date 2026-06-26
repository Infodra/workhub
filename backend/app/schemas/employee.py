from datetime import date

from pydantic import BaseModel, EmailStr


class Employee(BaseModel):
    id: str | None = None
    employee_id: str
    employee_name: str
    email: EmailStr
    department: str | None = None
    designation: str | None = None
    manager: str | None = None
    status: str = "Active"
    location: str | None = None
    joining_date: date | None = None

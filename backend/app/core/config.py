from functools import lru_cache
from typing import List

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Infodra WorkHub API"
    app_env: str = "development"
    app_port: int = 8000
    allowed_origins: str = "http://localhost:3000"
    force_https: bool = False

    tenant_id: str
    client_id: str
    client_secret: str
    authority: str
    api_audience: str
    frontend_client_id: str
    manager_override_emails: str = ""

    sharepoint_site_id: str
    sp_list_employees: str = "Employees"
    sp_list_attendance: str = "Attendance"
    sp_list_activity_logs: str = "ActivityLogs"
    sp_list_leave: str = "Leave"
    sp_list_holidays: str = "Holidays"
    sp_list_settings: str = "Settings"
    sp_list_audit_logs: str = "AuditLogs"

    scheduler_interval_minutes: int = 15
    default_timezone: str = "Asia/Kolkata"

    # Windows Event Log configuration for device activity tracking
    winrm_enabled: bool = False
    winrm_endpoint: str = "http://localhost:5985/wsman"  # Default local WinRM endpoint
    winrm_username: str = ""
    winrm_password: str = ""
    device_tracking_enabled: bool = False

    @field_validator("allowed_origins")
    @classmethod
    def validate_allowed_origins(cls, v: str) -> str:
        return ",".join([origin.strip() for origin in v.split(",") if origin.strip()])

    @property
    def cors_origins(self) -> List[str]:
        return [origin.strip() for origin in self.allowed_origins.split(",") if origin.strip()]

    @property
    def manager_override_email_set(self) -> set[str]:
        return {email.strip().lower() for email in self.manager_override_emails.split(",") if email.strip()}


@lru_cache
def get_settings() -> Settings:
    return Settings()

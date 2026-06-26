from fastapi import APIRouter

from app.api.v1.routes import attendance, dashboard, device_activity, employees, reports, settings, sync

api_router = APIRouter()
api_router.include_router(employees.router, prefix="/employees", tags=["Employees"])
api_router.include_router(attendance.router, prefix="/attendance", tags=["Attendance"])
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["Dashboard"])
api_router.include_router(reports.router, prefix="/reports", tags=["Reports"])
api_router.include_router(settings.router, prefix="/settings", tags=["Settings"])
api_router.include_router(sync.router, prefix="/sync", tags=["Synchronization"])
api_router.include_router(device_activity.router, prefix="/device-activity", tags=["Device Activity"])

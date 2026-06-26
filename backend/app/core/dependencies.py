from app.repositories.sharepoint_repository import SharePointRepository
from app.services.attendance_engine import AttendanceEngine
from app.services.graph_client import GraphApiClient
from app.services.sync_service import SyncService


def get_graph_client() -> GraphApiClient:
    return GraphApiClient()


def get_sharepoint_repository() -> SharePointRepository:
    return SharePointRepository()


def get_attendance_engine() -> AttendanceEngine:
    return AttendanceEngine()


def get_sync_service() -> SyncService:
    return SyncService(
        graph_client=get_graph_client(),
        sharepoint_repository=get_sharepoint_repository(),
        attendance_engine=get_attendance_engine(),
    )

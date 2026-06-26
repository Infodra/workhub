from pydantic import BaseModel


class ReportResponse(BaseModel):
    report_type: str
    generated_at: str
    items: list[dict]

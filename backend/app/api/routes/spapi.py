from fastapi import APIRouter

from app.schemas.spapi import SPAPIReportTypeResponse
from app.services.amazon.report_types import get_enabled_report_types

router = APIRouter(prefix="/spapi", tags=["spapi"])


@router.get("/report-types", response_model=list[SPAPIReportTypeResponse])
def report_types() -> list[SPAPIReportTypeResponse]:
    return [
        SPAPIReportTypeResponse(**report_type.__dict__)
        for report_type in get_enabled_report_types()
    ]

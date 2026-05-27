from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="app/web/templates")
router = APIRouter()


@router.get("/")
def dashboard(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={"title": "Dashboard"},
    )


@router.get("/imports")
def imports_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="imports.html",
        context={"title": "Data Import"},
    )


@router.get("/reports")
def reports_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="reports.html",
        context={"title": "Report Center"},
    )


@router.get("/settings")
def settings_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="settings.html",
        context={"title": "Settings"},
    )

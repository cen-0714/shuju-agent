from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.routes.health import router as health_router
from app.api.routes.imports import router as imports_router
from app.api.routes.settings import router as settings_router
from app.web.routes import router as web_router


def create_app() -> FastAPI:
    app = FastAPI(title="Amazon Daily Copilot")
    app.mount("/static", StaticFiles(directory="app/web/static"), name="static")
    app.include_router(health_router, prefix="/api")
    app.include_router(imports_router, prefix="/api")
    app.include_router(settings_router, prefix="/api")
    app.include_router(web_router)
    return app


app = create_app()

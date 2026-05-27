from fastapi import FastAPI

from app.api.routes.health import router as health_router
from app.api.routes.imports import router as imports_router


def create_app() -> FastAPI:
    app = FastAPI(title="Amazon Daily Copilot")
    app.include_router(health_router, prefix="/api")
    app.include_router(imports_router, prefix="/api")
    return app


app = create_app()

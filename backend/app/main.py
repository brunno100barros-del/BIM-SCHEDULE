"""Aplicação FastAPI do serviço local BIM SCHEDULE."""
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI

from app import models  # noqa: F401  (registra as tabelas no metadata)
from app.api.v1.api import api_router
from app.core.bootstrap import start_runtime, stop_runtime
from app.core.config import Settings, get_settings
from app.core.errors import register_exception_handlers
from app.core.security import install_middlewares


def create_app(settings: Optional[Settings] = None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        application.state.runtime = start_runtime(settings)
        try:
            yield
        finally:
            stop_runtime(application.state.runtime)
            application.state.runtime = None

    application = FastAPI(
        title=settings.PROJECT_NAME,
        version=settings.VERSION,
        description="Planejamento de obras com integração BIM/IFC e motor CPM/PERT. Serviço local.",
        openapi_url=f"{settings.API_V1_STR}/openapi.json",
        docs_url="/docs",
        lifespan=lifespan,
    )
    install_middlewares(application, settings)
    register_exception_handlers(application)
    application.include_router(api_router, prefix=settings.API_V1_STR)

    @application.get("/", tags=["system"])
    def root():
        return {"message": "BIM SCHEDULE API", "version": settings.VERSION, "status": "ok"}

    @application.get("/health", tags=["system"])
    def health():
        return {"status": "healthy"}

    return application


app = create_app()

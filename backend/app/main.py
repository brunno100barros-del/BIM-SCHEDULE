from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.core.database import engine, Base
from app.api.v1.api import api_router
# Importar modelos garante que todas as tabelas estejam registradas no metadata.
from app import models  # noqa: F401

@asynccontextmanager
async def lifespan(application: FastAPI):
    # Fallback para primeira execução; migrações oficiais são executadas pelo instalador.
    Base.metadata.create_all(bind=engine)
    yield

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Planejamento de obras com integração BIM/IFC e motor CPM/PERT.",
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.API_V1_STR)

@app.get("/", tags=["health"])
def root():
    return {"message": "BIM SCHEDULE API", "version": settings.VERSION, "status": "ok"}

@app.get("/health", tags=["health"])
def health():
    return {"status": "healthy"}

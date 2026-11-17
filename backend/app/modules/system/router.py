"""Saúde e estado do serviço local, consultados pelo frontend e pelo app desktop."""
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.runtime import Runtime, get_runtime

router = APIRouter()

# Estado real de cada área do produto. "available" = implementado e testado;
# "experimental" = funciona, mas precisa de validação; "not_implemented" = apenas preparado.
CAPABILITIES = {
    "projects": "available",
    "planning_cpm": "available",
    "ifc_processing": "experimental",
    "ifc_viewer": "experimental",
    "background_jobs": "available",
    "ai_manual_exchange": "experimental",
    "ai_local_ollama": "not_implemented",
    "budget_import": "not_implemented",
    "simulation_4d": "not_implemented",
    "reports": "not_implemented",
}


@router.get("/health")
def health():
    """Verificação leve (sem banco). Usada pelo app desktop para saber quando o serviço subiu."""
    return {"status": "ok"}


@router.get("/status")
def status(runtime: Runtime = Depends(get_runtime), db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        database = {"ok": True, "revision": runtime.schema.get("to")}
    except Exception as exc:  # pragma: no cover - depende de falha real do banco
        database = {"ok": False, "error": str(exc)}
    settings = runtime.settings
    return {
        "app": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "api_version": "v1",
        "environment": settings.ENVIRONMENT,
        "started_at": runtime.started_at,
        "database": database,
        "storage": runtime.storage.public_summary(),
        "jobs": {"max_workers": runtime.jobs.max_workers, "running": runtime.jobs.active_count()},
        "ai": {"provider": settings.AI_PROVIDER},
        "security": {"local_token_required": bool(settings.LOCAL_API_TOKEN)},
        "capabilities": CAPABILITIES,
    }

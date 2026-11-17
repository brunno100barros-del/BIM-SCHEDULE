"""Rotas de preparação para IA: provedores, esquemas e intercâmbio manual por arquivo."""
from typing import Any, Literal

from fastapi import APIRouter, Body, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.errors import AppError
from app.core.runtime import Runtime, get_runtime
from app.modules.ai import service
from app.modules.ai.exchange import AIRequestPackage, AIResponsePackage
from app.modules.projects.service import get_project_or_404

router = APIRouter()


@router.get("/providers")
def list_providers(runtime: Runtime = Depends(get_runtime)):
    """Lista os provedores configuráveis. Não consulta serviços externos."""
    return {
        "configured": runtime.settings.AI_PROVIDER,
        "providers": [
            {"kind": "manual-claude", "label": "Claude (intercâmbio manual por arquivo)", "implemented": True},
            {"kind": "ollama", "label": "IA local (Ollama)", "implemented": False,
             "base_url": runtime.settings.OLLAMA_BASE_URL, "model": runtime.settings.OLLAMA_MODEL},
        ],
    }


@router.get("/providers/{kind}/status")
def provider_status(kind: str, runtime: Runtime = Depends(get_runtime)):
    provider = service.available_providers(runtime.settings).get(kind)
    if provider is None:
        raise AppError(404, "Provedor de IA desconhecido.", code="ai_provider_not_found")
    return provider.status().to_dict()


@router.get("/schema/{which}")
def exchange_schema(which: Literal["request", "response"]):
    """JSON Schema do formato de intercâmbio (para orientar a IA e validar arquivos)."""
    model = AIRequestPackage if which == "request" else AIResponsePackage
    return model.model_json_schema()


@router.get("/projects/{project_id}/request-package")
def export_request_package(project_id: int, db: Session = Depends(get_db), runtime: Runtime = Depends(get_runtime)):
    project = get_project_or_404(db, project_id)
    package = service.build_request_package(db, project, runtime.settings)
    filename = f"bim-schedule-ai-request-{project.code}.json"
    return JSONResponse(package.model_dump(mode="json"),
                        headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@router.post("/projects/{project_id}/validate-response")
def validate_response(project_id: int, payload: Any = Body(...), db: Session = Depends(get_db)):
    """Valida um arquivo de resposta sem aplicar nenhuma alteração ao planejamento."""
    project = get_project_or_404(db, project_id)
    return service.validate_response(db, project, payload)

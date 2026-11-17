"""Montagem do pacote de pedido e validação das respostas de IA.

A validação **não aplica** nenhuma alteração ao planejamento. Aplicar propostas
(com recálculo pelo motor CPM e aprovação do usuário) é escopo de etapa futura.
"""
from __future__ import annotations

import uuid
from collections import Counter
from datetime import datetime, timezone
from typing import Any

from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models.ifc import IfcElementModel, IfcModelModel
from app.models.project import ProjectModel
from app.models.wbs_activity import ActivityModel, WbsNodeModel
from app.modules.ai.exchange import (
    DEFAULT_INSTRUCTIONS, RESPONSE_FORMAT, SCHEMA_VERSION, ActivityContext, AIRequestPackage, AIResponsePackage,
    GeneratorInfo, IfcModelSummary, PrecedenceContext, ProjectContext, WbsNodeContext,
)
from app.modules.ai.providers.base import AIProvider
from app.modules.ai.providers.manual import ManualExchangeProvider
from app.modules.ai.providers.ollama import OllamaProvider
from app.modules.planning.service import contract_deadline_days, project_network


def available_providers(settings: Settings) -> dict[str, AIProvider]:
    return {
        "manual-claude": ManualExchangeProvider(),
        "ollama": OllamaProvider(settings.OLLAMA_BASE_URL, settings.OLLAMA_MODEL),
    }


def build_request_package(db: Session, project: ProjectModel, settings: Settings) -> AIRequestPackage:
    acts, precs = project_network(db, project.id)
    wbs = db.query(WbsNodeModel).filter(WbsNodeModel.project_id == project.id).order_by(WbsNodeModel.sort_order, WbsNodeModel.id).all()
    models = db.query(IfcModelModel).filter(IfcModelModel.project_id == project.id).order_by(IfcModelModel.version).all()
    summaries = []
    for model in models:
        rows = db.query(IfcElementModel.ifc_type, IfcElementModel.storey_name).filter(IfcElementModel.model_id == model.id).all()
        summaries.append(IfcModelSummary(
            id=model.id, filename=model.filename, version=model.version, schema_name=model.schema_name,
            status=model.status, element_count=model.element_count or 0,
            elements_by_type=dict(Counter(t for t, _ in rows)),
            storeys=sorted({s for _, s in rows if s}),
        ))
    try:
        target = contract_deadline_days(project)
    except ValueError:
        target = None
    return AIRequestPackage(
        package_id=uuid.uuid4().hex,
        created_at=datetime.now(timezone.utc),
        generator=GeneratorInfo(version=settings.VERSION),
        project=ProjectContext(
            id=project.id, code=project.code, name=project.name, client=project.client,
            description=project.description, start_date=project.start_date, end_date=project.end_date,
            target_duration_days=target,
        ),
        wbs=[WbsNodeContext(id=n.id, code=n.code, name=n.name, parent_id=n.parent_id) for n in wbs],
        activities=[ActivityContext(
            id=a.id, code=a.code, name=a.name, wbs_id=a.wbs_id, duration=a.duration, quantity=a.quantity,
            unit=a.unit, optimistic=a.optimistic, most_likely=a.most_likely, pessimistic=a.pessimistic,
        ) for a in acts],
        precedences=[PrecedenceContext(predecessor_id=p.predecessor_id, successor_id=p.successor_id,
                                       relation_type=p.relation_type, lag=p.lag) for p in precs],
        ifc_models=summaries,
        instructions=DEFAULT_INSTRUCTIONS,
    )


def _normalize(payload: Any, warnings: list[str]) -> Any:
    """Converte o formato da demonstração antiga (sem cabeçalho) para o formato v1."""
    if isinstance(payload, dict) and "format" not in payload and any(
        k in payload for k in ("activities_updates", "risks", "assumptions")
    ):
        warnings.append("Resposta no formato antigo da demonstração; convertida para o formato v1.")
        return {"format": RESPONSE_FORMAT, "schema_version": SCHEMA_VERSION,
                "provider": {"kind": "legacy-demo"}, **payload}
    return payload


def validate_response(db: Session, project: ProjectModel, payload: Any) -> dict:
    warnings: list[str] = []
    errors: list[dict] = []
    data = _normalize(payload, warnings)
    try:
        response = AIResponsePackage.model_validate(data)
    except ValidationError as exc:
        errors = [{"loc": list(e["loc"]), "msg": e["msg"]} for e in exc.errors()]
        return {"valid": False, "errors": errors, "warnings": warnings, "summary": None}

    activity_ids = {a.id for a in db.query(ActivityModel.id).filter(ActivityModel.project_id == project.id).all()}
    for index, update in enumerate(response.activities_updates):
        if update.id not in activity_ids:
            errors.append({"loc": ["activities_updates", index, "id"], "msg": f"Atividade {update.id} não pertence ao projeto."})
    for index, seq in enumerate(response.sequence_suggestions):
        for field in ("predecessor_id", "successor_id"):
            if getattr(seq, field) not in activity_ids:
                errors.append({"loc": ["sequence_suggestions", index, field], "msg": f"Atividade {getattr(seq, field)} não pertence ao projeto."})
        if seq.predecessor_id == seq.successor_id:
            errors.append({"loc": ["sequence_suggestions", index], "msg": "Uma atividade não pode preceder a si mesma."})

    summary = {
        "provider": response.provider.kind,
        "methodology_proposals": len(response.methodology_proposals),
        "activities_updates": len(response.activities_updates),
        "new_activity_suggestions": len(response.new_activity_suggestions),
        "sequence_suggestions": len(response.sequence_suggestions),
        "risks": len(response.risks),
        "assumptions": len(response.assumptions),
    }
    return {"valid": not errors, "errors": errors, "warnings": warnings + response.warnings, "summary": summary}

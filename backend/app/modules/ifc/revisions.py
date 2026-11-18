"""Modelos lógicos (``BimModel``) e revisões (``IfcModelModel``): regras de negócio.

Conceitos:
* **Modelo lógico**: um conjunto de informação do projeto (ex.: "Estrutura Torre A").
* **Revisão**: cada arquivo IFC importado para um modelo lógico, numerado 1, 2, 3...
* **Revisão vigente** (``is_current``): a revisão concluída mais recente do modelo. Uma
  revisão nova só passa a vigente quando o processamento termina com sucesso.

Identidade dos elementos: ``(revisão, GlobalId)``. O GlobalId nunca é usado sozinho,
porque arquivos distintos (ou revisões distintas) podem repeti-lo.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models.ifc import REVISION_HIDDEN_STATUSES, BimModel, IfcElementModel, IfcModelModel
from app.models.wbs_activity import ActivityIfcElementModel

# Disciplinas aceitas como indicação do arquivo. Na Fase 4 passam a uma tabela configurável.
DISCIPLINE_HINTS = (
    "arquitetura", "estrutura_concreto", "estrutura_metalica", "eletrica",
    "hidrossanitaria", "climatizacao", "outras",
)
ACTIVE_PROCESSING = ("queued", "processing")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def validate_discipline_hint(value: Optional[str]) -> Optional[str]:
    if value in (None, ""):
        return None
    if value not in DISCIPLINE_HINTS:
        raise AppError(422, f"Disciplina inválida. Use uma de: {', '.join(DISCIPLINE_HINTS)}.",
                       code="invalid_discipline_hint")
    return value


def visible_revisions(db: Session, project_id: Optional[int] = None):
    query = db.query(IfcModelModel).filter(IfcModelModel.status.notin_(REVISION_HIDDEN_STATUSES))
    if project_id is not None:
        query = query.filter(IfcModelModel.project_id == project_id)
    return query


def get_bim_model_or_404(db: Session, bim_model_id: int, project_id: Optional[int] = None) -> BimModel:
    bim = db.get(BimModel, bim_model_id)
    if bim is None or bim.deleted_at is not None or (project_id is not None and bim.project_id != project_id):
        raise AppError(404, "Modelo BIM não encontrado neste projeto.", code="bim_model_not_found")
    return bim


def get_revision_or_404(db: Session, model_id: int, *, allow_hidden: bool = False) -> IfcModelModel:
    model = db.get(IfcModelModel, model_id)
    if model is None:
        raise AppError(404, "Modelo IFC não encontrado.", code="ifc_model_not_found")
    if not allow_hidden and model.status in REVISION_HIDDEN_STATUSES:
        raise AppError(404, "Esta revisão foi removida.", code="ifc_model_removed")
    return model


def next_revision_number(db: Session, bim_model_id: int) -> int:
    current = db.query(func.max(IfcModelModel.revision_number)).filter(IfcModelModel.bim_model_id == bim_model_id).scalar()
    return (current or 0) + 1


def resolve_target_bim_model(db: Session, project_id: int, *, bim_model_id: Optional[int], model_name: Optional[str],
                             discipline_hint: Optional[str], filename: str) -> BimModel:
    """Modelo lógico de destino de um upload: existente (nova revisão) ou novo."""
    hint = validate_discipline_hint(discipline_hint)
    if bim_model_id is not None:
        bim = get_bim_model_or_404(db, bim_model_id, project_id)
        if hint and hint != bim.discipline_hint:
            bim.discipline_hint = hint
        return bim
    name = (model_name or "").strip() or Path(filename).stem or filename
    bim = BimModel(project_id=project_id, name=name[:255], discipline_hint=hint)
    db.add(bim)
    db.flush()
    return bim


def find_duplicate(db: Session, project_id: int, sha256: str) -> list[IfcModelModel]:
    return (visible_revisions(db, project_id).filter(IfcModelModel.sha256 == sha256)
            .order_by(IfcModelModel.id).all())


def refresh_current_revision(db: Session, bim_model_id: Optional[int]) -> Optional[int]:
    """Define como vigente a revisão concluída de maior número; retorna o id (ou None)."""
    if bim_model_id is None:
        return None
    revisions = (db.query(IfcModelModel).filter(IfcModelModel.bim_model_id == bim_model_id)
                 .order_by(IfcModelModel.revision_number.desc(), IfcModelModel.id.desc()).all())
    current_id = next((r.id for r in revisions if r.status == "completed"), None)
    for revision in revisions:
        revision.is_current = revision.id == current_id
    return current_id


def revision_summary(model: IfcModelModel) -> dict:
    return {
        "id": model.id, "revision_number": model.revision_number, "filename": model.filename,
        "status": model.status, "is_current": bool(model.is_current), "uploaded_at": model.uploaded_at,
        "element_count": model.element_count or 0, "schema_name": model.schema_name,
        "file_size": model.file_size, "sha256": model.sha256, "ifc_project_global_id": model.ifc_project_global_id,
        "job_id": model.job_id, "progress": model.progress, "processing_message": model.processing_message,
        "error_message": model.error_message,
    }


def list_bim_models(db: Session, project_id: int) -> list[dict]:
    models = (db.query(BimModel).filter(BimModel.project_id == project_id, BimModel.deleted_at.is_(None))
              .order_by(BimModel.id).all())
    revisions = (visible_revisions(db, project_id).filter(IfcModelModel.bim_model_id.isnot(None))
                 .order_by(IfcModelModel.revision_number).all())
    by_model: dict[int, list[IfcModelModel]] = {}
    for revision in revisions:
        by_model.setdefault(revision.bim_model_id, []).append(revision)
    result = []
    for bim in models:
        items = by_model.get(bim.id, [])
        current = next((r for r in items if r.is_current), None)
        result.append({
            "id": bim.id, "project_id": bim.project_id, "name": bim.name, "discipline_hint": bim.discipline_hint,
            "description": bim.description, "created_at": bim.created_at, "updated_at": bim.updated_at,
            "current_revision_id": current.id if current else None,
            "revisions": [revision_summary(r) for r in items],
        })
    return result


def revision_candidates(db: Session, model: IfcModelModel) -> list[dict]:
    """Modelos lógicos dos quais esta revisão provavelmente é uma nova versão.

    Evidências: mesmo GlobalId de ``IfcProject`` (forte) e mesmo nome de arquivo (fraca).
    Apenas sugestão: o usuário confirma com ``move_to_bim_model``.
    """
    candidates = []
    stem = Path(model.filename).stem.lower()
    for other in visible_revisions(db, model.project_id).filter(IfcModelModel.id != model.id,
                                                                IfcModelModel.bim_model_id.isnot(None),
                                                                IfcModelModel.bim_model_id != model.bim_model_id).all():
        reasons = []
        if model.ifc_project_global_id and other.ifc_project_global_id == model.ifc_project_global_id:
            reasons.append("mesmo GlobalId de IfcProject")
        if Path(other.filename).stem.lower() == stem:
            reasons.append("mesmo nome de arquivo")
        if reasons:
            candidates.append({"bim_model_id": other.bim_model_id, "revision_id": other.id,
                               "revision_number": other.revision_number, "filename": other.filename,
                               "reasons": reasons, "strength": "alta" if len(reasons) > 1 or reasons[0].startswith("mesmo GlobalId") else "baixa"})
    seen, unique = set(), []
    for c in sorted(candidates, key=lambda c: (c["strength"] != "alta", c["bim_model_id"])):
        if c["bim_model_id"] not in seen:
            seen.add(c["bim_model_id"])
            unique.append(c)
    return unique


def move_to_bim_model(db: Session, model: IfcModelModel, target: BimModel) -> IfcModelModel:
    if target.project_id != model.project_id:
        raise AppError(400, "O modelo de destino pertence a outro projeto.", code="bim_model_other_project")
    if model.status in ACTIVE_PROCESSING:
        raise AppError(409, "Aguarde o fim do processamento antes de reagrupar a revisão.", code="ifc_model_busy")
    source_id = model.bim_model_id
    if source_id == target.id:
        return model
    model.bim_model_id = target.id
    model.revision_number = next_revision_number(db, target.id)
    db.flush()
    refresh_current_revision(db, target.id)
    refresh_current_revision(db, source_id)
    if source_id is not None and not visible_revisions(db).filter(IfcModelModel.bim_model_id == source_id).count():
        source = db.get(BimModel, source_id)
        if source is not None and source.deleted_at is None:
            source.deleted_at = _now()
    return model


def linked_activity_count(db: Session, model_ids: list[int]) -> int:
    if not model_ids:
        return 0
    return (db.query(func.count(ActivityIfcElementModel.id))
            .join(IfcElementModel, IfcElementModel.id == ActivityIfcElementModel.ifc_element_id)
            .filter(IfcElementModel.model_id.in_(model_ids)).scalar() or 0)


def mark_revision_for_deletion(db: Session, model: IfcModelModel) -> None:
    """Oculta a revisão imediatamente e recalcula a vigente; a remoção física é uma tarefa."""
    if model.status in ACTIVE_PROCESSING:
        raise AppError(409, "A revisão está em processamento. Cancele o processamento antes de removê-la.",
                       code="ifc_model_busy")
    model.status = "deleting"
    model.deleted_at = model.deleted_at or _now()
    model.is_current = False
    model.processing_message = "Remoção em andamento"
    db.flush()
    refresh_current_revision(db, model.bim_model_id)


def safe_to_delete_file(db: Session, model: IfcModelModel, uploads_dir: Path) -> Optional[Path]:
    """Caminho do arquivo da revisão, se puder ser apagado com segurança; senão None.

    Só apaga arquivos dentro da pasta de uploads e que não são usados por nenhuma outra revisão.
    """
    if not model.file_path:
        return None
    path = Path(model.file_path)
    try:
        resolved = path.resolve()
        if resolved.parent != uploads_dir.resolve():
            return None
    except OSError:
        return None
    shared = db.query(func.count(IfcModelModel.id)).filter(IfcModelModel.file_path == model.file_path,
                                                          IfcModelModel.id != model.id).scalar()
    return None if shared else resolved

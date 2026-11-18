"""Rotas IFC: modelos lógicos e revisões, processamento em segundo plano, elementos, comparação e remoção."""
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.errors import AppError
from app.core.logging import get_logger
from app.core.runtime import Runtime, get_runtime
from app.models.ifc import IfcElementModel, IfcModelModel
from app.models.project import ProjectModel
from app.modules.ifc import revisions
from app.modules.ifc.service import store_ifc_upload

router = APIRouter()
logger = get_logger("ifc")


class BimModelUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    discipline_hint: Optional[str] = None
    description: Optional[str] = None


class MoveRevision(BaseModel):
    bim_model_id: int


@router.post("/project/{project_id}/upload", status_code=status.HTTP_202_ACCEPTED)
def upload_ifc(project_id: int, file: UploadFile = File(...),
               bim_model_id: Optional[int] = Form(default=None),
               model_name: Optional[str] = Form(default=None),
               discipline_hint: Optional[str] = Form(default=None),
               db: Session = Depends(get_db), runtime: Runtime = Depends(get_runtime)):
    """Recebe o arquivo e agenda o processamento em um processo separado.

    Sem ``bim_model_id``, cria um novo modelo lógico (nome = ``model_name`` ou nome do arquivo).
    Com ``bim_model_id``, registra o arquivo como nova revisão desse modelo; ela só passa a vigente
    quando o processamento terminar com sucesso. A resposta é imediata (202); o andamento é
    consultado em ``/jobs/{job_id}``.
    """
    project = db.get(ProjectModel, project_id)
    if not project:
        raise AppError(404, "Projeto não encontrado.", code="project_not_found")
    revisions.validate_discipline_hint(discipline_hint)
    if bim_model_id is not None:
        revisions.get_bim_model_or_404(db, bim_model_id, project_id)
    try:
        stored = store_ifc_upload(file.file, file.filename, project_id, runtime.storage.uploads_dir,
                                  runtime.settings.max_ifc_bytes)
    finally:
        file.file.close()
    warnings: list[str] = []
    try:
        duplicates = revisions.find_duplicate(db, project_id, stored.sha256)
        same_model = [d for d in duplicates if bim_model_id is not None and d.bim_model_id == bim_model_id]
        if same_model:
            raise AppError(409, f"Este arquivo já foi importado como revisão {same_model[0].revision_number} deste modelo.",
                           code="ifc_revision_duplicate",
                           details={"revision_id": same_model[0].id, "revision_number": same_model[0].revision_number})
        if duplicates:
            warnings.append(f"Arquivo idêntico (mesmo SHA-256) já importado neste projeto: {duplicates[0].filename} "
                            f"(revisão id {duplicates[0].id}).")
        bim = revisions.resolve_target_bim_model(db, project_id, bim_model_id=bim_model_id, model_name=model_name,
                                                 discipline_hint=discipline_hint, filename=stored.original_name)
        version = db.query(IfcModelModel).filter(IfcModelModel.project_id == project_id).count() + 1
        model = IfcModelModel(project_id=project_id, filename=stored.original_name, file_path=str(stored.path),
                              version=version, status="queued", progress=0,
                              processing_message="Aguardando processamento", error_message=None,
                              bim_model_id=bim.id, revision_number=revisions.next_revision_number(db, bim.id),
                              is_current=False, file_size=stored.size, sha256=stored.sha256)
        db.add(model)
        db.commit()
        db.refresh(model)
        job = runtime.jobs.submit("ifc.parse", {"model_id": model.id}, project_id=project_id)
        model.job_id = job["id"]
        db.commit()
    except AppError:
        db.rollback()
        stored.path.unlink(missing_ok=True)
        raise
    except Exception:
        db.rollback()
        stored.path.unlink(missing_ok=True)
        logger.exception("Falha ao registrar o modelo IFC do projeto %s", project_id)
        raise AppError(500, "Falha ao registrar o arquivo IFC recebido.", code="ifc_register_failed")
    logger.info("IFC '%s' recebido (%s bytes) para o projeto %s: modelo %s, revisão %s; tarefa %s.",
                stored.original_name, stored.size, project_id, model.bim_model_id, model.revision_number, job["id"])
    return {"id": model.id, "filename": model.filename, "version": model.version, "status": model.status,
            "size_bytes": stored.size, "sha256": stored.sha256, "job_id": job["id"],
            "bim_model_id": model.bim_model_id, "revision_number": model.revision_number, "warnings": warnings,
            "message": "Arquivo recebido. O processamento IFC foi colocado na fila."}


# ----------------------------------------------------------------------------- modelos lógicos
@router.get("/project/{project_id}/bim-models")
def list_bim_models(project_id: int, db: Session = Depends(get_db)):
    if not db.get(ProjectModel, project_id):
        raise AppError(404, "Projeto não encontrado.", code="project_not_found")
    return revisions.list_bim_models(db, project_id)


@router.patch("/bim-models/{bim_model_id}")
def update_bim_model(bim_model_id: int, data: BimModelUpdate, db: Session = Depends(get_db)):
    bim = revisions.get_bim_model_or_404(db, bim_model_id)
    values = data.model_dump(exclude_unset=True)
    if "discipline_hint" in values:
        values["discipline_hint"] = revisions.validate_discipline_hint(values["discipline_hint"])
    for key, value in values.items():
        setattr(bim, key, value)
    db.commit()
    return next(m for m in revisions.list_bim_models(db, bim.project_id) if m["id"] == bim.id)


@router.delete("/bim-models/{bim_model_id}", status_code=status.HTTP_202_ACCEPTED)
def delete_bim_model(bim_model_id: int, confirm_links: bool = False, db: Session = Depends(get_db),
                     runtime: Runtime = Depends(get_runtime)):
    """Remove o modelo lógico e todas as suas revisões. Outros modelos não são afetados."""
    bim = revisions.get_bim_model_or_404(db, bim_model_id)
    targets = revisions.visible_revisions(db).filter(IfcModelModel.bim_model_id == bim.id).all()
    pending = db.query(IfcModelModel).filter(IfcModelModel.bim_model_id == bim.id,
                                             IfcModelModel.status == "deleting").all()
    jobs = _schedule_deletion(db, runtime, targets + pending, confirm_links)
    bim.deleted_at = revisions._now()
    db.commit()
    return {"bim_model_id": bim.id, "jobs": jobs}


# ----------------------------------------------------------------------------- revisões
@router.get("/project/{project_id}/models")
def get_models(project_id: int, db: Session = Depends(get_db)):
    return revisions.visible_revisions(db, project_id).order_by(IfcModelModel.version.desc()).all()


@router.get("/model/{model_id}")
def get_model(model_id: int, db: Session = Depends(get_db)):
    # Revisões removidas continuam consultáveis (status deleting/deleted) para acompanhamento e auditoria.
    return revisions.get_revision_or_404(db, model_id, allow_hidden=True)


@router.get("/model/{model_id}/revision-candidates")
def get_revision_candidates(model_id: int, db: Session = Depends(get_db)):
    return revisions.revision_candidates(db, revisions.get_revision_or_404(db, model_id))


@router.post("/model/{model_id}/move-to-bim-model")
def move_revision(model_id: int, data: MoveRevision, db: Session = Depends(get_db)):
    """Reagrupa a revisão como nova revisão de outro modelo lógico do mesmo projeto."""
    model = revisions.get_revision_or_404(db, model_id)
    target = revisions.get_bim_model_or_404(db, data.bim_model_id, model.project_id)
    revisions.move_to_bim_model(db, model, target)
    db.commit()
    db.refresh(model)
    return revisions.revision_summary(model) | {"bim_model_id": model.bim_model_id}


@router.delete("/model/{model_id}", status_code=status.HTTP_202_ACCEPTED)
def delete_revision(model_id: int, confirm_links: bool = False, db: Session = Depends(get_db),
                    runtime: Runtime = Depends(get_runtime)):
    """Remove uma revisão. Se ela tiver elementos vinculados a atividades, exige ``confirm_links=true``.

    A revisão some das consultas imediatamente; a remoção física (vínculos, elementos e arquivo)
    é feita por uma tarefa em segundo plano. Chamar de novo retoma uma remoção interrompida.
    """
    model = revisions.get_revision_or_404(db, model_id, allow_hidden=True)
    if model.status == "deleted":
        raise AppError(404, "Esta revisão já foi removida.", code="ifc_model_removed")
    jobs = _schedule_deletion(db, runtime, [model], confirm_links)
    db.commit()
    return {"model_id": model.id, "job_id": jobs[0]["job_id"] if jobs else None}


def _schedule_deletion(db: Session, runtime: Runtime, models: list[IfcModelModel], confirm_links: bool) -> list[dict]:
    links = revisions.linked_activity_count(db, [m.id for m in models])
    if links and not confirm_links:
        raise AppError(409, f"Há {links} vínculo(s) de elementos com atividades nesta remoção. "
                            "Confirme com confirm_links=true para remover também esses vínculos.",
                       code="ifc_delete_has_links", details={"linked_elements": links})
    busy = [m.id for m in models if m.status in revisions.ACTIVE_PROCESSING]
    if busy:
        raise AppError(409, "Há revisão em processamento. Cancele o processamento antes de removê-la.",
                       code="ifc_model_busy", details={"revision_ids": busy})
    jobs = []
    for model in models:
        if model.status != "deleting":
            revisions.mark_revision_for_deletion(db, model)
    db.commit()
    for model in models:
        job = runtime.jobs.submit("ifc.delete_revision",
                                  {"model_id": model.id, "uploads_dir": str(runtime.storage.uploads_dir)},
                                  project_id=model.project_id)
        model.job_id = job["id"]
        jobs.append({"model_id": model.id, "job_id": job["id"]})
        logger.info("Remoção da revisão %s agendada (tarefa %s).", model.id, job["id"])
    return jobs


@router.get("/model/{model_id}/download")
def download_ifc(model_id: int, db: Session = Depends(get_db)):
    model = revisions.get_revision_or_404(db, model_id)
    if not model.file_path or not Path(model.file_path).exists():
        raise AppError(404, "Arquivo não encontrado.", code="ifc_file_missing")
    return FileResponse(model.file_path, media_type="application/octet-stream", filename=model.filename)


@router.get("/model/{model_id}/elements")
def get_elements(model_id: int, skip: int = 0, limit: int = Query(1000), db: Session = Depends(get_db)):
    revisions.get_revision_or_404(db, model_id)
    limit = max(1, min(limit, 5000))
    return db.query(IfcElementModel).filter(IfcElementModel.model_id == model_id).order_by(IfcElementModel.id) \
        .offset(max(0, skip)).limit(limit).all()


@router.get("/project/{project_id}/compare")
def compare_ifc_versions(project_id: int, base_model_id: int, compare_model_id: int, db: Session = Depends(get_db)):
    base = revisions.visible_revisions(db, project_id).filter(IfcModelModel.id == base_model_id).first()
    newer = revisions.visible_revisions(db, project_id).filter(IfcModelModel.id == compare_model_id).first()
    if not base or not newer:
        raise AppError(404, "Uma das versões IFC não pertence ao projeto informado.", code="ifc_model_not_found")
    if base.status != "completed" or newer.status != "completed":
        raise AppError(409, "As duas versões precisam estar processadas para comparação.", code="ifc_model_not_ready")
    base_ids = {row[0] for row in db.query(IfcElementModel.global_id).filter(IfcElementModel.model_id == base_model_id).all()}
    newer_ids = {row[0] for row in db.query(IfcElementModel.global_id).filter(IfcElementModel.model_id == compare_model_id).all()}
    return {"base_model_id": base_model_id, "compare_model_id": compare_model_id,
            "added": sorted(newer_ids - base_ids), "removed": sorted(base_ids - newer_ids),
            "unchanged": len(base_ids & newer_ids)}

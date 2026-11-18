"""Tarefa de processamento IFC (executada em processo separado)."""
from __future__ import annotations

from pathlib import Path

from sqlalchemy.orm import Session

from app.jobs.context import JobCancelled, JobContext
from app.models.ifc import IfcElementModel, IfcModelModel
from app.models.wbs_activity import ActivityIfcElementModel
from app.modules.ifc.parser import parse_ifc_and_extract
from app.modules.ifc.revisions import refresh_current_revision, safe_to_delete_file

FINAL_MODEL_STATUS = {"cancelled": "cancelled", "interrupted": "failed", "failed": "failed"}
FINAL_MODEL_MESSAGE = {
    "cancelled": "Processamento cancelado",
    "interrupted": "Processamento interrompido: o serviço foi encerrado. Envie o arquivo novamente.",
    "failed": "Falha no processamento",
}


def _reset_model(db: Session, model_id: int, status: str, error: str | None = None) -> None:
    """Remove elementos parciais e registra o estado final do modelo."""
    db.query(IfcElementModel).filter(IfcElementModel.model_id == model_id).delete()
    model = db.get(IfcModelModel, model_id)
    if model:
        model.status = FINAL_MODEL_STATUS.get(status, "failed")
        model.progress = 0
        model.element_count = 0
        model.processing_message = FINAL_MODEL_MESSAGE.get(status, "Falha no processamento")
        if error:
            model.error_message = error[:2000]
    db.commit()


def parse_ifc_job(ctx: JobContext, *, model_id: int) -> dict:
    with ctx.session() as db:
        model = db.get(IfcModelModel, model_id)
        if model is None:
            raise ValueError(f"Modelo IFC {model_id} não encontrado.")
        model.status = "processing"
        model.processing_message = "Processamento iniciado"
        db.commit()
        path = model.file_path

        def on_progress(percent: float, message: str) -> None:
            ctx.progress(percent, message)

        try:
            result = parse_ifc_and_extract(path, model_id, db, on_progress=on_progress, check_cancel=ctx.check_cancelled)
        except JobCancelled:
            db.rollback()
            _reset_model(db, model_id, "cancelled")
            raise
        except Exception as exc:
            db.rollback()
            _reset_model(db, model_id, "failed", str(exc))
            raise
    with ctx.session() as db:
        model = db.get(IfcModelModel, model_id)
        if model is not None:
            refresh_current_revision(db, model.bim_model_id)  # a revisão concluída passa a vigente
            db.commit()
    ctx.progress(100, "Processamento concluído", force=True)
    return {"model_id": model_id, **result}


def on_parse_aborted(db: Session, *, job_id: str, params: dict, status: str) -> None:
    """Executado no processo principal quando a tarefa não finalizou o próprio estado."""
    model_id = params.get("model_id")
    if model_id is None:
        return
    model = db.get(IfcModelModel, model_id)
    if model is None or model.status == "completed":
        return
    _reset_model(db, model_id, status, f"Tarefa {job_id} terminou com status '{status}'.")


DELETE_BATCH = 5000


def delete_revision_job(ctx: JobContext, *, model_id: int, uploads_dir: str) -> dict:
    """Remove uma revisão: vínculos com atividades e elementos em lotes, depois o arquivo.

    Idempotente e interrompível: se for cancelada ou falhar, a revisão continua oculta
    (``deleting``) e uma nova solicitação de remoção retoma do ponto em que parou. Nada de
    outras revisões, modelos ou projetos é tocado.
    """
    try:
        return _delete_revision(ctx, model_id, uploads_dir)
    except (JobCancelled, Exception) as exc:
        status = "cancelled" if isinstance(exc, JobCancelled) else "failed"
        with ctx.session() as db:
            on_delete_aborted(db, job_id=ctx.job_id, params={"model_id": model_id}, status=status)
        raise


def _delete_revision(ctx: JobContext, model_id: int, uploads_dir: str) -> dict:
    with ctx.session() as db:
        model = db.get(IfcModelModel, model_id)
        if model is None:
            return {"model_id": model_id, "elements_deleted": 0, "links_deleted": 0, "file_deleted": False}
        if model.status != "deleting":
            raise ValueError(f"A revisão {model_id} não está marcada para remoção (status '{model.status}').")
        total = db.query(IfcElementModel).filter(IfcElementModel.model_id == model_id).count()
        deleted = links = 0
        while True:
            ctx.check_cancelled(force=True)
            ids = [row[0] for row in db.query(IfcElementModel.id).filter(IfcElementModel.model_id == model_id)
                   .order_by(IfcElementModel.id).limit(DELETE_BATCH).all()]
            if not ids:
                break
            links += db.query(ActivityIfcElementModel).filter(ActivityIfcElementModel.ifc_element_id.in_(ids)) \
                .delete(synchronize_session=False)
            db.query(IfcElementModel).filter(IfcElementModel.id.in_(ids)).delete(synchronize_session=False)
            db.commit()
            deleted += len(ids)
            ctx.progress(5 + deleted / max(total, 1) * 85, f"Removidos {deleted} de {total} elementos")
        ctx.check_cancelled(force=True)
        path = safe_to_delete_file(db, model, Path(uploads_dir))
        file_deleted = False
        if path is not None and path.exists():
            path.unlink()
            file_deleted = True
        model.status = "deleted"
        model.element_count = 0
        model.progress = 100
        model.is_current = False
        model.processing_message = "Revisão removida"
        db.commit()
    ctx.progress(100, "Revisão removida", force=True)
    return {"model_id": model_id, "elements_deleted": deleted, "links_deleted": links, "file_deleted": file_deleted}


def on_delete_aborted(db: Session, *, job_id: str, params: dict, status: str) -> None:
    """A remoção não terminou: a revisão permanece oculta e pode ser removida de novo."""
    model = db.get(IfcModelModel, params.get("model_id"))
    if model is None or model.status != "deleting":
        return
    model.processing_message = (f"Remoção não concluída ({status}). Solicite a remoção novamente para retomar.")[:255]
    db.commit()

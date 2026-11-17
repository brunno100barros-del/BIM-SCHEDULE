"""Tarefa de processamento IFC (executada em processo separado)."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.jobs.context import JobCancelled, JobContext
from app.models.ifc import IfcElementModel, IfcModelModel
from app.modules.ifc.parser import parse_ifc_and_extract

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

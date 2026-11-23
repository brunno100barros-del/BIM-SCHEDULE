"""Tarefa ``ifc.quantities``: calcula e grava os quantitativos de uma revisão IFC (processo separado)."""
from __future__ import annotations

import json

from sqlalchemy.orm import Session

from app.jobs.context import JobCancelled, JobContext
from app.models.ifc import IfcElementModel, IfcModelModel
from app.models.takeoff import IfcElementTakeoff, IfcTakeoffRun
from app.modules.takeoff.extractor import compute_takeoff

BATCH = 1000


def _set_run(db: Session, model_id: int, **fields) -> None:
    run = db.query(IfcTakeoffRun).filter(IfcTakeoffRun.model_id == model_id).first()
    if run is None:
        run = IfcTakeoffRun(model_id=model_id)
        db.add(run)
    for k, v in fields.items():
        setattr(run, k, v)
    db.commit()


def quantities_job(ctx: JobContext, *, model_id: int) -> dict:
    with ctx.session() as db:
        model = db.get(IfcModelModel, model_id)
        if model is None:
            raise ValueError(f"Revisão IFC {model_id} não encontrada.")
        if model.status != "completed":
            raise ValueError("A revisão IFC precisa estar processada antes do cálculo de quantitativos.")
        path = model.file_path
        _set_run(db, model_id, status="processing", job_id=ctx.job_id, error_message=None)
    try:
        result = compute_takeoff(path, on_progress=ctx.progress, check_cancel=ctx.check_cancelled)
        ctx.check_cancelled(force=True)
        with ctx.session() as db:
            ids = dict(db.query(IfcElementModel.global_id, IfcElementModel.id)
                       .filter(IfcElementModel.model_id == model_id).all())
            db.query(IfcElementTakeoff).filter(IfcElementTakeoff.model_id == model_id).delete()
            db.commit()
            batch = []
            for row in result["rows"]:
                data = {k: v for k, v in row.items() if k != "sources"}
                batch.append(IfcElementTakeoff(model_id=model_id, element_id=ids.get(row["global_id"]),
                                               sources_json=json.dumps(row["sources"], ensure_ascii=False), **data))
                if len(batch) >= BATCH:
                    db.bulk_save_objects(batch); db.commit(); batch.clear()
            if batch:
                db.bulk_save_objects(batch); db.commit()
            _set_run(db, model_id, status="completed",
                     summary_json=json.dumps(result["summary"], ensure_ascii=False, default=str))
    except JobCancelled:
        with ctx.session() as db:
            db.query(IfcElementTakeoff).filter(IfcElementTakeoff.model_id == model_id).delete()
            _set_run(db, model_id, status="cancelled", error_message="Cálculo cancelado.")
        raise
    except Exception as exc:
        with ctx.session() as db:
            db.query(IfcElementTakeoff).filter(IfcElementTakeoff.model_id == model_id).delete()
            _set_run(db, model_id, status="failed", error_message=str(exc)[:2000])
        raise
    ctx.progress(100, "Quantitativos calculados", force=True)
    return {"model_id": model_id, "elements": result["summary"]["elements"], "included": result["summary"]["included"]}


def on_quantities_aborted(db: Session, *, job_id: str, params: dict, status: str) -> None:
    model_id = params.get("model_id")
    run = db.query(IfcTakeoffRun).filter(IfcTakeoffRun.model_id == model_id).first()
    if run is None or run.status in ("completed",):
        return
    db.query(IfcElementTakeoff).filter(IfcElementTakeoff.model_id == model_id).delete()
    run.status = "failed" if status != "cancelled" else "cancelled"
    run.error_message = f"Tarefa {job_id} terminou com status '{status}'."
    db.commit()

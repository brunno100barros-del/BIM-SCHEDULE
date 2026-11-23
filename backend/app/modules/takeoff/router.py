"""Rotas de quantitativos (``/takeoff``) e do gerador de cronograma (``/schedule-generator``)."""
from __future__ import annotations

from typing import Literal, Optional

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.errors import AppError
from app.core.runtime import Runtime, get_runtime
from app.models.ifc import IfcModelModel
from app.models.takeoff import IfcElementTakeoff, IfcTakeoffRun, ScheduleService
from app.modules.ifc import revisions
from app.modules.takeoff import service
from app.modules.takeoff.catalog import QUANTITY_BASES

takeoff_router = APIRouter()
generator_router = APIRouter()


@takeoff_router.post("/model/{model_id}", status_code=status.HTTP_202_ACCEPTED)
def start_takeoff(model_id: int, db: Session = Depends(get_db), runtime: Runtime = Depends(get_runtime)):
    model = revisions.get_revision_or_404(db, model_id)
    if model.status != "completed":
        raise AppError(409, "O modelo precisa estar processado antes do cálculo de quantitativos.", code="ifc_model_not_ready")
    run = db.query(IfcTakeoffRun).filter(IfcTakeoffRun.model_id == model_id).first()
    if run is not None and run.status in ("queued", "processing") and run.job_id:
        job = runtime.jobs.get(run.job_id) if hasattr(runtime.jobs, "get") else None
        if job is None or job.get("status") in ("queued", "running", "cancelling"):
            return {"model_id": model_id, "job_id": run.job_id, "status": run.status, "message": "Cálculo já em andamento."}
    job = runtime.jobs.submit("ifc.quantities", {"model_id": model_id}, project_id=model.project_id)
    if run is None:
        run = IfcTakeoffRun(model_id=model_id)
        db.add(run)
    run.status = "queued"
    run.job_id = job["id"]
    run.error_message = None
    db.commit()
    return {"model_id": model_id, "job_id": job["id"], "status": "queued", "message": "Cálculo de quantitativos na fila."}


@takeoff_router.get("/model/{model_id}")
def get_takeoff(model_id: int, db: Session = Depends(get_db)):
    model = revisions.get_revision_or_404(db, model_id)
    run = db.query(IfcTakeoffRun).filter(IfcTakeoffRun.model_id == model_id).first()
    data = service.run_to_dict(run, model)
    if run is not None and run.status == "completed":
        data["totals"] = service.takeoff_summary(db, model_id)
    return data


@takeoff_router.get("/model/{model_id}/elements")
def list_takeoff_elements(model_id: int, skip: int = 0, limit: int = Query(200), ifc_type: Optional[str] = None,
                          db: Session = Depends(get_db)):
    revisions.get_revision_or_404(db, model_id)
    q = db.query(IfcElementTakeoff).filter(IfcElementTakeoff.model_id == model_id)
    if ifc_type:
        q = q.filter(IfcElementTakeoff.mapping_type == ifc_type)
    total = q.count()
    rows = q.order_by(IfcElementTakeoff.id).offset(max(0, skip)).limit(max(1, min(limit, 2000))).all()
    import json
    items = []
    for r in rows:
        items.append({c: getattr(r, c) for c in ("id", "element_id", "global_id", "name", "ifc_type", "mapping_type",
                                                 "storey_name", "z_min_m", "material", "material_class", "volume_m3",
                                                 "area_m2", "length_m", "weight_kg", "count", "geometry_ok", "excluded",
                                                 "excluded_reason")} | {"sources": json.loads(r.sources_json or "{}")})
    return {"total": total, "items": items}


@takeoff_router.get("/project/{project_id}/models")
def project_takeoff_status(project_id: int, db: Session = Depends(get_db)):
    return service.project_models_status(db, project_id)


# --------------------------------------------------------------------------- gerador
class ServiceUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    productivity_per_day: Optional[float] = Field(default=None, gt=0)
    clear_productivity: bool = False
    productivity_note: Optional[str] = None
    default_duration_days: Optional[float] = Field(default=None, ge=0)
    is_active: Optional[bool] = None
    include_by_default: Optional[bool] = None
    ifc_types: Optional[str] = None
    quantity_basis: Optional[Literal["volume_m3", "area_m2", "length_m", "weight_kg", "count"]] = None
    predecessors: Optional[str] = None
    after_previous_level: Optional[str] = None
    sequence: Optional[int] = None


class GeneratorRequest(BaseModel):
    model_ids: list[int]
    level_mode: Literal["auto", "storey", "elevation"] = "auto"
    band_height_m: float = Field(default=3.0, gt=0, le=100)


class ActivityOverride(BaseModel):
    key: str
    include: Optional[bool] = None
    name: Optional[str] = None
    duration: Optional[float] = Field(default=None, ge=0)


class ApplyRequest(GeneratorRequest):
    overrides: list[ActivityOverride] = []
    replace_previous: bool = True
    run_cpm: bool = True


@generator_router.get("/project/{project_id}/services")
def list_services(project_id: int, db: Session = Depends(get_db)):
    return [service.service_to_dict(s) for s in service.ensure_services(db, project_id)]


@generator_router.post("/project/{project_id}/services/reset")
def reset_services(project_id: int, db: Session = Depends(get_db)):
    return [service.service_to_dict(s) for s in service.reset_services(db, project_id)]


@generator_router.put("/services/{service_id}")
def update_service(service_id: int, data: ServiceUpdate, db: Session = Depends(get_db)):
    svc = db.get(ScheduleService, service_id)
    if svc is None:
        raise AppError(404, "Serviço não encontrado.", code="service_not_found")
    values = data.model_dump(exclude_unset=True)
    if values.pop("clear_productivity", False):
        svc.productivity_per_day = None
    for k, v in values.items():
        setattr(svc, k, v)
    db.commit()
    db.refresh(svc)
    return service.service_to_dict(svc)


@generator_router.get("/units")
def units():
    return QUANTITY_BASES


@generator_router.post("/project/{project_id}/preview")
def preview(project_id: int, data: GeneratorRequest, db: Session = Depends(get_db)):
    proposal = service.preview(db, project_id, data.model_ids, data.level_mode, data.band_height_m)
    for a in proposal["activities"]:  # a lista de elementos fica no servidor (a resposta seria grande)
        a.pop("element_ids", None)
        a.pop("element_global_ids", None)
    return proposal


@generator_router.post("/project/{project_id}/apply", status_code=status.HTTP_201_CREATED)
def apply(project_id: int, data: ApplyRequest, db: Session = Depends(get_db)):
    return service.apply(db, project_id, data.model_ids, data.level_mode, data.band_height_m,
                         [o.model_dump(exclude_unset=True) for o in data.overrides], data.replace_previous, data.run_cpm)


@generator_router.get("/project/{project_id}/generations")
def list_generations(project_id: int, db: Session = Depends(get_db)):
    return service.generations(db, project_id)


@generator_router.get("/project/{project_id}/activity-flags")
def activity_flags(project_id: int, db: Session = Depends(get_db)):
    return service.generated_activity_flags(db, project_id)

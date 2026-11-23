"""Operações de banco do módulo de quantitativos e do gerador de cronograma."""
from __future__ import annotations

import json
from collections import defaultdict
from typing import Optional

from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models.ifc import IfcModelModel
from app.models.project import ProjectModel
from app.models.takeoff import (IfcElementTakeoff, IfcTakeoffRun, ScheduleGeneratedActivity, ScheduleGeneration,
                                ScheduleService)
from app.models.wbs_activity import ActivityIfcElementModel, ActivityModel, PrecedenceModel, WbsNodeModel
from app.modules.ifc import revisions
from app.modules.planning.service import calculate_project_cpm
from app.modules.takeoff.catalog import DEFAULT_SERVICES, QUANTITY_BASES
from app.modules.takeoff.generator import build_proposal

SERVICE_FIELDS = ("code", "name", "discipline", "sequence", "quantity_basis", "ifc_types", "quantity_ifc_types",
                  "material_class", "predecessors", "after_previous_level", "productivity_per_day",
                  "productivity_note", "default_duration_days", "is_active", "include_by_default")


def service_to_dict(s: ScheduleService) -> dict:
    data = {f: getattr(s, f) for f in SERVICE_FIELDS}
    data["id"] = s.id
    data["project_id"] = s.project_id
    data["unit"] = QUANTITY_BASES.get(s.quantity_basis, s.quantity_basis)
    return data


def get_project_or_404(db: Session, project_id: int) -> ProjectModel:
    project = db.get(ProjectModel, project_id)
    if project is None:
        raise AppError(404, "Projeto não encontrado.", code="project_not_found")
    return project


def ensure_services(db: Session, project_id: int) -> list[ScheduleService]:
    get_project_or_404(db, project_id)
    items = db.query(ScheduleService).filter(ScheduleService.project_id == project_id).order_by(ScheduleService.sequence).all()
    if items:
        return items
    for d in DEFAULT_SERVICES:
        db.add(ScheduleService(project_id=project_id, **{**{"default_duration_days": 5.0, "is_active": True,
                                                            "include_by_default": True}, **d}))
    db.commit()
    return db.query(ScheduleService).filter(ScheduleService.project_id == project_id).order_by(ScheduleService.sequence).all()


def reset_services(db: Session, project_id: int) -> list[ScheduleService]:
    get_project_or_404(db, project_id)
    db.query(ScheduleService).filter(ScheduleService.project_id == project_id).delete()
    db.commit()
    return ensure_services(db, project_id)


def run_to_dict(run: Optional[IfcTakeoffRun], model: IfcModelModel) -> dict:
    return {
        "model_id": model.id, "filename": model.filename, "model_status": model.status,
        "status": run.status if run else "none", "job_id": run.job_id if run else None,
        "error_message": run.error_message if run else None,
        "summary": json.loads(run.summary_json) if run and run.summary_json else None,
        "updated_at": run.updated_at.isoformat() if run and run.updated_at else None,
    }


def project_models_status(db: Session, project_id: int) -> list[dict]:
    get_project_or_404(db, project_id)
    models = revisions.visible_revisions(db, project_id).filter(IfcModelModel.status == "completed") \
        .order_by(IfcModelModel.id).all()
    runs = {r.model_id: r for r in db.query(IfcTakeoffRun).filter(IfcTakeoffRun.model_id.in_([m.id for m in models])).all()}
    out = []
    for m in models:
        d = run_to_dict(runs.get(m.id), m)
        d["is_current"] = bool(m.is_current)
        d["element_count"] = m.element_count
        out.append(d)
    return out


def takeoff_rows(db: Session, model_ids: list[int]) -> list[dict]:
    cols = ("element_id", "global_id", "ifc_type", "mapping_type", "storey_name", "storey_key", "storey_elevation_m",
            "z_min_m", "material_class", "volume_m3", "area_m2", "length_m", "weight_kg", "count", "excluded")
    q = db.query(*[getattr(IfcElementTakeoff, c) for c in cols]).filter(IfcElementTakeoff.model_id.in_(model_ids))
    return [dict(zip(cols, row)) for row in q.all()]


def takeoff_summary(db: Session, model_id: int) -> dict:
    rows = db.query(IfcElementTakeoff).filter(IfcElementTakeoff.model_id == model_id,
                                              IfcElementTakeoff.excluded.is_(False)).all()
    by_type: dict[str, dict] = defaultdict(lambda: {"count": 0, "volume_m3": 0.0, "area_m2": 0.0, "length_m": 0.0,
                                                    "weight_kg": 0.0, "with_geometry": 0})
    by_storey: dict[str, int] = defaultdict(int)
    for r in rows:
        t = by_type[r.mapping_type]
        t["count"] += 1
        t["with_geometry"] += 1 if r.geometry_ok else 0
        for f in ("volume_m3", "area_m2", "length_m", "weight_kg"):
            t[f] += getattr(r, f) or 0.0
        by_storey[r.storey_name or "(sem pavimento)"] += 1
    return {"by_type": {k: {kk: (round(vv, 3) if isinstance(vv, float) else vv) for kk, vv in v.items()}
                        for k, v in sorted(by_type.items(), key=lambda kv: -kv[1]["count"])},
            "by_storey": dict(sorted(by_storey.items(), key=lambda kv: -kv[1]))}


def _check_models(db: Session, project_id: int, model_ids: list[int]) -> list[int]:
    if not model_ids:
        raise AppError(422, "Selecione ao menos um modelo IFC.", code="generator_no_models")
    valid = {m.id for m in revisions.visible_revisions(db, project_id).filter(IfcModelModel.id.in_(model_ids)).all()}
    missing = [m for m in model_ids if m not in valid]
    if missing:
        raise AppError(404, f"Modelos não pertencem ao projeto: {missing}", code="ifc_model_not_found")
    done = {r.model_id for r in db.query(IfcTakeoffRun).filter(IfcTakeoffRun.model_id.in_(model_ids),
                                                                IfcTakeoffRun.status == "completed").all()}
    pending = [m for m in model_ids if m not in done]
    if pending:
        raise AppError(409, "Calcule os quantitativos dos modelos selecionados antes de gerar o cronograma.",
                       code="takeoff_not_ready", details={"model_ids": pending})
    return model_ids


def preview(db: Session, project_id: int, model_ids: list[int], level_mode: str, band_height_m: float) -> dict:
    _check_models(db, project_id, model_ids)
    services = [service_to_dict(s) for s in ensure_services(db, project_id)]
    return build_proposal(takeoff_rows(db, model_ids), services, level_mode=level_mode, band_height_m=band_height_m)


def apply(db: Session, project_id: int, model_ids: list[int], level_mode: str, band_height_m: float,
          overrides: list[dict], replace_previous: bool, run_cpm: bool) -> dict:
    project = get_project_or_404(db, project_id)
    proposal = preview(db, project_id, model_ids, level_mode, band_height_m)
    by_key = {o["key"]: o for o in overrides or []}
    selected = []
    for act in proposal["activities"]:
        o = by_key.get(act["key"], {})
        include = o.get("include", act["include"])
        if not include:
            continue
        if o.get("name"):
            act["name"] = str(o["name"])[:255]
        if o.get("duration") is not None:
            duration = float(o["duration"])
            if duration < 0:
                raise AppError(422, "Duração não pode ser negativa.", code="invalid_duration")
            if duration != act["duration"]:
                act["duration"] = duration
                act["provisional"] = False
                act["provisional_reason"] = None
        selected.append(act)
    if not selected:
        raise AppError(422, "Nenhuma atividade selecionada.", code="generator_empty")

    removed = 0
    if replace_previous:
        previous = db.query(ScheduleGeneration).filter(ScheduleGeneration.project_id == project_id).all()
        for gen in previous:
            act_ids = [r.activity_id for r in db.query(ScheduleGeneratedActivity)
                       .filter(ScheduleGeneratedActivity.generation_id == gen.id).all()]
            if act_ids:
                db.query(ActivityIfcElementModel).filter(ActivityIfcElementModel.activity_id.in_(act_ids)).delete(synchronize_session=False)
                db.query(PrecedenceModel).filter((PrecedenceModel.predecessor_id.in_(act_ids)) |
                                                 (PrecedenceModel.successor_id.in_(act_ids))).delete(synchronize_session=False)
                removed += db.query(ActivityModel).filter(ActivityModel.id.in_(act_ids)).delete(synchronize_session=False)
            summary = json.loads(gen.summary_json or "{}")
            wbs_ids = summary.get("wbs_ids", [])
            if wbs_ids:
                db.query(WbsNodeModel).filter(WbsNodeModel.id.in_(wbs_ids)).delete(synchronize_session=False)
        db.commit()

    number = (db.query(ScheduleGeneration).filter(ScheduleGeneration.project_id == project_id).count() or 0) + 1
    gen = ScheduleGeneration(project_id=project_id, number=number,
                             options_json=json.dumps({"model_ids": model_ids, "level_mode": proposal["level_mode"],
                                                      "band_height_m": band_height_m, "replace_previous": replace_previous}))
    db.add(gen)
    db.flush()
    prefix = f"G{number}-"
    root = WbsNodeModel(project_id=project_id, name=f"Cronograma gerado do IFC (geração {number})", code=f"G{number}",
                        description="Gerado automaticamente por regras (nível × serviço).", sort_order=1000 + number)
    db.add(root)
    db.flush()
    wbs_ids = [root.id]
    level_nodes: dict[str, int] = {}
    for lv in proposal["levels"]:
        if not any(a["level_key"] == lv["key"] for a in selected):
            continue
        node = WbsNodeModel(project_id=project_id, name=lv["name"], code=f"G{number}.{lv['order']:02d}",
                            parent_id=root.id, sort_order=lv["order"])
        db.add(node)
        db.flush()
        level_nodes[lv["key"]] = node.id
        wbs_ids.append(node.id)

    act_ids: dict[str, int] = {}
    links = 0
    for act in selected:
        a = ActivityModel(project_id=project_id, wbs_id=level_nodes.get(act["level_key"]), name=act["name"][:255],
                          code=(prefix + act["code"])[:50], duration=act["duration"], quantity=act["quantity"],
                          unit=act["unit"], productivity=act["productivity"],
                          description=(f"Gerada do IFC: {act['element_count']} elementos; "
                                       f"cobertura da quantidade {act['coverage']:.0%}."
                                       + (f" Duração PROVISÓRIA: {act['provisional_reason']}." if act["provisional"] else "")))
        db.add(a)
        db.flush()
        act_ids[act["key"]] = a.id
        db.add(ScheduleGeneratedActivity(generation_id=gen.id, activity_id=a.id, service_code=act["service_code"],
                                         level_name=act["level_name"], provisional=act["provisional"],
                                         provisional_reason=act["provisional_reason"], quantity_coverage=act["coverage"]))
        for eid in sorted(set(act["element_ids"])):
            db.add(ActivityIfcElementModel(activity_id=a.id, ifc_element_id=eid))
            links += 1
    precedences = 0
    for p in proposal["precedences"]:
        if p["pred_key"] in act_ids and p["succ_key"] in act_ids:
            db.add(PrecedenceModel(predecessor_id=act_ids[p["pred_key"]], successor_id=act_ids[p["succ_key"]],
                                   relation_type="FS", lag=0.0))
            precedences += 1
    summary = {"activities": len(selected), "precedences": precedences, "element_links": links,
               "provisional": sum(1 for a in selected if a["provisional"]), "removed_previous": removed,
               "wbs_ids": wbs_ids, "level_mode": proposal["level_mode"], "warnings": proposal["warnings"]}
    gen.summary_json = json.dumps(summary, ensure_ascii=False)
    db.commit()
    cpm = None
    if run_cpm:
        try:
            result = calculate_project_cpm(db, project)
            critical = sum(1 for r in (result.get("activities") or {}).values() if r.get("is_critical"))
            cpm = {"status": result.get("status"), "duration": result.get("duration"),
                   "critical_activities": critical, "deadline_feasible": result.get("deadline_feasible"),
                   "project_deadline": result.get("project_deadline")}
        except (ValueError, OverflowError) as exc:
            db.rollback()
            cpm = {"status": "error", "message": str(exc)}
    return {"generation_id": gen.id, "number": number, **{k: v for k, v in summary.items() if k != "wbs_ids"}, "cpm": cpm}


def generations(db: Session, project_id: int) -> list[dict]:
    get_project_or_404(db, project_id)
    out = []
    for g in db.query(ScheduleGeneration).filter(ScheduleGeneration.project_id == project_id).order_by(ScheduleGeneration.id).all():
        summary = json.loads(g.summary_json or "{}")
        summary.pop("wbs_ids", None)
        out.append({"id": g.id, "number": g.number, "created_at": g.created_at.isoformat() if g.created_at else None,
                    "options": json.loads(g.options_json or "{}"), "summary": summary})
    return out


def generated_activity_flags(db: Session, project_id: int) -> dict:
    rows = db.query(ScheduleGeneratedActivity).join(ActivityModel, ActivityModel.id == ScheduleGeneratedActivity.activity_id) \
        .filter(ActivityModel.project_id == project_id).all()
    return {r.activity_id: {"provisional": r.provisional, "reason": r.provisional_reason, "service_code": r.service_code,
                            "coverage": r.quantity_coverage} for r in rows}

"""Orquestração entre a persistência e o motor CPM/PERT.

O cálculo em si fica em :mod:`app.engine.cpm_pert`, que não conhece banco de
dados, HTTP ou IA. Este serviço apenas converte os registros para o formato do
motor e grava os resultados.
"""
from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from app.engine.cpm_pert import analyze_cpm
from app.models.project import ProjectModel
from app.models.wbs_activity import ActivityModel, PrecedenceModel

CPM_RESULT_FIELDS = ("es", "ef", "ls", "lf", "tf", "ff", "is_critical")


def _relation_dict(p: PrecedenceModel) -> dict:
    return {"predecessor_id": p.predecessor_id, "successor_id": p.successor_id,
            "relation_type": p.relation_type, "lag": p.lag}


def project_network(db: Session, project_id: int) -> tuple[list[ActivityModel], list[PrecedenceModel]]:
    acts = db.query(ActivityModel).filter(ActivityModel.project_id == project_id).all()
    ids = [a.id for a in acts]
    if not ids:
        return acts, []
    precs = db.query(PrecedenceModel).filter(
        PrecedenceModel.predecessor_id.in_(ids), PrecedenceModel.successor_id.in_(ids)
    ).all()
    return acts, precs


def ensure_network_is_valid(db: Session, project_id: int, candidate_relation: dict) -> None:
    """Valida a rede com a nova relação (ciclos, atividades inexistentes). Lança ValueError."""
    acts, precs = project_network(db, project_id)
    relations = [_relation_dict(p) for p in precs] + [candidate_relation]
    analyze_cpm([{"id": a.id, "duration": a.duration} for a in acts], relations)


def contract_deadline_days(project: ProjectModel) -> float | None:
    if not (project.start_date and project.end_date):
        return None
    start = date.fromisoformat(project.start_date[:10])
    end = date.fromisoformat(project.end_date[:10])
    if end < start:
        raise ValueError("A data final do projeto é anterior à data inicial.")
    return float((end - start).days)


def calculate_project_cpm(db: Session, project: ProjectModel) -> dict:
    acts, precs = project_network(db, project.id)
    if not acts:
        return {"status": "empty", "message": "Nenhuma atividade encontrada", "results": {}}
    summary = analyze_cpm(
        [{"id": a.id, "duration": a.duration} for a in acts],
        [_relation_dict(p) for p in precs],
        project_deadline=contract_deadline_days(project),
        project_start=0.0,
    )
    by_id = {a.id: a for a in acts}
    for aid, result in summary["activities"].items():
        for field in CPM_RESULT_FIELDS:
            setattr(by_id[aid], field, result[field])
    db.commit()
    return {"status": "success", **summary}

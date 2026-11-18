"""Regras de negócio de projetos, independentes da camada HTTP."""
from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models.ifc import IfcModelModel
from app.models.project import ProjectModel
from app.models.wbs_activity import ActivityModel, PrecedenceModel, WbsNodeModel


def validate_dates(start_value: Optional[str], end_value: Optional[str]) -> None:
    try:
        start = date.fromisoformat(start_value[:10]) if start_value else None
        end = date.fromisoformat(end_value[:10]) if end_value else None
    except ValueError:
        raise AppError(422, "Datas devem utilizar o formato AAAA-MM-DD.", code="invalid_date")
    if start and end and end < start:
        raise AppError(422, "A data final não pode ser anterior à data inicial.", code="invalid_date_range")


def get_project_or_404(db: Session, project_id: int) -> ProjectModel:
    project = db.get(ProjectModel, project_id)
    if not project:
        raise AppError(404, "Projeto não encontrado.", code="project_not_found")
    return project


def duplicate_project(db: Session, project: ProjectModel) -> ProjectModel:
    """Copia o projeto com EAP, atividades e precedências. Avanço e status são reiniciados."""
    new_code = f"{project.code}-DUP"
    count = 1
    while db.query(ProjectModel).filter(ProjectModel.code == new_code).first():
        new_code = f"{project.code}-DUP{count}"
        count += 1
    new_proj = ProjectModel(
        name=f"{project.name} (Cópia)", code=new_code, client=project.client, description=project.description,
        start_date=project.start_date, end_date=project.end_date, status="Planejamento",
    )
    db.add(new_proj)
    db.flush()

    original_nodes = db.query(WbsNodeModel).filter(WbsNodeModel.project_id == project.id).order_by(WbsNodeModel.id).all()
    node_map: dict[int, int] = {}
    pending = list(original_nodes)
    while pending:
        progressed = False
        for old_node in pending[:]:
            if old_node.parent_id is None or old_node.parent_id in node_map:
                clone = WbsNodeModel(
                    project_id=new_proj.id, name=old_node.name, code=old_node.code, description=old_node.description,
                    parent_id=node_map.get(old_node.parent_id), sort_order=old_node.sort_order,
                )
                db.add(clone)
                db.flush()
                node_map[old_node.id] = clone.id
                pending.remove(old_node)
                progressed = True
        if not progressed:
            raise ValueError("A EAP original contém referência circular ou pai inexistente.")

    activity_map: dict[int, int] = {}
    for old in db.query(ActivityModel).filter(ActivityModel.project_id == project.id).all():
        clone = ActivityModel(
            project_id=new_proj.id, wbs_id=node_map.get(old.wbs_id), name=old.name, code=old.code,
            description=old.description, duration=old.duration, quantity=old.quantity, unit=old.unit,
            productivity=old.productivity, optimistic=old.optimistic, most_likely=old.most_likely,
            pessimistic=old.pessimistic, percent_complete=0, status="Não Iniciado",
        )
        db.add(clone)
        db.flush()
        activity_map[old.id] = clone.id

    if activity_map:
        relations = db.query(PrecedenceModel).filter(PrecedenceModel.predecessor_id.in_(activity_map.keys())).all()
        for rel in relations:
            if rel.predecessor_id in activity_map and rel.successor_id in activity_map:
                db.add(PrecedenceModel(
                    predecessor_id=activity_map[rel.predecessor_id], successor_id=activity_map[rel.successor_id],
                    relation_type=rel.relation_type, lag=rel.lag,
                ))
    return new_proj


def remove_orphan_upload_files(db: Session, paths: list[str], uploads_dir: Path) -> int:
    """Apaga arquivos IFC que ficaram sem nenhuma revisão no banco.

    Só considera arquivos diretamente dentro da pasta de uploads; um arquivo ainda citado por
    qualquer revisão restante (de qualquer projeto) é mantido.
    """
    removed = 0
    root = uploads_dir.resolve()
    for raw in paths:
        path = Path(raw)
        try:
            resolved = path.resolve()
        except OSError:
            continue
        if resolved.parent != root or not resolved.is_file():
            continue
        if db.query(IfcModelModel.id).filter(IfcModelModel.file_path == raw).first():
            continue
        resolved.unlink()
        removed += 1
    return removed

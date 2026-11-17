from datetime import date
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.core.database import get_db
from app.models.project import ProjectModel
from app.models.wbs_activity import WbsNodeModel, ActivityModel, PrecedenceModel
from app.schemas.project import ProjectCreate, ProjectUpdate, ProjectResponse

router = APIRouter()

def validate_dates(start_value, end_value):
    try:
        start = date.fromisoformat(start_value[:10]) if start_value else None
        end = date.fromisoformat(end_value[:10]) if end_value else None
    except ValueError:
        raise HTTPException(422, "Datas devem utilizar o formato AAAA-MM-DD.")
    if start and end and end < start:
        raise HTTPException(422, "A data final não pode ser anterior à data inicial.")

@router.get("/", response_model=list[ProjectResponse])
def list_projects(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return db.query(ProjectModel).order_by(ProjectModel.updated_at.desc()).offset(max(skip, 0)).limit(min(max(limit, 1), 500)).all()

@router.post("/", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
def create_project(project_in: ProjectCreate, db: Session = Depends(get_db)):
    validate_dates(project_in.start_date, project_in.end_date)
    existing = db.query(ProjectModel).filter(ProjectModel.code == project_in.code).first()
    if existing:
        raise HTTPException(status_code=409, detail="Projeto com este código já existe.")
    db_project = ProjectModel(**project_in.model_dump())
    db.add(db_project)
    try:
        db.commit()
    except IntegrityError:
        db.rollback(); raise HTTPException(409, "Código de projeto já cadastrado.")
    db.refresh(db_project)
    return db_project

@router.get("/{project_id}", response_model=ProjectResponse)
def get_project(project_id: int, db: Session = Depends(get_db)):
    project = db.query(ProjectModel).filter(ProjectModel.id == project_id).first()
    if not project: raise HTTPException(404, "Projeto não encontrado.")
    return project

@router.put("/{project_id}", response_model=ProjectResponse)
def update_project(project_id: int, project_in: ProjectUpdate, db: Session = Depends(get_db)):
    project = db.query(ProjectModel).filter(ProjectModel.id == project_id).first()
    if not project: raise HTTPException(404, "Projeto não encontrado.")
    values = project_in.model_dump(exclude_unset=True)
    start = values.get("start_date", project.start_date)
    end = values.get("end_date", project.end_date)
    validate_dates(start, end)
    if "code" in values:
        duplicate = db.query(ProjectModel).filter(ProjectModel.code == values["code"], ProjectModel.id != project_id).first()
        if duplicate: raise HTTPException(409, "Projeto com este código já existe.")
    for field, value in values.items(): setattr(project, field, value)
    try: db.commit()
    except IntegrityError:
        db.rollback(); raise HTTPException(409, "Não foi possível salvar o projeto por conflito de dados.")
    db.refresh(project)
    return project

@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(project_id: int, db: Session = Depends(get_db)):
    project = db.query(ProjectModel).filter(ProjectModel.id == project_id).first()
    if not project: raise HTTPException(404, "Projeto não encontrado.")
    db.delete(project); db.commit()

@router.post("/{project_id}/duplicate", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
def duplicate_project(project_id: int, db: Session = Depends(get_db)):
    project = db.query(ProjectModel).filter(ProjectModel.id == project_id).first()
    if not project: raise HTTPException(404, "Projeto não encontrado.")
    new_code = f"{project.code}-DUP"; count = 1
    while db.query(ProjectModel).filter(ProjectModel.code == new_code).first():
        new_code = f"{project.code}-DUP{count}"; count += 1
    new_proj = ProjectModel(name=f"{project.name} (Cópia)", code=new_code, client=project.client,
        description=project.description, start_date=project.start_date, end_date=project.end_date, status="Planejamento")
    try:
        db.add(new_proj); db.flush()
        original_nodes = db.query(WbsNodeModel).filter(WbsNodeModel.project_id == project_id).order_by(WbsNodeModel.id).all()
        node_map = {}
        pending = list(original_nodes)
        while pending:
            progressed = False
            for old_node in pending[:]:
                if old_node.parent_id is None or old_node.parent_id in node_map:
                    clone = WbsNodeModel(project_id=new_proj.id, name=old_node.name, code=old_node.code,
                        description=old_node.description, parent_id=node_map.get(old_node.parent_id), sort_order=old_node.sort_order)
                    db.add(clone); db.flush(); node_map[old_node.id] = clone.id
                    pending.remove(old_node); progressed = True
            if not progressed:
                raise ValueError("A EAP original contém referência circular ou pai inexistente.")
        original_activities = db.query(ActivityModel).filter(ActivityModel.project_id == project_id).all()
        activity_map = {}
        for old in original_activities:
            clone = ActivityModel(
                project_id=new_proj.id, wbs_id=node_map.get(old.wbs_id), name=old.name, code=old.code,
                description=old.description, duration=old.duration, quantity=old.quantity, unit=old.unit,
                productivity=old.productivity, optimistic=old.optimistic, most_likely=old.most_likely,
                pessimistic=old.pessimistic, percent_complete=0, status="Não Iniciado",
            )
            db.add(clone); db.flush(); activity_map[old.id] = clone.id
        original_relations = db.query(PrecedenceModel).filter(
            PrecedenceModel.predecessor_id.in_(activity_map.keys()) if activity_map else False
        ).all() if activity_map else []
        for old_relation in original_relations:
            if old_relation.predecessor_id in activity_map and old_relation.successor_id in activity_map:
                db.add(PrecedenceModel(predecessor_id=activity_map[old_relation.predecessor_id],
                    successor_id=activity_map[old_relation.successor_id], relation_type=old_relation.relation_type, lag=old_relation.lag))
        db.commit(); db.refresh(new_proj)
    except Exception:
        db.rollback()
        raise HTTPException(400, "Não foi possível duplicar a estrutura do projeto.")
    return new_proj

from fastapi import APIRouter, Depends, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.errors import AppError
from app.core.logging import get_logger
from app.models.project import ProjectModel
from app.modules.projects import service
from app.modules.projects.schemas import ProjectCreate, ProjectResponse, ProjectUpdate

router = APIRouter()
logger = get_logger("projects")


@router.get("/", response_model=list[ProjectResponse])
def list_projects(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return (db.query(ProjectModel).order_by(ProjectModel.updated_at.desc())
            .offset(max(skip, 0)).limit(min(max(limit, 1), 500)).all())


@router.post("/", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
def create_project(project_in: ProjectCreate, db: Session = Depends(get_db)):
    service.validate_dates(project_in.start_date, project_in.end_date)
    if db.query(ProjectModel).filter(ProjectModel.code == project_in.code).first():
        raise AppError(409, "Projeto com este código já existe.", code="project_code_conflict")
    db_project = ProjectModel(**project_in.model_dump())
    db.add(db_project)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise AppError(409, "Código de projeto já cadastrado.", code="project_code_conflict")
    db.refresh(db_project)
    logger.info("Projeto %s (%s) criado.", db_project.id, db_project.code)
    return db_project


@router.get("/{project_id}", response_model=ProjectResponse)
def get_project(project_id: int, db: Session = Depends(get_db)):
    return service.get_project_or_404(db, project_id)


@router.put("/{project_id}", response_model=ProjectResponse)
def update_project(project_id: int, project_in: ProjectUpdate, db: Session = Depends(get_db)):
    project = service.get_project_or_404(db, project_id)
    values = project_in.model_dump(exclude_unset=True)
    service.validate_dates(values.get("start_date", project.start_date), values.get("end_date", project.end_date))
    if "code" in values:
        duplicate = db.query(ProjectModel).filter(ProjectModel.code == values["code"], ProjectModel.id != project_id).first()
        if duplicate:
            raise AppError(409, "Projeto com este código já existe.", code="project_code_conflict")
    for field, value in values.items():
        setattr(project, field, value)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise AppError(409, "Não foi possível salvar o projeto por conflito de dados.", code="conflict")
    db.refresh(project)
    return project


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(project_id: int, db: Session = Depends(get_db)):
    project = service.get_project_or_404(db, project_id)
    db.delete(project)
    db.commit()
    logger.info("Projeto %s excluído.", project_id)


@router.post("/{project_id}/duplicate", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
def duplicate_project(project_id: int, db: Session = Depends(get_db)):
    project = service.get_project_or_404(db, project_id)
    try:
        new_proj = service.duplicate_project(db, project)
        db.commit()
        db.refresh(new_proj)
    except Exception:
        db.rollback()
        logger.exception("Falha ao duplicar o projeto %s", project_id)
        raise AppError(400, "Não foi possível duplicar a estrutura do projeto.", code="duplicate_failed")
    return new_proj

from datetime import date
from typing import Optional
import math
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.project import ProjectModel
from app.models.wbs_activity import ActivityModel, PrecedenceModel, WbsNodeModel, ActivityIfcElementModel
from app.models.ifc import IfcElementModel
from app.engine.cpm_pert import analyze_cpm

router = APIRouter()

class ActivityCreate(BaseModel):
    project_id: int
    wbs_id: Optional[int] = None
    name: str = Field(min_length=1, max_length=255)
    code: str = Field(min_length=1, max_length=50)
    description: Optional[str] = None
    duration: float = Field(default=1.0, ge=0)
    quantity: Optional[float] = Field(default=None, ge=0)
    unit: Optional[str] = None
    productivity: Optional[float] = Field(default=None, gt=0)
    optimistic: Optional[float] = Field(default=None, ge=0)
    most_likely: Optional[float] = Field(default=None, ge=0)
    pessimistic: Optional[float] = Field(default=None, ge=0)

class ActivityUpdate(BaseModel):
    wbs_id: Optional[int] = None
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    code: Optional[str] = Field(default=None, min_length=1, max_length=50)
    description: Optional[str] = None
    duration: Optional[float] = Field(default=None, ge=0)
    quantity: Optional[float] = Field(default=None, ge=0)
    unit: Optional[str] = None
    productivity: Optional[float] = Field(default=None, gt=0)
    percent_complete: Optional[float] = Field(default=None, ge=0, le=100)
    status: Optional[str] = None

class PrecedenceCreate(BaseModel):
    predecessor_id: int
    successor_id: int
    relation_type: str = "FS"
    lag: float = 0.0

class WbsCreate(BaseModel):
    project_id: int
    name: str = Field(min_length=1, max_length=255)
    code: str = Field(min_length=1, max_length=50)
    description: Optional[str] = None
    parent_id: Optional[int] = None
    sort_order: int = 0

class WbsUpdate(BaseModel):
    name: Optional[str] = None
    code: Optional[str] = None
    description: Optional[str] = None
    parent_id: Optional[int] = None
    sort_order: Optional[int] = None

class ElementLink(BaseModel):
    ifc_element_id: int

@router.get("/project/{project_id}")
def list_activities(project_id: int, db: Session = Depends(get_db)):
    if not db.query(ProjectModel).filter(ProjectModel.id == project_id).first():
        raise HTTPException(404, "Projeto não encontrado.")
    return db.query(ActivityModel).filter(ActivityModel.project_id == project_id).order_by(ActivityModel.id).all()

@router.post("/", status_code=status.HTTP_201_CREATED)
def create_activity(act_in: ActivityCreate, db: Session = Depends(get_db)):
    if not db.query(ProjectModel).filter(ProjectModel.id == act_in.project_id).first():
        raise HTTPException(404, "Projeto não encontrado.")
    if act_in.wbs_id is not None:
        node = db.query(WbsNodeModel).filter(WbsNodeModel.id == act_in.wbs_id, WbsNodeModel.project_id == act_in.project_id).first()
        if not node:
            raise HTTPException(400, "Nó da EAP não pertence ao projeto informado.")
    act = ActivityModel(**act_in.model_dump())
    db.add(act)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(409, "Não foi possível cadastrar a atividade. Verifique código e dados.")
    db.refresh(act)
    return act

@router.put("/{act_id}")
def update_activity(act_id: int, data: ActivityUpdate, db: Session = Depends(get_db)):
    act = db.query(ActivityModel).filter(ActivityModel.id == act_id).first()
    if not act:
        raise HTTPException(404, "Atividade não encontrada.")
    values = data.model_dump(exclude_unset=True)
    if values.get("wbs_id") is not None:
        node = db.query(WbsNodeModel).filter(WbsNodeModel.id == values["wbs_id"], WbsNodeModel.project_id == act.project_id).first()
        if not node:
            raise HTTPException(400, "Nó da EAP não pertence ao projeto da atividade.")
    for key, value in values.items():
        setattr(act, key, value)
    db.commit(); db.refresh(act)
    return act

@router.delete("/{act_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_activity(act_id: int, db: Session = Depends(get_db)):
    act = db.query(ActivityModel).filter(ActivityModel.id == act_id).first()
    if not act:
        raise HTTPException(status_code=404, detail="Atividade não encontrada")
    db.delete(act); db.commit()

@router.get("/project/{project_id}/precedences")
def list_precedences(project_id: int, db: Session = Depends(get_db)):
    ids = [a.id for a in db.query(ActivityModel.id).filter(ActivityModel.project_id == project_id).all()]
    if not ids:
        return []
    return db.query(PrecedenceModel).filter(PrecedenceModel.predecessor_id.in_(ids), PrecedenceModel.successor_id.in_(ids)).all()

@router.post("/precedences", status_code=status.HTTP_201_CREATED)
def create_precedence(data: PrecedenceCreate, db: Session = Depends(get_db)):
    relation = data.relation_type.upper()
    if relation not in {"FS", "SS", "FF", "SF"}:
        raise HTTPException(422, "Tipo de relação deve ser FS, SS, FF ou SF.")
    predecessor = db.query(ActivityModel).filter(ActivityModel.id == data.predecessor_id).first()
    successor = db.query(ActivityModel).filter(ActivityModel.id == data.successor_id).first()
    if not predecessor or not successor:
        raise HTTPException(404, "Atividade predecessora ou sucessora não encontrada.")
    if predecessor.project_id != successor.project_id:
        raise HTTPException(400, "As atividades precisam pertencer ao mesmo projeto.")
    if predecessor.id == successor.id:
        raise HTTPException(400, "Uma atividade não pode preceder a si mesma.")
    # Testa a rede incluindo a nova relação para impedir ciclos.
    current = db.query(PrecedenceModel).filter(PrecedenceModel.predecessor_id.in_([a.id for a in db.query(ActivityModel.id).filter(ActivityModel.project_id == predecessor.project_id).all()])).all()
    candidate = [{"predecessor_id": p.predecessor_id, "successor_id": p.successor_id, "relation_type": p.relation_type, "lag": p.lag} for p in current]
    candidate.append({**data.model_dump(), "relation_type": relation})
    acts = db.query(ActivityModel).filter(ActivityModel.project_id == predecessor.project_id).all()
    try:
        analyze_cpm([{"id": a.id, "duration": a.duration} for a in acts], candidate)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    prec = PrecedenceModel(**{**data.model_dump(), "relation_type": relation})
    db.add(prec); db.commit(); db.refresh(prec)
    return prec

@router.delete("/precedences/{precedence_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_precedence(precedence_id: int, db: Session = Depends(get_db)):
    prec = db.query(PrecedenceModel).filter(PrecedenceModel.id == precedence_id).first()
    if not prec:
        raise HTTPException(404, "Precedência não encontrada.")
    db.delete(prec); db.commit()

@router.post("/project/{project_id}/calculate-cpm")
def run_cpm(project_id: int, db: Session = Depends(get_db)):
    project = db.query(ProjectModel).filter(ProjectModel.id == project_id).first()
    if not project:
        raise HTTPException(404, "Projeto não encontrado.")
    acts = db.query(ActivityModel).filter(ActivityModel.project_id == project_id).all()
    if not acts:
        return {"status": "empty", "message": "Nenhuma atividade encontrada", "results": {}}
    ids = [a.id for a in acts]
    precs = db.query(PrecedenceModel).filter(PrecedenceModel.predecessor_id.in_(ids), PrecedenceModel.successor_id.in_(ids)).all()
    try:
        deadline = None
        if project.start_date and project.end_date:
            start = date.fromisoformat(project.start_date[:10])
            end = date.fromisoformat(project.end_date[:10])
            if end < start:
                raise ValueError("A data final do projeto é anterior à data inicial.")
            deadline = float((end - start).days)
        summary = analyze_cpm(
            [{"id": a.id, "duration": a.duration} for a in acts],
            [{"predecessor_id": p.predecessor_id, "successor_id": p.successor_id, "relation_type": p.relation_type, "lag": p.lag} for p in precs],
            project_deadline=deadline,
            project_start=0.0,
        )
        for aid, result in summary["activities"].items():
            act = next(a for a in acts if a.id == aid)
            for field in ("es", "ef", "ls", "lf", "tf", "ff", "is_critical"):
                setattr(act, field, result[field])
        db.commit()
        return {"status": "success", **summary}
    except (ValueError, OverflowError) as exc:
        db.rollback()
        raise HTTPException(400, str(exc))

@router.get("/project/{project_id}/wbs")
def list_wbs(project_id: int, db: Session = Depends(get_db)):
    if not db.query(ProjectModel).filter(ProjectModel.id == project_id).first():
        raise HTTPException(404, "Projeto não encontrado.")
    return db.query(WbsNodeModel).filter(WbsNodeModel.project_id == project_id).order_by(WbsNodeModel.sort_order, WbsNodeModel.id).all()

@router.post("/wbs", status_code=status.HTTP_201_CREATED)
def create_wbs(data: WbsCreate, db: Session = Depends(get_db)):
    if not db.query(ProjectModel).filter(ProjectModel.id == data.project_id).first():
        raise HTTPException(404, "Projeto não encontrado.")
    if data.parent_id is not None:
        parent = db.query(WbsNodeModel).filter(WbsNodeModel.id == data.parent_id, WbsNodeModel.project_id == data.project_id).first()
        if not parent:
            raise HTTPException(400, "O nó pai não pertence ao projeto.")
    node = WbsNodeModel(**data.model_dump()); db.add(node); db.commit(); db.refresh(node)
    return node

@router.put("/wbs/{node_id}")
def update_wbs(node_id: int, data: WbsUpdate, db: Session = Depends(get_db)):
    node = db.query(WbsNodeModel).filter(WbsNodeModel.id == node_id).first()
    if not node:
        raise HTTPException(404, "Nó da EAP não encontrado.")
    values = data.model_dump(exclude_unset=True)
    if values.get("parent_id") is not None:
        if values["parent_id"] == node_id:
            raise HTTPException(400, "Um nó não pode ser pai de si mesmo.")
        parent = db.query(WbsNodeModel).filter(WbsNodeModel.id == values["parent_id"], WbsNodeModel.project_id == node.project_id).first()
        if not parent:
            raise HTTPException(400, "O nó pai não pertence ao projeto.")
        # Impede criar ciclos na hierarquia ao mover um nó para dentro de um descendente.
        cursor = parent
        visited = set()
        while cursor is not None:
            if cursor.id == node_id:
                raise HTTPException(400, "A alteração criaria um ciclo na EAP.")
            if cursor.id in visited:
                raise HTTPException(400, "A hierarquia atual da EAP contém um ciclo.")
            visited.add(cursor.id)
            cursor = db.query(WbsNodeModel).filter(WbsNodeModel.id == cursor.parent_id).first() if cursor.parent_id else None
    for key, value in values.items(): setattr(node, key, value)
    db.commit(); db.refresh(node); return node

@router.delete("/wbs/{node_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_wbs(node_id: int, db: Session = Depends(get_db)):
    node = db.query(WbsNodeModel).filter(WbsNodeModel.id == node_id).first()
    if not node: raise HTTPException(404, "Nó da EAP não encontrado.")
    db.delete(node); db.commit()

@router.post("/{act_id}/ifc-elements", status_code=status.HTTP_201_CREATED)
def link_ifc_element(act_id: int, data: ElementLink, db: Session = Depends(get_db)):
    act = db.query(ActivityModel).filter(ActivityModel.id == act_id).first()
    element = db.query(IfcElementModel).filter(IfcElementModel.id == data.ifc_element_id).first()
    if not act or not element: raise HTTPException(404, "Atividade ou elemento IFC não encontrado.")
    from app.models.ifc import IfcModelModel
    model = db.query(IfcModelModel).filter(IfcModelModel.id == element.model_id).first()
    if not model or model.project_id != act.project_id: raise HTTPException(400, "O elemento IFC não pertence ao projeto da atividade.")
    link = db.query(ActivityIfcElementModel).filter_by(activity_id=act_id, ifc_element_id=element.id).first()
    if not link:
        link = ActivityIfcElementModel(activity_id=act_id, ifc_element_id=element.id); db.add(link); db.commit(); db.refresh(link)
    return {"id": link.id, "activity_id": act_id, "ifc_element_id": element.id, "global_id": element.global_id}

@router.get("/{act_id}/ifc-elements")
def list_linked_elements(act_id: int, db: Session = Depends(get_db)):
    if not db.query(ActivityModel).filter(ActivityModel.id == act_id).first(): raise HTTPException(404, "Atividade não encontrada.")
    return db.query(IfcElementModel).join(ActivityIfcElementModel, ActivityIfcElementModel.ifc_element_id == IfcElementModel.id).filter(ActivityIfcElementModel.activity_id == act_id).all()

@router.delete("/{act_id}/ifc-elements/{element_id}", status_code=status.HTTP_204_NO_CONTENT)
def unlink_ifc_element(act_id: int, element_id: int, db: Session = Depends(get_db)):
    link = db.query(ActivityIfcElementModel).filter_by(activity_id=act_id, ifc_element_id=element_id).first()
    if not link: raise HTTPException(404, "Vínculo Activity-IFC não encontrado.")
    db.delete(link); db.commit()

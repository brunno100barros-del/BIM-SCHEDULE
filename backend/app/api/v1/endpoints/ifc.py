import os
import shutil
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.ifc import IfcModelModel, IfcElementModel
from app.ifc.parser import parse_ifc_and_extract

router = APIRouter()
UPLOAD_DIR = os.path.join(os.getcwd(), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

@router.post("/project/{project_id}/upload")
def upload_ifc(project_id: int, file: UploadFile = File(...), db: Session = Depends(get_db)):
    if not file.filename.lower().endswith(".ifc"):
        raise HTTPException(status_code=400, detail="Apenas arquivos .ifc são suportados.")
    
    file_path = os.path.join(UPLOAD_DIR, f"{project_id}_{file.filename}")
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    db_model = IfcModelModel(project_id=project_id, filename=file.filename, file_path=file_path)
    db.add(db_model)
    db.commit()
    db.refresh(db_model)
    
    parse_ifc_and_extract(file_path, db_model.id, db)
    
    return {"id": db_model.id, "filename": db_model.filename, "message": "Importado e processado com sucesso"}

@router.get("/project/{project_id}/models")
def get_models(project_id: int, db: Session = Depends(get_db)):
    models = db.query(IfcModelModel).filter(IfcModelModel.project_id == project_id).all()
    return models

@router.get("/model/{model_id}/download")
def download_ifc(model_id: int, db: Session = Depends(get_db)):
    model = db.query(IfcModelModel).filter(IfcModelModel.id == model_id).first()
    if not model or not os.path.exists(model.file_path):
        raise HTTPException(status_code=404, detail="Arquivo não encontrado.")
    return FileResponse(model.file_path, media_type="application/octet-stream", filename=model.filename)

@router.get("/model/{model_id}/elements")
def get_elements(model_id: int, skip: int = 0, limit: int = 1000, db: Session = Depends(get_db)):
    elements = db.query(IfcElementModel).filter(IfcElementModel.model_id == model_id).offset(skip).limit(limit).all()
    return elements

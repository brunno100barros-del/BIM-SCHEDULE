from pathlib import Path
from uuid import uuid4
import hashlib
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, BackgroundTasks, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from app.core.database import get_db, SessionLocal
from app.models.project import ProjectModel
from app.models.ifc import IfcModelModel, IfcElementModel
from app.ifc.parser import parse_ifc_and_extract

router = APIRouter()
UPLOAD_DIR = Path(__file__).resolve().parents[4] / "uploads"
MAX_IFC_BYTES = 1024 * 1024 * 1024  # limite inicial de 1 GiB
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def _process_ifc_job(model_id: int):
    db = SessionLocal()
    try:
        model = db.query(IfcModelModel).filter(IfcModelModel.id == model_id).first()
        if not model:
            return
        model.status = "processing"; db.commit()
        try:
            parse_ifc_and_extract(model.file_path, model.id, db)
        except Exception as exc:
            db.rollback()
            model = db.query(IfcModelModel).filter(IfcModelModel.id == model_id).first()
            if model:
                model.status = "failed"
                model.progress = 0
                model.processing_message = "Falha no processamento"
                model.error_message = str(exc)[:2000]
                db.commit()
    finally:
        db.close()


@router.post("/project/{project_id}/upload", status_code=status.HTTP_202_ACCEPTED)
def upload_ifc(project_id: int, background_tasks: BackgroundTasks, file: UploadFile = File(...), db: Session = Depends(get_db)):
    project = db.query(ProjectModel).filter(ProjectModel.id == project_id).first()
    if not project:
        raise HTTPException(404, "Projeto não encontrado.")
    original_name = Path(file.filename or "modelo.ifc").name
    if not original_name.lower().endswith(".ifc"):
        raise HTTPException(400, "Apenas arquivos .ifc são suportados.")
    model_count = db.query(IfcModelModel).filter(IfcModelModel.project_id == project_id).count()
    version = model_count + 1
    safe_name = f"{project_id}_{uuid4().hex}_{original_name}"
    file_path = UPLOAD_DIR / safe_name
    digest = hashlib.sha256()
    size = 0
    try:
        with file_path.open("wb") as output:
            while True:
                chunk = file.file.read(1024 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                if size > MAX_IFC_BYTES:
                    raise HTTPException(413, "Arquivo IFC excede o limite de 1 GiB.")
                digest.update(chunk)
                output.write(chunk)
        if size == 0:
            raise HTTPException(400, "O arquivo enviado está vazio.")
        model = IfcModelModel(
            project_id=project_id, filename=original_name, file_path=str(file_path),
            version=version, status="queued", error_message=None,
        )
        db.add(model); db.commit(); db.refresh(model)
        background_tasks.add_task(_process_ifc_job, model.id)
        return {"id": model.id, "filename": model.filename, "version": model.version,
                "status": model.status, "size_bytes": size, "sha256": digest.hexdigest(),
                "message": "Arquivo recebido. O processamento IFC foi colocado na fila."}
    except HTTPException:
        if file_path.exists(): file_path.unlink(missing_ok=True)
        raise
    except Exception as exc:
        db.rollback()
        if file_path.exists(): file_path.unlink(missing_ok=True)
        raise HTTPException(500, f"Falha ao receber o IFC: {exc}")
    finally:
        file.file.close()


@router.get("/project/{project_id}/models")
def get_models(project_id: int, db: Session = Depends(get_db)):
    return db.query(IfcModelModel).filter(IfcModelModel.project_id == project_id).order_by(IfcModelModel.version.desc()).all()

@router.get("/model/{model_id}")
def get_model(model_id: int, db: Session = Depends(get_db)):
    model = db.query(IfcModelModel).filter(IfcModelModel.id == model_id).first()
    if not model: raise HTTPException(404, "Modelo IFC não encontrado.")
    return model

@router.get("/model/{model_id}/download")
def download_ifc(model_id: int, db: Session = Depends(get_db)):
    model = db.query(IfcModelModel).filter(IfcModelModel.id == model_id).first()
    if not model or not Path(model.file_path).exists():
        raise HTTPException(404, "Arquivo não encontrado.")
    return FileResponse(model.file_path, media_type="application/octet-stream", filename=model.filename)

@router.get("/model/{model_id}/elements")
def get_elements(model_id: int, skip: int = 0, limit: int = 1000, db: Session = Depends(get_db)):
    model = db.query(IfcModelModel).filter(IfcModelModel.id == model_id).first()
    if not model: raise HTTPException(404, "Modelo IFC não encontrado.")
    limit = max(1, min(limit, 5000))
    return db.query(IfcElementModel).filter(IfcElementModel.model_id == model_id).offset(max(0, skip)).limit(limit).all()

@router.get("/project/{project_id}/compare")
def compare_ifc_versions(project_id: int, base_model_id: int, compare_model_id: int, db: Session = Depends(get_db)):
    base = db.query(IfcModelModel).filter(IfcModelModel.id == base_model_id, IfcModelModel.project_id == project_id).first()
    newer = db.query(IfcModelModel).filter(IfcModelModel.id == compare_model_id, IfcModelModel.project_id == project_id).first()
    if not base or not newer: raise HTTPException(404, "Uma das versões IFC não pertence ao projeto informado.")
    if base.status != "completed" or newer.status != "completed":
        raise HTTPException(409, "As duas versões precisam estar processadas para comparação.")
    base_ids = {row[0] for row in db.query(IfcElementModel.global_id).filter(IfcElementModel.model_id == base_model_id).all()}
    newer_ids = {row[0] for row in db.query(IfcElementModel.global_id).filter(IfcElementModel.model_id == compare_model_id).all()}
    return {"base_model_id": base_model_id, "compare_model_id": compare_model_id,
            "added": sorted(newer_ids - base_ids), "removed": sorted(base_ids - newer_ids),
            "unchanged": len(base_ids & newer_ids)}

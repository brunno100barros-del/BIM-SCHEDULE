"""Rotas IFC: envio de modelos, processamento em segundo plano, elementos e comparação de versões."""
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.errors import AppError
from app.core.logging import get_logger
from app.core.runtime import Runtime, get_runtime
from app.models.ifc import IfcElementModel, IfcModelModel
from app.models.project import ProjectModel
from app.modules.ifc.service import store_ifc_upload

router = APIRouter()
logger = get_logger("ifc")


@router.post("/project/{project_id}/upload", status_code=status.HTTP_202_ACCEPTED)
def upload_ifc(project_id: int, file: UploadFile = File(...), db: Session = Depends(get_db),
               runtime: Runtime = Depends(get_runtime)):
    """Recebe o arquivo e agenda o processamento em um processo separado.

    A resposta é imediata (202); o andamento é consultado em ``/jobs/{job_id}``.
    """
    project = db.get(ProjectModel, project_id)
    if not project:
        raise AppError(404, "Projeto não encontrado.", code="project_not_found")
    try:
        stored = store_ifc_upload(file.file, file.filename, project_id, runtime.storage.uploads_dir,
                                  runtime.settings.max_ifc_bytes)
    finally:
        file.file.close()
    try:
        version = db.query(IfcModelModel).filter(IfcModelModel.project_id == project_id).count() + 1
        model = IfcModelModel(project_id=project_id, filename=stored.original_name, file_path=str(stored.path),
                              version=version, status="queued", progress=0,
                              processing_message="Aguardando processamento", error_message=None)
        db.add(model)
        db.commit()
        db.refresh(model)
        job = runtime.jobs.submit("ifc.parse", {"model_id": model.id}, project_id=project_id)
        model.job_id = job["id"]
        db.commit()
    except Exception:
        db.rollback()
        stored.path.unlink(missing_ok=True)
        logger.exception("Falha ao registrar o modelo IFC do projeto %s", project_id)
        raise AppError(500, "Falha ao registrar o arquivo IFC recebido.", code="ifc_register_failed")
    logger.info("IFC '%s' recebido (%s bytes) para o projeto %s; tarefa %s.", stored.original_name, stored.size,
                project_id, job["id"])
    return {"id": model.id, "filename": model.filename, "version": model.version, "status": model.status,
            "size_bytes": stored.size, "sha256": stored.sha256, "job_id": job["id"],
            "message": "Arquivo recebido. O processamento IFC foi colocado na fila."}


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

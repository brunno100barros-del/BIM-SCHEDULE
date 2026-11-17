"""Acompanhamento e cancelamento de tarefas em segundo plano."""
from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.core.errors import AppError
from app.core.runtime import Runtime, get_runtime

router = APIRouter()


@router.get("/")
def list_jobs(project_id: Optional[int] = None, kind: Optional[str] = None,
              limit: int = Query(50, ge=1, le=200), runtime: Runtime = Depends(get_runtime)):
    return runtime.jobs.list(project_id=project_id, kind=kind, limit=limit)


@router.get("/{job_id}")
def get_job(job_id: str, runtime: Runtime = Depends(get_runtime)):
    job = runtime.jobs.get(job_id)
    if job is None:
        raise AppError(404, "Tarefa não encontrada.", code="job_not_found")
    return job


@router.post("/{job_id}/cancel", status_code=202)
def cancel_job(job_id: str, runtime: Runtime = Depends(get_runtime)):
    """Solicita o cancelamento. A tarefa encerra no próximo ponto de verificação."""
    job = runtime.jobs.cancel(job_id)
    if job is None:
        raise AppError(404, "Tarefa não encontrada.", code="job_not_found")
    return job

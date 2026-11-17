"""Ponto de entrada do processo filho de uma tarefa.

Executado com o método de inicialização ``spawn``: o processo importa este módulo
do zero, cria seu próprio engine de banco e grava progresso e resultado na tabela
``jobs``. Nenhum objeto do processo principal é compartilhado.
"""
from __future__ import annotations

import json
import logging
import traceback

from sqlalchemy.orm import sessionmaker

from app.core.database import create_engine_for_url
from app.core.logging import configure_logging, get_logger
from app.jobs.context import JobCancelled, JobContext, utcnow
from app.jobs.registry import get_kind, resolve
from app.models.job import JobModel


def run_job_process(job_id: str, kind: str, params: dict, database_url: str, log_level: str = "INFO",
                    logs_dir: str | None = None, poll_interval: float = 0.2) -> None:
    from pathlib import Path

    configure_logging(log_level, Path(logs_dir) if logs_dir else None)
    log = get_logger("jobs.worker")
    engine = create_engine_for_url(database_url, worker=True)
    factory = sessionmaker(bind=engine, autoflush=False, future=True)
    ctx = JobContext(job_id, factory, min_interval=poll_interval)

    def finish(status: str, *, error: str | None = None, result: object = None, progress: int | None = None):
        with ctx.session() as db:
            job = db.get(JobModel, job_id)
            if job is None:
                return
            job.status = status
            job.finished_at = utcnow()
            job.error = error
            if result is not None:
                job.result_json = json.dumps(result, ensure_ascii=False, default=str)
            if progress is not None:
                job.progress = progress
            job.message = {"completed": "Concluído", "cancelled": "Cancelado pelo usuário", "failed": "Falhou"}[status]
            db.commit()

    try:
        func = resolve(get_kind(kind).target)
        log.info("Tarefa %s (%s) iniciada", job_id, kind)
        result = func(ctx, **params)
        finish("completed", result=result, progress=100)
        log.info("Tarefa %s concluída", job_id)
    except JobCancelled:
        finish("cancelled")
        log.info("Tarefa %s cancelada", job_id)
    except Exception as exc:  # registra a falha para o usuário e o diagnóstico
        log.error("Tarefa %s falhou: %s\n%s", job_id, exc, traceback.format_exc())
        finish("failed", error=str(exc)[:2000] or exc.__class__.__name__)
    finally:
        engine.dispose()
        logging.shutdown()

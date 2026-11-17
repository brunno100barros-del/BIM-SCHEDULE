"""Sequência de inicialização do serviço.

1. Lê a configuração.
2. Resolve a pasta de dados (com migração segura de dados legados).
3. Configura logs na pasta de dados.
4. Atualiza o esquema do banco (com backup prévio).
5. Inicializa o engine e o gerenciador de tarefas.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from app.core.config import Settings, get_settings
from app.core.database import dispose_database, init_database
from app.core.logging import configure_logging, get_logger
from app.core.runtime import Runtime
from app.core.schema_migrations import upgrade_database
from app.core.storage import resolve_storage
from app.jobs.manager import JobManager

logger = get_logger("bootstrap")


def prepare_storage(settings: Optional[Settings] = None):
    """Resolve a pasta de dados e aplica migrações. Usado pelo serviço e pela CLI."""
    settings = settings or get_settings()
    configure_logging(settings.LOG_LEVEL)
    storage = resolve_storage(settings)
    configure_logging(settings.LOG_LEVEL, storage.logs_dir)
    schema = upgrade_database(storage)
    return storage, schema


def start_runtime(settings: Optional[Settings] = None) -> Runtime:
    settings = settings or get_settings()
    storage, schema = prepare_storage(settings)
    init_database(storage.database_url)
    jobs = JobManager(
        storage.database_url,
        max_workers=settings.JOB_MAX_WORKERS,
        cancel_grace=settings.JOB_CANCEL_GRACE_SECONDS,
        poll_interval=settings.JOB_POLL_INTERVAL_SECONDS,
        log_level=settings.LOG_LEVEL,
        logs_dir=storage.logs_dir,
    )
    jobs.start()
    logger.info("BIM SCHEDULE %s iniciado. Dados em %s (modo %s).", settings.VERSION, storage.data_dir, storage.mode)
    return Runtime(settings=settings, storage=storage, jobs=jobs, schema=schema,
                   started_at=datetime.now(timezone.utc).isoformat())


def stop_runtime(runtime: Runtime) -> None:
    runtime.jobs.shutdown()
    dispose_database()
    logger.info("BIM SCHEDULE encerrado.")

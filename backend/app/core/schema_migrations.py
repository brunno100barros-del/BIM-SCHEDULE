"""Execução das migrações Alembic com cópia de segurança prévia do banco."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Optional

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import inspect

from app.core.config import BACKEND_DIR
from app.core.database import create_engine_for_url
from app.core.logging import get_logger
from app.core.storage import StorageLayout, sqlite_backup

logger = get_logger("migrations")


def alembic_config(database_url: str) -> Config:
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    cfg.set_main_option("sqlalchemy.url", database_url)
    # Evita que o fileConfig do alembic.ini substitua os logs do serviço.
    cfg.attributes["configure_logger"] = False
    return cfg


def current_revision(database_url: str) -> Optional[str]:
    engine = create_engine_for_url(database_url, worker=True)
    try:
        with engine.connect() as conn:
            return MigrationContext.configure(conn).get_current_revision()
    finally:
        engine.dispose()


def _has_user_tables(database_url: str) -> bool:
    engine = create_engine_for_url(database_url, worker=True)
    try:
        return any(t != "alembic_version" for t in inspect(engine).get_table_names())
    finally:
        engine.dispose()


def upgrade_database(layout: StorageLayout) -> dict:
    """Atualiza o esquema para a última revisão. Faz backup do banco antes, se houver dados."""
    cfg = alembic_config(layout.database_url)
    head = ScriptDirectory.from_config(cfg).get_current_head()
    db_exists = bool(layout.database_path and layout.database_path.exists())
    before = current_revision(layout.database_url) if db_exists else None
    backup_path: Optional[Path] = None
    if before != head and db_exists and layout.database_path and _has_user_tables(layout.database_url):
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup_path = layout.backups_dir / f"bim_schedule-{stamp}-antes-{head}.db"
        sqlite_backup(layout.database_path, backup_path)
        logger.info("Backup do banco antes da migração de esquema: %s", backup_path)
    if before != head:
        command.upgrade(cfg, "head")
        logger.info("Esquema do banco atualizado de %s para %s", before, head)
    return {"from": before, "to": head, "backup": str(backup_path) if backup_path else None}

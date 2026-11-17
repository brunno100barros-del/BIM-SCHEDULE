"""Resolução da pasta de dados e migração segura de instalações legadas.

Layout da pasta de dados (``%LOCALAPPDATA%\\BIM-SCHEDULE`` no Windows)::

    bim_schedule.db        banco SQLite
    uploads/               arquivos IFC enviados
    logs/                  logs rotativos do serviço
    backups/               cópias do banco feitas antes de migrações de esquema
    ai-exchange/           pacotes de intercâmbio com IA (exportação/importação)
    migration-report.json  relatório da migração de dados legados, se houver

Instalações anteriores à Etapa 2 gravavam o banco em ``backend/bim_schedule.db`` e
os IFC em ``backend/uploads``. A migração **copia** esses dados para a nova pasta,
valida contagens de registros, integridade do SQLite e hash SHA-256 de cada
arquivo e só então ativa a nova pasta. Os dados legados nunca são alterados nem
apagados. Se qualquer validação falhar, a cópia parcial é descartada e o serviço
continua usando a localização legada.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import shutil
import sqlite3
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal, Optional

from app.core.config import Settings

logger = logging.getLogger("bim_schedule.storage")

DB_FILENAME = "bim_schedule.db"
UPLOADS_DIRNAME = "uploads"
REPORT_FILENAME = "migration-report.json"

StorageMode = Literal["data_dir", "legacy", "explicit_database_url"]


class MigrationError(RuntimeError):
    """Falha de validação durante a migração de dados legados."""


@dataclass
class MigrationReport:
    status: Literal["migrated", "skipped", "failed"]
    source_dir: str
    target_dir: str
    started_at: str
    finished_at: Optional[str] = None
    table_counts: dict[str, int] = field(default_factory=dict)
    files_copied: int = 0
    bytes_copied: int = 0
    rewritten_paths: int = 0
    missing_files: list[str] = field(default_factory=list)
    message: str = ""


@dataclass
class StorageLayout:
    mode: StorageMode
    data_dir: Path
    database_url: str
    database_path: Optional[Path]
    uploads_dir: Path
    logs_dir: Path
    backups_dir: Path
    ai_exchange_dir: Path
    legacy_data_detected: bool = False
    migration: Optional[MigrationReport] = None

    def ensure_directories(self) -> None:
        for directory in (self.data_dir, self.uploads_dir, self.logs_dir, self.backups_dir, self.ai_exchange_dir):
            directory.mkdir(parents=True, exist_ok=True)

    def public_summary(self) -> dict:
        return {
            "mode": self.mode,
            "data_dir": str(self.data_dir),
            "database_path": str(self.database_path) if self.database_path else None,
            "uploads_dir": str(self.uploads_dir),
            "legacy_data_detected": self.legacy_data_detected,
            "migration": asdict(self.migration) if self.migration else None,
        }


def default_data_dir() -> Path:
    """Pasta de dados padrão do usuário, conforme o sistema operacional."""
    if sys.platform.startswith("win"):
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(base) / "BIM-SCHEDULE"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "BIM-SCHEDULE"
    base = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
    return Path(base) / "bim-schedule"


def sqlite_path_from_url(url: str) -> Optional[Path]:
    prefix = "sqlite:///"
    if not url.startswith(prefix):
        return None
    raw = url[len(prefix):]
    if raw in ("", ":memory:"):
        return None
    return Path(raw).resolve()


def _layout(mode: StorageMode, data_dir: Path, db_path: Path, uploads_dir: Path) -> StorageLayout:
    return StorageLayout(
        mode=mode,
        data_dir=data_dir,
        database_url=f"sqlite:///{db_path.as_posix()}",
        database_path=db_path,
        uploads_dir=uploads_dir,
        logs_dir=data_dir / "logs",
        backups_dir=data_dir / "backups",
        ai_exchange_dir=data_dir / "ai-exchange",
    )


def _legacy_paths(settings: Settings) -> tuple[Path, Path]:
    legacy_dir = Path(settings.LEGACY_DIR).resolve()
    return legacy_dir / DB_FILENAME, legacy_dir / UPLOADS_DIRNAME


def _legacy_has_data(settings: Settings) -> bool:
    legacy_db, legacy_uploads = _legacy_paths(settings)
    has_files = legacy_uploads.is_dir() and any(p.is_file() for p in legacy_uploads.iterdir())
    return (legacy_db.is_file() and legacy_db.stat().st_size > 0) or has_files


def resolve_storage(settings: Settings, *, migrate: bool = True) -> StorageLayout:
    """Define onde o serviço guarda os dados e, se necessário, migra os dados legados."""
    data_dir = Path(settings.DATA_DIR).expanduser().resolve() if settings.DATA_DIR else default_data_dir()

    if settings.DATABASE_URL:
        db_path = sqlite_path_from_url(settings.DATABASE_URL)
        legacy_db, legacy_uploads = _legacy_paths(settings)
        # Compatibilidade: a URL antiga apontava para backend/bim_schedule.db com uploads em backend/uploads.
        uploads = legacy_uploads if db_path and db_path == legacy_db.resolve() else data_dir / UPLOADS_DIRNAME
        layout = StorageLayout(
            mode="explicit_database_url",
            data_dir=data_dir,
            database_url=settings.DATABASE_URL,
            database_path=db_path,
            uploads_dir=uploads,
            logs_dir=data_dir / "logs",
            backups_dir=data_dir / "backups",
            ai_exchange_dir=data_dir / "ai-exchange",
        )
        layout.ensure_directories()
        return layout

    target = _layout("data_dir", data_dir, data_dir / DB_FILENAME, data_dir / UPLOADS_DIRNAME)
    legacy_db, legacy_uploads = _legacy_paths(settings)
    legacy_detected = legacy_db.resolve() != target.database_path and _legacy_has_data(settings)

    if target.database_path.exists() or not legacy_detected:
        target.legacy_data_detected = legacy_detected
        target.migration = read_migration_report(data_dir)
        target.ensure_directories()
        return target

    if not (migrate and settings.AUTO_MIGRATE_LEGACY_DATA):
        logger.warning("Dados legados encontrados em %s, migração automática desativada; usando local legado.", legacy_db.parent)
        legacy = _layout("legacy", data_dir, legacy_db, legacy_uploads)
        legacy.legacy_data_detected = True
        legacy.ensure_directories()
        return legacy

    try:
        report = migrate_legacy_data(legacy_db, legacy_uploads, data_dir)
        target.migration = report
        target.legacy_data_detected = True
        target.ensure_directories()
        return target
    except Exception as exc:  # a falha nunca pode impedir o acesso aos dados originais
        logger.error("Migração de dados legados falhou; mantendo local legado. Motivo: %s", exc)
        legacy = _layout("legacy", data_dir, legacy_db, legacy_uploads)
        legacy.legacy_data_detected = True
        legacy.migration = MigrationReport(
            status="failed", source_dir=str(legacy_db.parent), target_dir=str(data_dir),
            started_at=_now(), finished_at=_now(), message=str(exc),
        )
        legacy.ensure_directories()
        return legacy


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sqlite_backup(source: Path, destination: Path) -> None:
    """Cópia consistente de um banco SQLite (inclui conteúdo de arquivos WAL)."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    src = sqlite3.connect(f"file:{source.as_posix()}?mode=ro", uri=True)
    try:
        dst = sqlite3.connect(str(destination))
        try:
            src.backup(dst)
        finally:
            dst.close()
    finally:
        src.close()


def _table_counts(db_path: Path) -> dict[str, int]:
    conn = sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro", uri=True)
    try:
        tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
        return {t: conn.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0] for t in sorted(tables)}
    finally:
        conn.close()


def _integrity_ok(db_path: Path) -> bool:
    conn = sqlite3.connect(str(db_path))
    try:
        return conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    finally:
        conn.close()


def migrate_legacy_data(legacy_db: Path, legacy_uploads: Path, data_dir: Path) -> MigrationReport:
    """Copia banco e uploads legados para ``data_dir`` com validação completa.

    A cópia é montada em uma pasta temporária dentro de ``data_dir`` e só é ativada
    após todas as validações. Os arquivos de origem são abertos somente para leitura.
    """
    report = MigrationReport(status="failed", source_dir=str(legacy_db.parent), target_dir=str(data_dir), started_at=_now())
    data_dir.mkdir(parents=True, exist_ok=True)
    staging = data_dir / f".migration-{datetime.now().strftime('%Y%m%d-%H%M%S-%f')}"
    staging.mkdir()
    logger.info("Migrando dados legados de %s para %s", legacy_db.parent, data_dir)
    try:
        staged_db = staging / DB_FILENAME
        source_counts: dict[str, int] = {}
        if legacy_db.is_file():
            source_counts = _table_counts(legacy_db)
            sqlite_backup(legacy_db, staged_db)
            if not _integrity_ok(staged_db):
                raise MigrationError("PRAGMA integrity_check falhou na cópia do banco.")
            copied_counts = _table_counts(staged_db)
            if copied_counts != source_counts:
                raise MigrationError(f"Contagem de registros divergente: origem={source_counts} cópia={copied_counts}")
        report.table_counts = source_counts

        staged_uploads = staging / UPLOADS_DIRNAME
        staged_uploads.mkdir()
        if legacy_uploads.is_dir():
            for item in sorted(legacy_uploads.iterdir()):
                if not item.is_file():
                    continue
                target_file = staged_uploads / item.name
                shutil.copy2(item, target_file)
                if _sha256(item) != _sha256(target_file):
                    raise MigrationError(f"Hash divergente após copiar {item.name}.")
                report.files_copied += 1
                report.bytes_copied += target_file.stat().st_size

        final_uploads = data_dir / UPLOADS_DIRNAME
        if staged_db.exists():
            report.rewritten_paths, report.missing_files = _rewrite_ifc_paths(staged_db, legacy_uploads, final_uploads)

        # Ativação: só depois de todas as validações.
        final_uploads.mkdir(exist_ok=True)
        for item in staged_uploads.iterdir():
            destination = final_uploads / item.name
            if destination.exists():
                if _sha256(destination) != _sha256(item):
                    raise MigrationError(f"Já existe um arquivo diferente com o nome {item.name} na pasta de destino.")
                continue
            shutil.move(str(item), destination)
        if staged_db.exists():
            os.replace(staged_db, data_dir / DB_FILENAME)
        report.status = "migrated"
        report.finished_at = _now()
        report.message = "Dados copiados e validados. Os arquivos originais foram mantidos sem alteração."
        write_migration_report(data_dir, report)
        logger.info("Migração concluída: %s tabelas, %s arquivos.", len(report.table_counts), report.files_copied)
        return report
    finally:
        shutil.rmtree(staging, ignore_errors=True)


def _rewrite_ifc_paths(db_path: Path, legacy_uploads: Path, new_uploads: Path) -> tuple[int, list[str]]:
    conn = sqlite3.connect(str(db_path))
    rewritten, missing = 0, []
    try:
        exists = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='ifc_models'").fetchone()
        if not exists:
            return 0, []
        legacy_resolved = legacy_uploads.resolve()
        for model_id, file_path in conn.execute("SELECT id, file_path FROM ifc_models").fetchall():
            old = Path(file_path)
            candidate = old if old.is_absolute() else (legacy_uploads.parent / old)
            in_legacy = candidate.resolve().parent == legacy_resolved
            if in_legacy and (legacy_uploads / old.name).is_file():
                conn.execute("UPDATE ifc_models SET file_path=? WHERE id=?", (str(new_uploads / old.name), model_id))
                rewritten += 1
            elif not candidate.exists():
                missing.append(file_path)
        conn.commit()
    finally:
        conn.close()
    return rewritten, missing


def write_migration_report(data_dir: Path, report: MigrationReport) -> None:
    (data_dir / REPORT_FILENAME).write_text(json.dumps(asdict(report), ensure_ascii=False, indent=2), encoding="utf-8")


def read_migration_report(data_dir: Path) -> Optional[MigrationReport]:
    path = data_dir / REPORT_FILENAME
    if not path.is_file():
        return None
    try:
        return MigrationReport(**json.loads(path.read_text(encoding="utf-8")))
    except Exception:
        return None

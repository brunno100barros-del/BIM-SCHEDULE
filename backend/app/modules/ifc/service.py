"""Recebimento seguro de arquivos IFC."""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO
from uuid import uuid4

from app.core.errors import AppError

CHUNK_SIZE = 1024 * 1024
_SAFE_CHARS = re.compile(r"[^A-Za-z0-9._-]+")


def safe_filename(original: str | None, default: str = "modelo.ifc") -> str:
    """Nome de arquivo sem diretórios nem caracteres problemáticos (Windows inclusive)."""
    name = Path((original or default).replace("\\", "/")).name or default
    stem, dot, ext = name.rpartition(".")
    cleaned = _SAFE_CHARS.sub("_", stem if dot else name).strip("._") or "modelo"
    return f"{cleaned[:120]}.{ext.lower()}" if dot else cleaned[:120]


@dataclass
class StoredFile:
    path: Path
    original_name: str
    size: int
    sha256: str


def store_ifc_upload(stream: BinaryIO, original_name: str | None, project_id: int, uploads_dir: Path,
                     max_bytes: int) -> StoredFile:
    display_name = Path((original_name or "modelo.ifc").replace("\\", "/")).name or "modelo.ifc"
    if not display_name.lower().endswith(".ifc"):
        raise AppError(400, "Apenas arquivos .ifc são suportados.", code="unsupported_file_type")
    uploads_dir.mkdir(parents=True, exist_ok=True)
    target = uploads_dir / f"{project_id}_{uuid4().hex}_{safe_filename(display_name)}"
    digest = hashlib.sha256()
    size = 0
    try:
        with target.open("wb") as output:
            while chunk := stream.read(CHUNK_SIZE):
                size += len(chunk)
                if size > max_bytes:
                    raise AppError(413, f"Arquivo IFC excede o limite de {max_bytes // (1024 * 1024)} MiB.",
                                   code="file_too_large")
                digest.update(chunk)
                output.write(chunk)
        if size == 0:
            raise AppError(400, "O arquivo enviado está vazio.", code="empty_file")
    except BaseException:
        target.unlink(missing_ok=True)
        raise
    return StoredFile(path=target, original_name=display_name, size=size, sha256=digest.hexdigest())

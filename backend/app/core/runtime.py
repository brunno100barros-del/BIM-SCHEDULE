"""Estado de execução do serviço (configuração, armazenamento e tarefas)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from fastapi import Request

from app.core.config import Settings
from app.core.storage import StorageLayout
from app.jobs.manager import JobManager


@dataclass
class Runtime:
    settings: Settings
    storage: StorageLayout
    jobs: JobManager
    schema: dict = field(default_factory=dict)
    started_at: Optional[str] = None


def get_runtime(request: Request) -> Runtime:
    runtime = getattr(request.app.state, "runtime", None)
    if runtime is None:
        raise RuntimeError("Serviço ainda não inicializado.")
    return runtime

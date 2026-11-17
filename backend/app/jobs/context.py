"""Contexto entregue às funções de tarefa, executadas em processo separado."""
from __future__ import annotations

import time
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Callable, Iterator, Optional

from sqlalchemy.orm import Session, sessionmaker

from app.models.job import JobModel


class JobCancelled(Exception):
    """Lançada por :meth:`JobContext.check_cancelled` quando o usuário pediu o cancelamento."""


class JobContext:
    """Canal entre a tarefa e o serviço: progresso, cancelamento cooperativo e sessão de banco.

    O progresso é gravado na tabela ``jobs`` (que a API consulta). As gravações são
    limitadas para não sobrecarregar o SQLite em laços rápidos.
    """

    def __init__(self, job_id: str, session_factory: sessionmaker, *, min_interval: float = 0.2,
                 clock: Callable[[], float] = time.monotonic):
        self.job_id = job_id
        self._session_factory = session_factory
        self._min_interval = min_interval
        self._clock = clock
        self._last_write = 0.0
        self._last_cancel_check = 0.0
        self._last_progress: Optional[int] = None
        self._cancelled = False

    @contextmanager
    def session(self) -> Iterator[Session]:
        db = self._session_factory()
        try:
            yield db
        finally:
            db.close()

    def progress(self, percent: float, message: Optional[str] = None, *, force: bool = False) -> None:
        value = max(0, min(100, int(percent)))
        now = self._clock()
        if not force and value == self._last_progress and now - self._last_write < self._min_interval:
            return
        if not force and now - self._last_write < self._min_interval and value - (self._last_progress or 0) < 5:
            return
        with self.session() as db:
            job = db.get(JobModel, self.job_id)
            if job is None:
                return
            job.progress = value
            if message is not None:
                job.message = message[:500]
            db.commit()
        self._last_progress = value
        self._last_write = now

    def is_cancel_requested(self, *, force: bool = False) -> bool:
        if self._cancelled:
            return True
        now = self._clock()
        if not force and now - self._last_cancel_check < self._min_interval:
            return False
        self._last_cancel_check = now
        with self.session() as db:
            job = db.get(JobModel, self.job_id)
            self._cancelled = bool(job and job.cancel_requested)
        return self._cancelled

    def check_cancelled(self, *, force: bool = False) -> None:
        if self.is_cancel_requested(force=force):
            raise JobCancelled()


def utcnow() -> datetime:
    return datetime.now(timezone.utc)

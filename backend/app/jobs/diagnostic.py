"""Tarefa de diagnóstico do mecanismo de processamento em segundo plano.

Não é exposta pela API; é usada pelos testes automatizados para verificar
progresso, cancelamento cooperativo, encerramento forçado e falhas.
"""
from __future__ import annotations

import os
import time

from app.jobs.context import JobContext


def diagnostic_job(ctx: JobContext, *, steps: int = 10, step_seconds: float = 0.05,
                   fail_at: int | None = None, ignore_cancel: bool = False, crash_at: int | None = None) -> dict:
    for step in range(1, steps + 1):
        if not ignore_cancel:
            ctx.check_cancelled(force=True)
        time.sleep(step_seconds)
        if fail_at is not None and step == fail_at:
            raise RuntimeError(f"Falha simulada na etapa {step}")
        if crash_at is not None and step == crash_at:
            os._exit(3)  # simula a morte abrupta do processo
        ctx.progress(step / steps * 100, f"Etapa {step} de {steps}", force=True)
    return {"steps": steps}

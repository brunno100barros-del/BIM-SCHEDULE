"""Tarefa de diagnóstico do mecanismo de processamento em segundo plano.

Não é exposta pela API; é usada pelos testes automatizados para verificar
progresso, cancelamento cooperativo, encerramento forçado e falhas.
"""
from __future__ import annotations

import os
import time

from app.jobs.context import JobContext


def diagnostic_job(ctx: JobContext, *, steps: int = 10, step_seconds: float = 0.05,
                   fail_at: int | None = None, ignore_cancel: bool = False, crash_at: int | None = None,
                   abort_marker: bool = False, abort_hook_fails: bool = False) -> dict:
    # abort_marker / abort_hook_fails configuram apenas on_diagnostic_aborted.
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


def on_diagnostic_aborted(db, *, job_id: str, params: dict, status: str) -> None:
    """Rotina de consistência da tarefa de diagnóstico (somente testes).

    Com ``abort_marker=True``, registra em ``result_json`` que a rotina rodou e com qual
    status, para que os testes verifiquem que ela terminou ANTES do estado terminal.
    Com ``abort_hook_fails=True``, falha de propósito. Idempotente.
    """
    import json

    from app.models.job import JobModel

    if params.get("abort_hook_fails"):
        raise RuntimeError("falha simulada na rotina de consistência do diagnóstico")
    if not params.get("abort_marker"):
        return
    job = db.get(JobModel, job_id)
    if job is not None:
        job.result_json = json.dumps({"abort_hook": status})
        db.commit()

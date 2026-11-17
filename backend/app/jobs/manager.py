"""Gerenciador de tarefas em segundo plano.

Decisões de projeto (Etapa 2):

* **Um processo por tarefa**, criado com ``multiprocessing`` no modo ``spawn``
  (o único disponível no Windows e usado em todos os sistemas para manter o
  mesmo comportamento). O processamento pesado (IfcOpenShell) não disputa o GIL
  com o servidor FastAPI e não bloqueia a API.
* **Estado persistido** na tabela ``jobs`` do SQLite: status, progresso,
  mensagem, erro e resultado sobrevivem a reinícios e são lidos pela API.
* **Cancelamento cooperativo real**: a API marca ``cancel_requested``; a tarefa
  verifica a marca entre lotes de trabalho e encerra de forma limpa. Se não
  responder em ``cancel_grace`` segundos (por exemplo, presa dentro de uma
  chamada nativa), o supervisor encerra o processo (terminate/kill) e executa o
  ``abort_hook`` do tipo de tarefa para restaurar a consistência dos dados.
* **Recuperação**: tarefas ativas encontradas na inicialização pertenciam a um
  serviço anterior que terminou; são marcadas como ``interrupted``.

Não há fila distribuída, Redis ou Celery: o serviço é local e de usuário único.
"""
from __future__ import annotations

import json
import multiprocessing
import queue
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Optional

from sqlalchemy.orm import sessionmaker

from app.core.database import create_engine_for_url
from app.core.logging import get_logger
from app.jobs.context import utcnow
from app.jobs.registry import get_kind, resolve
from app.jobs.worker import run_job_process
from app.models.job import JobModel

logger = get_logger("jobs")

ACTIVE_STATUSES = ("queued", "running", "cancelling")
TERMINAL_STATUSES = ("completed", "failed", "cancelled", "interrupted")


def job_to_dict(job: JobModel) -> dict[str, Any]:
    return {
        "id": job.id,
        "kind": job.kind,
        "project_id": job.project_id,
        "status": job.status,
        "progress": job.progress,
        "message": job.message,
        "error": job.error,
        "result": json.loads(job.result_json) if job.result_json else None,
        "cancel_requested": bool(job.cancel_requested),
        "created_at": job.created_at,
        "started_at": job.started_at,
        "updated_at": job.updated_at,
        "finished_at": job.finished_at,
        "is_terminal": job.status in TERMINAL_STATUSES,
    }


class JobManager:
    def __init__(self, database_url: str, *, max_workers: int = 1, cancel_grace: float = 10.0,
                 poll_interval: float = 0.2, log_level: str = "INFO", logs_dir: Optional[Path] = None):
        self.database_url = database_url
        self.max_workers = max(1, max_workers)
        self.cancel_grace = cancel_grace
        self.poll_interval = poll_interval
        self.log_level = log_level
        self.logs_dir = logs_dir
        self._engine = create_engine_for_url(database_url)
        self._sessions = sessionmaker(bind=self._engine, autoflush=False, future=True)
        self._mp = multiprocessing.get_context("spawn")
        self._queue: "queue.Queue[str]" = queue.Queue()
        self._stopping = threading.Event()
        self._threads: list[threading.Thread] = []
        self._processes: dict[str, multiprocessing.process.BaseProcess] = {}
        self._lock = threading.Lock()
        self._started = False

    # ------------------------------------------------------------------ ciclo de vida
    def start(self) -> None:
        if self._started:
            return
        self._recover_stale_jobs()
        for index in range(self.max_workers):
            thread = threading.Thread(target=self._supervise, name=f"bim-job-supervisor-{index}", daemon=True)
            thread.start()
            self._threads.append(thread)
        self._started = True
        logger.info("Gerenciador de tarefas iniciado com %s processo(s) simultâneo(s).", self.max_workers)

    def shutdown(self, timeout: Optional[float] = None) -> None:
        """Encerra o gerenciador: pede o cancelamento das tarefas em execução e aguarda."""
        if not self._started:
            self._engine.dispose()
            return
        self._stopping.set()
        with self._lock:
            running = list(self._processes)
        for job_id in running:
            self._request_cancel(job_id, reason="Encerramento do serviço")
        limit = timeout if timeout is not None else self.cancel_grace + 10
        deadline = time.monotonic() + limit
        for thread in self._threads:
            thread.join(max(0.0, deadline - time.monotonic()))
        with self._lock:
            leftovers = list(self._processes.items())
        for job_id, process in leftovers:
            logger.warning("Encerrando à força o processo da tarefa %s no desligamento.", job_id)
            process.kill()
            process.join(5)
        # Tarefas que nunca saíram da fila.
        with self._sessions() as db:
            for job in db.query(JobModel).filter(JobModel.status == "queued").all():
                job.status = "interrupted"
                job.message = "Interrompida: o serviço foi encerrado antes do início."
                job.finished_at = utcnow()
            db.commit()
        self._threads.clear()
        self._started = False
        self._engine.dispose()
        logger.info("Gerenciador de tarefas encerrado.")

    # ------------------------------------------------------------------ API pública
    def submit(self, kind: str, params: Optional[dict] = None, *, project_id: Optional[int] = None) -> dict:
        get_kind(kind)  # valida o tipo
        if self._stopping.is_set():
            raise RuntimeError("O serviço está sendo encerrado; não é possível iniciar novas tarefas.")
        job_id = uuid.uuid4().hex
        with self._sessions() as db:
            job = JobModel(id=job_id, kind=kind, project_id=project_id, status="queued", progress=0,
                           message="Na fila", params_json=json.dumps(params or {}, ensure_ascii=False))
            db.add(job)
            db.commit()
            data = job_to_dict(job)
        self._queue.put(job_id)
        logger.info("Tarefa %s (%s) enfileirada.", job_id, kind)
        return data

    def get(self, job_id: str) -> Optional[dict]:
        with self._sessions() as db:
            job = db.get(JobModel, job_id)
            return job_to_dict(job) if job else None

    def list(self, *, project_id: Optional[int] = None, kind: Optional[str] = None, limit: int = 50) -> list[dict]:
        with self._sessions() as db:
            query = db.query(JobModel)
            if project_id is not None:
                query = query.filter(JobModel.project_id == project_id)
            if kind:
                query = query.filter(JobModel.kind == kind)
            return [job_to_dict(j) for j in query.order_by(JobModel.created_at.desc()).limit(limit).all()]

    def cancel(self, job_id: str) -> Optional[dict]:
        with self._sessions() as db:
            job = db.get(JobModel, job_id)
            if job is None:
                return None
            if job.status == "queued":
                job.status = "cancelled"
                job.cancel_requested = True
                job.cancel_requested_at = utcnow()
                job.finished_at = utcnow()
                job.message = "Cancelada antes do início"
                db.commit()
                params = json.loads(job.params_json or "{}")
                self._run_abort_hook(job.kind, job_id, params, "cancelled")
                return job_to_dict(job)
        self._request_cancel(job_id, reason="Cancelamento solicitado pelo usuário")
        return self.get(job_id)

    def active_count(self) -> int:
        with self._lock:
            return len(self._processes)

    def wait(self, job_id: str, timeout: float = 30.0) -> Optional[dict]:
        """Aguarda a conclusão de uma tarefa (uso em testes e scripts)."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            data = self.get(job_id)
            if data and data["is_terminal"]:
                with self._lock:
                    if job_id not in self._processes:
                        return data
            time.sleep(0.05)
        return self.get(job_id)

    # ------------------------------------------------------------------ internos
    def _request_cancel(self, job_id: str, *, reason: str) -> None:
        with self._sessions() as db:
            job = db.get(JobModel, job_id)
            if job is None or job.status in TERMINAL_STATUSES:
                return
            if not job.cancel_requested:
                job.cancel_requested = True
                job.cancel_requested_at = utcnow()
            job.status = "cancelling"
            job.message = reason
            db.commit()

    def _recover_stale_jobs(self) -> None:
        with self._sessions() as db:
            stale = db.query(JobModel).filter(JobModel.status.in_(ACTIVE_STATUSES)).all()
            items = [(j.id, j.kind, json.loads(j.params_json or "{}")) for j in stale]
            for job in stale:
                job.status = "interrupted"
                job.message = "Interrompida: o serviço anterior foi encerrado antes da conclusão."
                job.finished_at = utcnow()
            db.commit()
        for job_id, kind, params in items:
            logger.warning("Tarefa %s (%s) marcada como interrompida na inicialização.", job_id, kind)
            self._run_abort_hook(kind, job_id, params, "interrupted")

    def _supervise(self) -> None:
        while not self._stopping.is_set():
            try:
                job_id = self._queue.get(timeout=self.poll_interval)
            except queue.Empty:
                continue
            try:
                self._run(job_id)
            except Exception:  # o supervisor nunca pode morrer
                logger.exception("Erro ao supervisionar a tarefa %s", job_id)
            finally:
                self._queue.task_done()

    def _run(self, job_id: str) -> None:
        with self._sessions() as db:
            job = db.get(JobModel, job_id)
            if job is None or job.status != "queued":
                return
            kind, params = job.kind, json.loads(job.params_json or "{}")
            job.status = "running"
            job.started_at = utcnow()
            job.message = "Em execução"
            db.commit()

        try:
            process = self._mp.Process(
                target=run_job_process,
                args=(job_id, kind, params, self.database_url, self.log_level,
                      str(self.logs_dir) if self.logs_dir else None, self.poll_interval),
                name=f"bim-job-{job_id[:8]}",
                daemon=True,
            )
            with self._lock:
                self._processes[job_id] = process
            process.start()
        except Exception as exc:
            # Sem processo não há quem finalize a tarefa: registra a falha aqui para que
            # ela não fique "running" indefinidamente. O supervisor segue para a próxima.
            # A referência só é liberada depois da finalização, para que wait() e os
            # clientes não vejam a tarefa encerrada antes de os dados ficarem consistentes.
            logger.exception("Falha ao iniciar o processo da tarefa %s (%s)", job_id, kind)
            try:
                self._fail_to_start(job_id, kind, params, exc)
            finally:
                with self._lock:
                    self._processes.pop(job_id, None)
            return
        try:
            with self._sessions() as db:
                job = db.get(JobModel, job_id)
                if job is not None:
                    job.pid = process.pid
                    db.commit()
            forced = self._monitor(job_id, process)
        finally:
            with self._lock:
                self._processes.pop(job_id, None)
        self._finalize(job_id, kind, params, process.exitcode, forced)

    def _monitor(self, job_id: str, process) -> bool:
        cancel_seen: Optional[float] = None
        while process.is_alive():
            process.join(self.poll_interval)
            if not process.is_alive():
                break
            if cancel_seen is None:
                with self._sessions() as db:
                    job = db.get(JobModel, job_id)
                    if job is not None and job.cancel_requested:
                        cancel_seen = time.monotonic()
            elif time.monotonic() - cancel_seen > self.cancel_grace:
                logger.warning("Tarefa %s não respondeu ao cancelamento em %.1fs; encerrando o processo.", job_id, self.cancel_grace)
                process.terminate()
                process.join(5)
                if process.is_alive():
                    process.kill()
                    process.join(5)
                return True
        return False

    def _fail_to_start(self, job_id: str, kind: str, params: dict, exc: BaseException) -> None:
        """Registra como ``failed`` uma tarefa cujo processo não pôde ser iniciado.

        O ``abort_hook`` roda primeiro: quando a tarefa aparece como ``failed``, os dados
        do domínio (por exemplo, o modelo IFC) já foram restaurados.
        """
        detail = str(exc).strip() or exc.__class__.__name__
        self._run_abort_hook(kind, job_id, params, "failed")
        with self._sessions() as db:
            job = db.get(JobModel, job_id)
            if job is None:
                return
            job.status = "failed"
            job.message = "Falhou ao iniciar"
            job.error = (f"Não foi possível iniciar o processo da tarefa ({exc.__class__.__name__}: {detail}). "
                         "Verifique memória disponível, antivírus e permissões, e tente novamente.")[:2000]
            job.pid = None
            job.finished_at = utcnow()
            db.commit()

    def _finalize(self, job_id: str, kind: str, params: dict, exitcode: Optional[int], forced: bool) -> None:
        with self._sessions() as db:
            job = db.get(JobModel, job_id)
            if job is None or job.status in TERMINAL_STATUSES:
                return
            if forced or job.cancel_requested:
                job.status = "cancelled"
                job.message = (f"Cancelada: o processo foi encerrado após {self.cancel_grace:.0f}s sem resposta"
                               if forced else "Cancelada")
            else:
                job.status = "failed"
                job.message = "Falhou"
                job.error = f"O processo da tarefa terminou inesperadamente (código de saída {exitcode})."
            job.finished_at = utcnow()
            status = job.status
            db.commit()
        logger.warning("Tarefa %s finalizada pelo supervisor com status %s (exitcode=%s).", job_id, status, exitcode)
        self._run_abort_hook(kind, job_id, params, status)

    def _run_abort_hook(self, kind: str, job_id: str, params: dict, status: str) -> None:
        try:
            hook_path = get_kind(kind).abort_hook
        except ValueError:
            return
        if not hook_path:
            return
        try:
            hook = resolve(hook_path)
            with self._sessions() as db:
                hook(db, job_id=job_id, params=params, status=status)
        except Exception:
            logger.exception("Falha ao executar a rotina de consistência da tarefa %s", job_id)

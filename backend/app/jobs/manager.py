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

Regras de consistência (revisão da Etapa 2, defeitos J1–J6):

* **Ordem de encerramento** em todos os caminhos conduzidos pelo supervisor
  (falha ao iniciar, falha de supervisão, morte do processo, encerramento
  forçado, cancelamento na fila, desligamento e recuperação):
  ``abort_hook`` → estado terminal com diagnóstico → liberação da referência ao
  processo. Quando a tarefa aparece como terminal, os dados do domínio já foram
  restaurados. Falha do próprio ``abort_hook`` fica explícita na tarefa e no log.
* **Transições atômicas**: mudanças de estado são ``UPDATE ... WHERE status IN
  (...)`` condicionais; apenas quem efetivamente muda o estado prossegue. Isso
  elimina as corridas entre cancelamento, início e conclusão.

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

from sqlalchemy import update
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
        """Encerra o gerenciador: pede o cancelamento das tarefas em execução e aguarda.

        Tarefas ainda na fila são encerradas como ``interrupted`` **depois** da rotina de
        consistência (J5). Processos que não terminam no prazo são encerrados à força e
        finalizados da mesma forma; o que ainda restar ativo é recuperado na próxima
        inicialização.
        """
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
            self._stop_process(process)
        if leftovers:
            # Com o processo encerrado, o supervisor conclui a finalização (_finalize).
            for thread in self._threads:
                thread.join(10)
        with self._sessions() as db:
            queued = [(j.id, j.kind, json.loads(j.params_json or "{}"))
                      for j in db.query(JobModel).filter(JobModel.status == "queued").all()]
        for job_id, kind, params in queued:
            self._close(job_id, kind, params, from_statuses=("queued",), status="interrupted",
                        message="Interrompida: o serviço foi encerrado antes do início.")
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
        """Cancela uma tarefa.

        Na fila: a transição ``queued`` → ``cancelling`` é atômica (J4), então o supervisor
        não pode iniciá-la depois; a rotina de consistência roda e só então a tarefa fica
        ``cancelled`` (J2). Em execução: pede o cancelamento cooperativo.
        """
        with self._sessions() as db:
            job = db.get(JobModel, job_id)
            if job is None:
                return None
            kind, params = job.kind, json.loads(job.params_json or "{}")
        now = utcnow()
        claimed = self._transition(job_id, ("queued",), status="cancelling", cancel_requested=True,
                                   cancel_requested_at=now, message="Cancelando antes do início")
        if claimed:
            self._close(job_id, kind, params, from_statuses=("cancelling",), status="cancelled",
                        message="Cancelada antes do início")
        else:
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

    # ------------------------------------------------------------------ transições
    def _transition(self, job_id: str, from_statuses: tuple[str, ...], **values: Any) -> bool:
        """Muda o estado somente se o atual estiver em ``from_statuses``. Retorna se mudou."""
        values.setdefault("updated_at", utcnow())
        with self._sessions() as db:
            result = db.execute(
                update(JobModel)
                .where(JobModel.id == job_id, JobModel.status.in_(from_statuses))
                .values(**values)
                .execution_options(synchronize_session=False)
            )
            db.commit()
            return result.rowcount == 1

    def _close(self, job_id: str, kind: str, params: dict, *, from_statuses: tuple[str, ...], status: str,
               message: str, error: Optional[str] = None) -> bool:
        """Encerra a tarefa na ordem garantida: rotina de consistência → estado terminal.

        Se a rotina falhar, a falha fica explícita em ``message`` e ``error`` (além do log).
        Retorna se o estado terminal foi gravado (False se outra parte já o encerrou).
        """
        hook_error = self._run_abort_hook(kind, job_id, params, status)
        if hook_error:
            message = f"{message}; a rotina de consistência dos dados também falhou"
            warning = (f"ATENÇÃO: a rotina de consistência dos dados falhou ({hook_error}); "
                       "os registros relacionados podem ter ficado em estado intermediário. Consulte o log.")
            error = f"{error} {warning}" if error else warning
        closed = self._transition(job_id, from_statuses, status=status, message=message[:500],
                                  error=error[:2000] if error else None, finished_at=utcnow())
        if not closed:
            logger.info("Tarefa %s já havia sido encerrada por outra parte; estado %s não aplicado.", job_id, status)
        return closed

    def _request_cancel(self, job_id: str, *, reason: str) -> None:
        """Pede cancelamento cooperativo; nunca altera uma tarefa já encerrada (J4)."""
        with self._sessions() as db:
            job = db.get(JobModel, job_id)
            requested_at = (job.cancel_requested_at if job and job.cancel_requested_at else utcnow())
        self._transition(job_id, ("running", "cancelling"), status="cancelling", cancel_requested=True,
                         cancel_requested_at=requested_at, message=reason)

    def _recover_stale_jobs(self) -> None:
        """Tarefas ativas de um serviço anterior: rotina de consistência → ``interrupted`` (J6)."""
        with self._sessions() as db:
            stale = [(j.id, j.kind, json.loads(j.params_json or "{}"))
                     for j in db.query(JobModel).filter(JobModel.status.in_(ACTIVE_STATUSES)).all()]
        for job_id, kind, params in stale:
            logger.warning("Tarefa %s (%s) interrompida por encerramento anterior do serviço.", job_id, kind)
            self._close(job_id, kind, params, from_statuses=ACTIVE_STATUSES, status="interrupted",
                        message="Interrompida: o serviço anterior foi encerrado antes da conclusão.")

    # ------------------------------------------------------------------ supervisão
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
        # J4: só inicia quem efetivamente muda queued → running.
        if not self._transition(job_id, ("queued",), status="running", started_at=utcnow(), message="Em execução"):
            return
        with self._sessions() as db:
            job = db.get(JobModel, job_id)
            kind, params = job.kind, json.loads(job.params_json or "{}")

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
            # Sem processo não há quem finalize a tarefa: registra a falha aqui. A referência
            # só é liberada depois da finalização.
            logger.exception("Falha ao iniciar o processo da tarefa %s (%s)", job_id, kind)
            try:
                self._fail_to_start(job_id, kind, params, exc)
            finally:
                with self._lock:
                    self._processes.pop(job_id, None)
            return

        forced = False
        supervision_error: Optional[BaseException] = None
        try:
            with self._sessions() as db:
                job = db.get(JobModel, job_id)
                if job is not None:
                    job.pid = process.pid
                    db.commit()
            forced = self._monitor(job_id, process)
        except Exception as exc:
            # J3: sem supervisão o processo ficaria órfão; encerra-o e finaliza a tarefa.
            supervision_error = exc
            logger.exception("Falha na supervisão da tarefa %s; encerrando o processo.", job_id)
            self._stop_process(process)
        try:
            self._finalize(job_id, kind, params, process.exitcode, forced, supervision_error)
        finally:
            with self._lock:
                self._processes.pop(job_id, None)

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
                self._stop_process(process)
                return True
        return False

    @staticmethod
    def _stop_process(process) -> None:
        if process.is_alive():
            process.terminate()
            process.join(5)
        if process.is_alive():
            process.kill()
            process.join(5)

    def _fail_to_start(self, job_id: str, kind: str, params: dict, exc: BaseException) -> None:
        """Registra como ``failed`` uma tarefa cujo processo não pôde ser iniciado.

        Ordem garantida: rotina de consistência (``abort_hook``) → estado ``failed`` com
        mensagem e erro. Se a própria rotina falhar, a falha fica explícita no log e no
        diagnóstico da tarefa.
        """
        detail = str(exc).strip() or exc.__class__.__name__
        error = (f"Não foi possível iniciar o processo da tarefa ({exc.__class__.__name__}: {detail}). "
                 "Verifique memória disponível, antivírus e permissões, e tente novamente.")
        self._close(job_id, kind, params, from_statuses=("running", "cancelling"), status="failed",
                    message="Falhou ao iniciar", error=error)

    def _finalize(self, job_id: str, kind: str, params: dict, exitcode: Optional[int], forced: bool,
                  supervision_error: Optional[BaseException] = None) -> None:
        """Finaliza uma tarefa cujo processo terminou sem gravar o próprio estado (J1, J3)."""
        with self._sessions() as db:
            job = db.get(JobModel, job_id)
            if job is None or job.status in TERMINAL_STATUSES:
                return  # o processo da tarefa já finalizou o próprio estado
            cancel_requested = bool(job.cancel_requested)
        error: Optional[str] = None
        if supervision_error is not None:
            status, message = "failed", "Falhou"
            detail = str(supervision_error).strip() or supervision_error.__class__.__name__
            error = (f"Falha na supervisão do processo da tarefa ({supervision_error.__class__.__name__}: "
                     f"{detail}); o processo foi encerrado.")
        elif forced or cancel_requested:
            status = "cancelled"
            message = (f"Cancelada: o processo foi encerrado após {self.cancel_grace:.0f}s sem resposta"
                       if forced else "Cancelada")
        else:
            status, message = "failed", "Falhou"
            error = f"O processo da tarefa terminou inesperadamente (código de saída {exitcode})."
        logger.warning("Tarefa %s finalizada pelo supervisor com status %s (exitcode=%s).", job_id, status, exitcode)
        self._close(job_id, kind, params, from_statuses=("running", "cancelling"), status=status,
                    message=message, error=error)

    def _run_abort_hook(self, kind: str, job_id: str, params: dict, status: str) -> Optional[str]:
        """Executa a rotina de consistência do tipo de tarefa.

        Retorna ``None`` em caso de sucesso (ou se o tipo não tem rotina) e, em caso de
        falha, uma descrição do erro, que também é registrada no log com o traceback.
        As rotinas devem ser idempotentes: podem ser executadas mais de uma vez.
        """
        try:
            hook_path = get_kind(kind).abort_hook
        except ValueError:
            return None
        if not hook_path:
            return None
        try:
            hook = resolve(hook_path)
            with self._sessions() as db:
                hook(db, job_id=job_id, params=params, status=status)
        except Exception as exc:
            logger.exception("Falha ao executar a rotina de consistência (%s) da tarefa %s", hook_path, job_id)
            return f"{exc.__class__.__name__}: {str(exc).strip() or 'sem mensagem'}"
        return None

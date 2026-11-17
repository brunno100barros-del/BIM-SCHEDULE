"""Revisão da Etapa 2 (J1–J6): ordem de encerramento e transições atômicas das tarefas.

A ordem é provada pelo gatilho SQLite de ``test_jobs.install_terminal_audit``: no instante em
que a tarefa recebe o estado terminal, o próprio banco registra se a rotina de consistência
já havia terminado (marca em ``result_json`` gravada pela rotina da tarefa de diagnóstico).
"""
import json
import threading

from fastapi.testclient import TestClient

from app.core.database import SessionLocal
from app.jobs.manager import JobManager
from app.main import create_app
from app.models.job import JobModel
from test_jobs import install_terminal_audit, terminal_audit


def marker(status: str) -> dict:
    return {"abort_hook": status}


# --------------------------------------------------------------------------- J1
def test_j1_crashed_process_runs_consistency_before_failed(runtime):
    install_terminal_audit(runtime.storage.database_url)
    job = runtime.jobs.submit("system.diagnostic", {"steps": 5, "step_seconds": 0.01, "crash_at": 2,
                                                    "abort_marker": True})
    final = runtime.jobs.wait(job["id"])
    assert final["status"] == "failed" and "código de saída 3" in final["error"]
    audit = terminal_audit(runtime.storage.database_url, job["id"])
    assert [(a["status"], a["result"]) for a in audit] == [("failed", marker("failed"))]


def test_j1_forced_termination_runs_consistency_before_cancelled(runtime):
    install_terminal_audit(runtime.storage.database_url)
    job = runtime.jobs.submit("system.diagnostic", {"steps": 400, "step_seconds": 0.05, "ignore_cancel": True,
                                                    "abort_marker": True})
    runtime.jobs.cancel(job["id"])
    final = runtime.jobs.wait(job["id"], timeout=runtime.jobs.cancel_grace + 20)
    assert final["status"] == "cancelled"
    audit = terminal_audit(runtime.storage.database_url, job["id"])
    # Na fila, o cancelamento é imediato (J2); em execução, o encerramento forçado finaliza (J1).
    assert [(a["status"], a["result"]) for a in audit] == [("cancelled", marker("cancelled"))]


def test_j1_consistency_failure_is_explicit_after_process_death(runtime):
    job = runtime.jobs.submit("system.diagnostic", {"steps": 5, "step_seconds": 0.01, "crash_at": 2,
                                                    "abort_hook_fails": True})
    final = runtime.jobs.wait(job["id"])
    assert final["status"] == "failed"
    assert final["message"] == "Falhou; a rotina de consistência dos dados também falhou"
    assert "código de saída 3" in final["error"]
    assert "ATENÇÃO" in final["error"] and "falha simulada na rotina de consistência" in final["error"]


# --------------------------------------------------------------------------- J2
def test_j2_queued_cancel_runs_consistency_before_cancelled(runtime):
    install_terminal_audit(runtime.storage.database_url)
    blocker = runtime.jobs.submit("system.diagnostic", {"steps": 400, "step_seconds": 0.05})
    queued = runtime.jobs.submit("system.diagnostic", {"steps": 1, "abort_marker": True})
    result = runtime.jobs.cancel(queued["id"])
    assert result["status"] == "cancelled" and result["message"] == "Cancelada antes do início"
    audit = terminal_audit(runtime.storage.database_url, queued["id"])
    assert [(a["status"], a["result"]) for a in audit] == [("cancelled", marker("cancelled"))]
    runtime.jobs.cancel(blocker["id"])
    assert runtime.jobs.wait(blocker["id"])["status"] == "cancelled"
    with SessionLocal() as db:
        assert db.get(JobModel, queued["id"]).started_at is None  # nunca foi iniciada


def test_j2_queued_cancel_with_failing_consistency_is_explicit(runtime):
    blocker = runtime.jobs.submit("system.diagnostic", {"steps": 400, "step_seconds": 0.05})
    queued = runtime.jobs.submit("system.diagnostic", {"steps": 1, "abort_hook_fails": True})
    result = runtime.jobs.cancel(queued["id"])
    assert result["status"] == "cancelled"
    assert result["message"] == "Cancelada antes do início; a rotina de consistência dos dados também falhou"
    assert "ATENÇÃO" in result["error"]
    runtime.jobs.cancel(blocker["id"])
    runtime.jobs.wait(blocker["id"])


# --------------------------------------------------------------------------- J3
def test_j3_supervision_failure_stops_process_and_finalizes(runtime, monkeypatch):
    install_terminal_audit(runtime.storage.database_url)
    captured = {}
    real_monitor = runtime.jobs._monitor

    def broken_monitor(job_id, process):
        captured["process"] = process
        monkeypatch.setattr(runtime.jobs, "_monitor", real_monitor)  # só a primeira chamada falha
        raise RuntimeError("falha simulada na supervisão")

    monkeypatch.setattr(runtime.jobs, "_monitor", broken_monitor)
    job = runtime.jobs.submit("system.diagnostic", {"steps": 400, "step_seconds": 0.05, "abort_marker": True})
    final = runtime.jobs.wait(job["id"], timeout=30)
    assert final["status"] == "failed"
    assert "Falha na supervisão do processo da tarefa" in final["error"]
    assert "falha simulada na supervisão" in final["error"]
    assert not captured["process"].is_alive()  # processo não ficou órfão
    assert runtime.jobs.active_count() == 0
    audit = terminal_audit(runtime.storage.database_url, job["id"])
    assert [(a["status"], a["result"]) for a in audit] == [("failed", marker("failed"))]

    nxt = runtime.jobs.submit("system.diagnostic", {"steps": 2, "step_seconds": 0.01})
    assert runtime.jobs.wait(nxt["id"])["status"] == "completed"


# --------------------------------------------------------------------------- J4
def test_j4_cancelled_job_cannot_be_started_later(runtime):
    manager = JobManager(runtime.storage.database_url)  # sem supervisores: controle total da ordem
    try:
        job = manager.submit("system.diagnostic", {"steps": 1})
        assert manager.cancel(job["id"])["status"] == "cancelled"
        manager._run(job["id"])  # o supervisor recebe a tarefa já cancelada
        assert manager.active_count() == 0
        data = manager.get(job["id"])
        assert data["status"] == "cancelled" and data["started_at"] is None
    finally:
        manager.shutdown()


def test_j4_cancel_never_overwrites_a_finished_job(runtime):
    job = runtime.jobs.submit("system.diagnostic", {"steps": 2, "step_seconds": 0.01})
    assert runtime.jobs.wait(job["id"])["status"] == "completed"
    after = runtime.jobs.cancel(job["id"])
    assert after["status"] == "completed" and after["cancel_requested"] is False
    runtime.jobs._request_cancel(job["id"], reason="teste")
    assert runtime.jobs.get(job["id"])["status"] == "completed"


def test_j4_cancel_and_start_race_has_a_single_winner(runtime):
    """Cancelamento e início disputando a mesma tarefa: exatamente um vence, sempre."""
    manager = JobManager(runtime.storage.database_url)
    try:
        for _ in range(30):
            job = manager.submit("system.diagnostic", {"steps": 1})
            barrier = threading.Barrier(2)
            outcome = {}

            def do_cancel():
                barrier.wait()
                outcome["cancel"] = manager.cancel(job["id"])["status"]

            def do_start():
                barrier.wait()
                outcome["started"] = manager._transition(job["id"], ("queued",), status="running")

            threads = [threading.Thread(target=do_cancel), threading.Thread(target=do_start)]
            for t in threads:
                t.start()
            for t in threads:
                t.join(10)
            final = manager.get(job["id"])["status"]
            if outcome["started"]:
                # O início venceu: o cancelamento virou pedido cooperativo, nunca "cancelled" direto.
                assert final == "cancelling", outcome
            else:
                assert final == "cancelled" and outcome["cancel"] == "cancelled", outcome
    finally:
        manager.shutdown()


# --------------------------------------------------------------------------- J5
def test_j5_shutdown_runs_consistency_for_queued_jobs(settings):
    app = create_app(settings)
    with TestClient(app):
        runtime = app.state.runtime
        db_url = runtime.storage.database_url
        install_terminal_audit(db_url)
        blocker = runtime.jobs.submit("system.diagnostic", {"steps": 400, "step_seconds": 0.05})
        queued = runtime.jobs.submit("system.diagnostic", {"steps": 1, "abort_marker": True})
    # Fora do bloco: o serviço foi encerrado.
    audit = terminal_audit(db_url, queued["id"])
    assert [(a["status"], a["result"]) for a in audit] == [("interrupted", marker("interrupted"))]
    manager = JobManager(db_url)
    try:
        assert manager.get(queued["id"])["message"] == "Interrompida: o serviço foi encerrado antes do início."
        assert manager.get(blocker["id"])["is_terminal"] is True
    finally:
        manager.shutdown()


# --------------------------------------------------------------------------- J6
def test_j6_recovery_runs_consistency_before_interrupted(settings):
    app = create_app(settings)
    with TestClient(app):
        db_url = app.state.runtime.storage.database_url
        install_terminal_audit(db_url)
        with SessionLocal() as db:
            db.add(JobModel(id="b" * 32, kind="system.diagnostic", status="running",
                            params_json=json.dumps({"abort_marker": True})))
            db.add(JobModel(id="c" * 32, kind="system.diagnostic", status="cancelling",
                            params_json=json.dumps({"abort_hook_fails": True})))
            db.commit()
    with TestClient(create_app(settings)) as client:
        ok = client.get(f"/api/v1/jobs/{'b' * 32}").json()
        assert ok["status"] == "interrupted"
        audit = terminal_audit(db_url, "b" * 32)
        assert [(a["status"], a["result"]) for a in audit] == [("interrupted", marker("interrupted"))]

        failed_hook = client.get(f"/api/v1/jobs/{'c' * 32}").json()
        assert failed_hook["status"] == "interrupted"
        assert failed_hook["message"].endswith("a rotina de consistência dos dados também falhou")
        assert "ATENÇÃO" in failed_hook["error"]  # diagnóstico visível pela API

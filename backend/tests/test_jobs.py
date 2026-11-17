"""Mecanismo de tarefas: processo separado, progresso, cancelamento, falhas e encerramento."""
import json
import time

from app.core.database import SessionLocal
from app.jobs.manager import JobManager
from app.models.job import JobModel


def test_job_runs_in_separate_process_and_reports_progress(runtime):
    job = runtime.jobs.submit("system.diagnostic", {"steps": 10, "step_seconds": 0.05})
    seen = set()
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        current = runtime.jobs.get(job["id"])
        seen.add(current["progress"])
        if current["is_terminal"]:
            break
        time.sleep(0.02)
    final = runtime.jobs.wait(job["id"])
    assert final["status"] == "completed", final
    assert final["progress"] == 100
    assert final["result"] == {"steps": 10}
    assert any(0 < p < 100 for p in seen), f"progresso intermediário não observado: {sorted(seen)}"
    with SessionLocal() as db:
        pid = db.get(JobModel, job["id"]).pid
    import os
    assert pid and pid != os.getpid()


def test_api_stays_responsive_while_job_runs(client, runtime):
    job = runtime.jobs.submit("system.diagnostic", {"steps": 20, "step_seconds": 0.1})
    latencies = []
    while not runtime.jobs.get(job["id"])["is_terminal"]:
        started = time.perf_counter()
        assert client.get("/api/v1/system/health").status_code == 200
        latencies.append(time.perf_counter() - started)
        time.sleep(0.05)
    assert latencies and max(latencies) < 0.5, latencies
    assert runtime.jobs.wait(job["id"])["status"] == "completed"


def test_cooperative_cancellation_via_api(client, runtime):
    job = runtime.jobs.submit("system.diagnostic", {"steps": 200, "step_seconds": 0.05})
    deadline = time.monotonic() + 30
    while runtime.jobs.get(job["id"])["progress"] < 3 and time.monotonic() < deadline:
        time.sleep(0.02)
    response = client.post(f"/api/v1/jobs/{job['id']}/cancel")
    assert response.status_code == 202
    assert response.json()["status"] in ("cancelling", "cancelled")
    started = time.monotonic()
    final = runtime.jobs.wait(job["id"])
    assert final["status"] == "cancelled"
    assert final["message"] == "Cancelado pelo usuário"  # gravado pelo próprio processo (cooperativo)
    assert time.monotonic() - started < runtime.jobs.cancel_grace
    assert final["progress"] < 100


def test_unresponsive_job_is_terminated_after_grace_period(runtime):
    job = runtime.jobs.submit("system.diagnostic", {"steps": 400, "step_seconds": 0.05, "ignore_cancel": True})
    while runtime.jobs.get(job["id"])["status"] != "running":
        time.sleep(0.02)
    time.sleep(0.3)
    runtime.jobs.cancel(job["id"])
    final = runtime.jobs.wait(job["id"], timeout=runtime.jobs.cancel_grace + 15)
    assert final["status"] == "cancelled"
    assert "encerrado" in final["message"]


def test_failure_is_recorded_with_error_message(runtime):
    job = runtime.jobs.submit("system.diagnostic", {"steps": 5, "step_seconds": 0.01, "fail_at": 3})
    final = runtime.jobs.wait(job["id"])
    assert final["status"] == "failed"
    assert "Falha simulada na etapa 3" in final["error"]


def test_crashed_process_is_detected(runtime):
    job = runtime.jobs.submit("system.diagnostic", {"steps": 5, "step_seconds": 0.01, "crash_at": 2})
    final = runtime.jobs.wait(job["id"])
    assert final["status"] == "failed"
    assert "código de saída 3" in final["error"]


def test_queued_job_can_be_cancelled_before_start(runtime):
    blocker = runtime.jobs.submit("system.diagnostic", {"steps": 40, "step_seconds": 0.05})
    queued = runtime.jobs.submit("system.diagnostic", {"steps": 1})
    cancelled = runtime.jobs.cancel(queued["id"])
    assert cancelled["status"] == "cancelled"
    runtime.jobs.cancel(blocker["id"])
    runtime.jobs.wait(blocker["id"])
    time.sleep(0.3)
    assert runtime.jobs.get(queued["id"])["status"] == "cancelled"


def test_shutdown_stops_running_jobs(settings, tmp_path):
    from fastapi.testclient import TestClient
    from app.main import create_app

    app = create_app(settings)
    with TestClient(app) as client:
        runtime = app.state.runtime
        job = runtime.jobs.submit("system.diagnostic", {"steps": 400, "step_seconds": 0.05})
        while runtime.jobs.get(job["id"])["status"] != "running":
            time.sleep(0.02)
        job_id = job["id"]
        db_url = runtime.storage.database_url
    # fora do bloco: lifespan encerrado
    manager = JobManager(db_url)
    try:
        final = manager.get(job_id)
    finally:
        manager.shutdown()
    assert final["status"] == "cancelled"


def test_stale_jobs_are_marked_interrupted_on_startup(settings):
    from fastapi.testclient import TestClient
    from app.main import create_app

    with TestClient(create_app(settings)) as client:
        with SessionLocal() as db:
            db.add(JobModel(id="a" * 32, kind="system.diagnostic", status="running", progress=40,
                            params_json=json.dumps({})))
            db.commit()
    with TestClient(create_app(settings)) as client:
        body = client.get(f"/api/v1/jobs/{'a' * 32}").json()
        assert body["status"] == "interrupted"
        assert body["is_terminal"] is True


def test_jobs_api_errors(client):
    assert client.get("/api/v1/jobs/inexistente").json()["error"]["code"] == "job_not_found"
    assert client.post("/api/v1/jobs/inexistente/cancel").status_code == 404
    assert client.get("/api/v1/jobs/").status_code == 200


class FailingStartContext:
    """Contexto multiprocessing cujo Process.start() falha nas primeiras N chamadas."""

    def __init__(self, real, failures=1):
        self.real = real
        self.failures = failures

    def Process(self, *args, **kwargs):
        process = self.real.Process(*args, **kwargs)
        if self.failures > 0:
            self.failures -= 1

            def start():
                raise OSError("[WinError 1455] O arquivo de paginação é muito pequeno para concluir a operação")

            process.start = start
        return process


def test_process_start_failure_marks_job_failed_and_supervisor_continues(runtime, monkeypatch):
    monkeypatch.setattr(runtime.jobs, "_mp", FailingStartContext(runtime.jobs._mp, failures=1))
    job = runtime.jobs.submit("system.diagnostic", {"steps": 2, "step_seconds": 0.01})
    final = runtime.jobs.wait(job["id"], timeout=15)
    assert final["status"] == "failed", final
    assert final["is_terminal"] is True and final["finished_at"] is not None
    assert final["message"] == "Falhou ao iniciar"
    assert "Não foi possível iniciar o processo da tarefa" in final["error"]
    assert "OSError" in final["error"] and "WinError 1455" in final["error"]
    with SessionLocal() as db:
        assert db.get(JobModel, job["id"]).pid is None
    assert runtime.jobs.active_count() == 0

    # O supervisor continua atendendo a fila depois da falha.
    next_job = runtime.jobs.submit("system.diagnostic", {"steps": 2, "step_seconds": 0.01})
    assert runtime.jobs.wait(next_job["id"])["status"] == "completed"


def test_process_start_failure_runs_abort_hook_for_ifc(client, runtime, monkeypatch, tmp_path):
    from ifc_factory import build_ifc

    import app.modules.ifc.jobs as ifc_jobs

    monkeypatch.setattr(runtime.jobs, "_mp", FailingStartContext(runtime.jobs._mp, failures=1))
    # Torna determinística a verificação de ordem: mesmo com uma rotina de consistência lenta,
    # a tarefa só pode aparecer como encerrada depois que o modelo IFC foi restaurado.
    original_hook = ifc_jobs.on_parse_aborted

    def slow_hook(*args, **kwargs):
        time.sleep(0.5)
        return original_hook(*args, **kwargs)

    monkeypatch.setattr(ifc_jobs, "on_parse_aborted", slow_hook)
    project_id = client.post("/api/v1/projects/", json={"name": "Falha", "code": "START-FAIL"}).json()["id"]
    ifc = build_ifc(tmp_path / "modelo.ifc", walls=3)
    with ifc.open("rb") as handle:
        body = client.post(f"/api/v1/ifc/project/{project_id}/upload",
                           files={"file": ("modelo.ifc", handle, "application/octet-stream")}).json()
    final = runtime.jobs.wait(body["job_id"], timeout=15)
    assert final["status"] == "failed"
    model = client.get(f"/api/v1/ifc/model/{body['id']}").json()
    assert model["status"] == "failed"  # abort_hook executado: o modelo não fica "queued"/"processing"
    assert body["job_id"] in model["error_message"]
    assert client.get(f"/api/v1/ifc/model/{body['id']}/elements").json() == []

    # Novo envio é processado normalmente pelo mesmo supervisor.
    with ifc.open("rb") as handle:
        retry = client.post(f"/api/v1/ifc/project/{project_id}/upload",
                            files={"file": ("modelo.ifc", handle, "application/octet-stream")}).json()
    assert runtime.jobs.wait(retry["job_id"], timeout=60)["status"] == "completed"

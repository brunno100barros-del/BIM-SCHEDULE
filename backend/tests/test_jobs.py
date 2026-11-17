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

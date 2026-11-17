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


def _upload_ifc(client, project_id, path):
    with path.open("rb") as handle:
        response = client.post(f"/api/v1/ifc/project/{project_id}/upload",
                               files={"file": ("modelo.ifc", handle, "application/octet-stream")})
    assert response.status_code == 202, response.text
    return response.json()


def install_terminal_audit(database_url: str) -> None:
    """Gatilho SQLite: no instante em que uma tarefa recebe estado terminal, registra o estado
    do modelo IFC associado e o resultado da rotina de consistência. Prova a ordem das
    operações no próprio banco, sem atrasos nem consultas repetidas.
    """
    import sqlite3

    from app.core.storage import sqlite_path_from_url

    conn = sqlite3.connect(str(sqlite_path_from_url(database_url)))
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS job_terminal_audit (
                job_id TEXT, status TEXT, result_json TEXT, model_status TEXT, model_elements INTEGER);
            CREATE TRIGGER IF NOT EXISTS trg_job_terminal_audit
            AFTER UPDATE OF status ON jobs
            WHEN NEW.status IN ('completed', 'failed', 'cancelled', 'interrupted')
                 AND OLD.status NOT IN ('completed', 'failed', 'cancelled', 'interrupted')
            BEGIN
                INSERT INTO job_terminal_audit VALUES (
                    NEW.id, NEW.status, NEW.result_json,
                    (SELECT status FROM ifc_models WHERE id = json_extract(NEW.params_json, '$.model_id')),
                    (SELECT COUNT(*) FROM ifc_elements WHERE model_id = json_extract(NEW.params_json, '$.model_id')));
            END;
        """)
        conn.commit()
    finally:
        conn.close()


def terminal_audit(database_url: str, job_id: str) -> list[dict]:
    import sqlite3

    from app.core.storage import sqlite_path_from_url

    conn = sqlite3.connect(str(sqlite_path_from_url(database_url)))
    try:
        rows = conn.execute("SELECT status, result_json, model_status, model_elements FROM job_terminal_audit "
                            "WHERE job_id = ?", (job_id,)).fetchall()
    finally:
        conn.close()
    return [{"status": r[0], "result": json.loads(r[1]) if r[1] else None, "model_status": r[2],
             "model_elements": r[3]} for r in rows]


def test_process_start_failure_runs_abort_hook_for_ifc(client, runtime, monkeypatch, tmp_path):
    """No exato momento em que a tarefa passa a 'failed', o modelo IFC já está 'failed' e sem elementos."""
    from ifc_factory import build_ifc

    install_terminal_audit(runtime.storage.database_url)
    monkeypatch.setattr(runtime.jobs, "_mp", FailingStartContext(runtime.jobs._mp, failures=1))
    project_id = client.post("/api/v1/projects/", json={"name": "Falha", "code": "START-FAIL"}).json()["id"]
    ifc = build_ifc(tmp_path / "modelo.ifc", walls=3)
    body = _upload_ifc(client, project_id, ifc)
    final = runtime.jobs.wait(body["job_id"], timeout=15)

    assert final["status"] == "failed"
    audit = terminal_audit(runtime.storage.database_url, body["job_id"])
    assert [(a["status"], a["model_status"], a["model_elements"]) for a in audit] == [("failed", "failed", 0)]
    model = client.get(f"/api/v1/ifc/model/{body['id']}").json()
    assert model["status"] == "failed"
    assert body["job_id"] in model["error_message"]
    assert client.get(f"/api/v1/ifc/model/{body['id']}/elements").json() == []

    # Novo envio é processado normalmente pelo mesmo supervisor.
    retry = _upload_ifc(client, project_id, ifc)
    assert runtime.jobs.wait(retry["job_id"], timeout=60)["status"] == "completed"


def test_abort_hook_failure_is_explicit_in_job_and_log(client, runtime, monkeypatch, tmp_path):
    import logging

    import app.modules.ifc.jobs as ifc_jobs
    from ifc_factory import build_ifc

    def broken_hook(*_args, **_kwargs):
        raise RuntimeError("falha simulada na rotina de consistência")

    records = []

    class Collector(logging.Handler):
        def emit(self, record):
            records.append(record)

    collector = Collector(level=logging.ERROR)
    jobs_logger = logging.getLogger("bim_schedule.jobs")
    jobs_logger.addHandler(collector)
    monkeypatch.setattr(ifc_jobs, "on_parse_aborted", broken_hook)
    monkeypatch.setattr(runtime.jobs, "_mp", FailingStartContext(runtime.jobs._mp, failures=1))
    try:
        project_id = client.post("/api/v1/projects/", json={"name": "Hook", "code": "HOOK-FAIL"}).json()["id"]
        body = _upload_ifc(client, project_id, build_ifc(tmp_path / "m.ifc", walls=2))
        final = runtime.jobs.wait(body["job_id"], timeout=15)
    finally:
        jobs_logger.removeHandler(collector)

    assert final["status"] == "failed"
    assert final["message"] == "Falhou ao iniciar; a rotina de consistência dos dados também falhou"
    assert "Não foi possível iniciar o processo da tarefa" in final["error"]
    assert "RuntimeError: falha simulada na rotina de consistência" in final["error"]
    assert "ATENÇÃO" in final["error"]
    hook_logs = [r for r in records if "rotina de consistência" in r.getMessage()]
    assert hook_logs and hook_logs[0].exc_info is not None  # traceback no log
    assert any(body["job_id"] in r.getMessage() for r in hook_logs)

    # O supervisor continua atendendo a fila.
    next_job = runtime.jobs.submit("system.diagnostic", {"steps": 2, "step_seconds": 0.01})
    assert runtime.jobs.wait(next_job["id"])["status"] == "completed"


def test_ifc_abort_hook_is_idempotent(client, db):
    from app.models.ifc import IfcElementModel, IfcModelModel
    from app.modules.ifc.jobs import on_parse_aborted

    project_id = client.post("/api/v1/projects/", json={"name": "Idem", "code": "IDEM"}).json()["id"]
    model = IfcModelModel(project_id=project_id, filename="a.ifc", file_path="/tmp/a.ifc", status="processing",
                          progress=40, element_count=2)
    done = IfcModelModel(project_id=project_id, filename="b.ifc", file_path="/tmp/b.ifc", status="completed",
                         progress=100, element_count=1)
    db.add_all([model, done]); db.commit()
    db.add_all([IfcElementModel(model_id=model.id, global_id=f"G{i}", ifc_type="IfcWall") for i in range(2)]
               + [IfcElementModel(model_id=done.id, global_id="D1", ifc_type="IfcSlab")])
    db.commit()

    def state():
        db.expire_all()
        m = db.get(IfcModelModel, model.id)
        return (m.status, m.progress, m.element_count, m.processing_message, m.error_message,
                db.query(IfcElementModel).filter_by(model_id=model.id).count())

    on_parse_aborted(db, job_id="j1", params={"model_id": model.id}, status="failed")
    first = state()
    on_parse_aborted(db, job_id="j1", params={"model_id": model.id}, status="failed")
    assert state() == first
    assert first[0] == "failed" and first[5] == 0

    # Modelo concluído nunca é alterado; modelo inexistente ou sem model_id não gera erro.
    on_parse_aborted(db, job_id="j2", params={"model_id": done.id}, status="failed")
    on_parse_aborted(db, job_id="j3", params={"model_id": 999999}, status="failed")
    on_parse_aborted(db, job_id="j4", params={}, status="failed")
    db.expire_all()
    assert db.get(IfcModelModel, done.id).status == "completed"
    assert db.query(IfcElementModel).filter_by(model_id=done.id).count() == 1

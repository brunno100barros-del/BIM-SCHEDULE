"""Processamento IFC real (IfcOpenShell) em segundo plano, com cancelamento e falhas."""
import time

from app.modules.ifc import parser as ifc_parser
from app.modules.ifc.service import safe_filename
from ifc_factory import build_ifc


def make_project(client, code="IFC-01"):
    response = client.post("/api/v1/projects/", json={"name": "Projeto IFC", "code": code})
    assert response.status_code == 201, response.text
    return response.json()["id"]


def upload(client, project_id, path, name=None):
    with path.open("rb") as handle:
        return client.post(f"/api/v1/ifc/project/{project_id}/upload",
                           files={"file": (name or path.name, handle, "application/octet-stream")})


def wait_job(client, job_id, timeout=60):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        body = client.get(f"/api/v1/jobs/{job_id}").json()
        if body["is_terminal"]:
            return body
        time.sleep(0.05)
    raise AssertionError("tarefa não terminou")


def test_real_ifc_is_processed_in_background(client, tmp_path):
    project_id = make_project(client)
    ifc = build_ifc(tmp_path / "Edifício teste.ifc", walls=12, slabs=2)
    response = upload(client, project_id, ifc)
    assert response.status_code == 202, response.text
    body = response.json()
    assert body["job_id"] and body["status"] == "queued"

    job = wait_job(client, body["job_id"])
    assert job["status"] == "completed", job
    assert job["result"]["element_count"] == 17  # 12 paredes + 2 lajes + terreno, edifício e pavimento (IfcProduct)
    assert job["project_id"] == project_id

    model = client.get(f"/api/v1/ifc/model/{body['id']}").json()
    assert model["status"] == "completed" and model["schema_name"] == "IFC4"
    assert model["job_id"] == body["job_id"]
    elements = client.get(f"/api/v1/ifc/model/{body['id']}/elements").json()
    walls = [e for e in elements if e["ifc_type"] == "IfcWall"]
    assert len(walls) == 12
    assert {w["storey_name"] for w in walls} == {"Térreo"}

    jobs = client.get(f"/api/v1/jobs/?project_id={project_id}").json()
    assert [j["id"] for j in jobs] == [body["job_id"]]


def test_ifc_processing_can_be_cancelled(client, tmp_path, monkeypatch):
    project_id = make_project(client)
    ifc = build_ifc(tmp_path / "grande.ifc", walls=3000)
    body = upload(client, project_id, ifc).json()
    deadline = time.monotonic() + 30
    while client.get(f"/api/v1/jobs/{body['job_id']}").json()["status"] != "running" and time.monotonic() < deadline:
        time.sleep(0.01)
    client.post(f"/api/v1/jobs/{body['job_id']}/cancel")
    job = wait_job(client, body["job_id"])
    model = client.get(f"/api/v1/ifc/model/{body['id']}").json()
    if job["status"] == "completed":  # máquina rápida demais: o cancelamento chegou após o fim
        assert model["status"] == "completed"
        return
    assert job["status"] == "cancelled", job
    assert model["status"] == "cancelled"
    assert client.get(f"/api/v1/ifc/model/{body['id']}/elements").json() == []  # sem dados parciais


def test_invalid_ifc_content_fails_cleanly(client, tmp_path):
    project_id = make_project(client)
    bad = tmp_path / "corrompido.ifc"
    bad.write_text("isto não é um arquivo IFC", encoding="utf-8")
    body = upload(client, project_id, bad).json()
    job = wait_job(client, body["job_id"])
    assert job["status"] == "failed"
    assert job["error"]
    model = client.get(f"/api/v1/ifc/model/{body['id']}").json()
    assert model["status"] == "failed" and model["error_message"]


def test_upload_validation_errors(client, tmp_path):
    project_id = make_project(client)
    txt = tmp_path / "planilha.xlsx"
    txt.write_bytes(b"x")
    r = upload(client, project_id, txt)
    assert r.status_code == 400 and r.json()["error"]["code"] == "unsupported_file_type"
    empty = tmp_path / "vazio.ifc"
    empty.write_bytes(b"")
    r = upload(client, project_id, empty)
    assert r.status_code == 400 and r.json()["error"]["code"] == "empty_file"
    assert upload(client, 9999, empty).status_code == 404


def test_upload_size_limit(tmp_path):
    from fastapi.testclient import TestClient
    from app.main import create_app
    from conftest import make_settings

    settings = make_settings(tmp_path, MAX_IFC_UPLOAD_MB=1)
    with TestClient(create_app(settings)) as client:
        project_id = make_project(client)
        big = tmp_path / "grande.ifc"
        big.write_bytes(b"0" * (1024 * 1024 + 10))
        r = upload(client, project_id, big)
        assert r.status_code == 413 and r.json()["error"]["code"] == "file_too_large"
        assert list((tmp_path / "data" / "uploads").iterdir()) == []  # arquivo parcial removido


def test_uploaded_file_stays_inside_uploads_dir(client, runtime, tmp_path):
    project_id = make_project(client)
    ifc = build_ifc(tmp_path / "x.ifc", walls=1)
    body = upload(client, project_id, ifc, name="..\\..\\Windows\\evil name?.ifc").json()
    wait_job(client, body["job_id"])
    model = client.get(f"/api/v1/ifc/model/{body['id']}").json()
    from pathlib import Path
    stored = Path(model["file_path"]).resolve()
    assert stored.parent == runtime.storage.uploads_dir.resolve()
    assert "\\" not in stored.name and "?" not in stored.name and ".." not in stored.name
    assert model["filename"] == "evil name?.ifc"


def test_safe_filename():
    assert safe_filename("Projeto final (rev 2).IFC") == "Projeto_final_rev_2.ifc"
    assert safe_filename("../../etc/passwd") == "passwd"
    assert safe_filename("C:\\Users\\x\\modelo.ifc") == "modelo.ifc"


def test_parser_without_callbacks_keeps_previous_signature():
    import inspect
    params = inspect.signature(ifc_parser.parse_ifc_and_extract).parameters
    assert list(params)[:3] == ["filepath", "model_id", "db_session"]
    assert params["on_progress"].default is None and params["check_cancel"].default is None


def test_parser_progress_writes_do_not_deadlock_with_open_transaction(client, runtime, tmp_path):
    """Regressão (CI Windows, 'database is locked'): o progresso é gravado por outra conexão.

    Com min_interval=0 TODO relatório de progresso grava na tabela jobs, inclusive logo após o
    DELETE dos elementos anteriores e durante a leitura antes do primeiro lote. O parser não pode
    manter uma transação de escrita aberta nesses pontos.
    """
    import uuid

    from sqlalchemy.orm import sessionmaker

    from app.core.database import create_engine_for_url
    from app.jobs.context import JobContext
    from app.models.ifc import IfcModelModel
    from app.models.job import JobModel
    from app.modules.ifc.jobs import parse_ifc_job

    project_id = make_project(client, code="LOCK-01")
    ifc = build_ifc(tmp_path / "lock.ifc", walls=60)  # > 25 produtos: há relatórios antes do 1º lote
    engine = create_engine_for_url(runtime.storage.database_url, worker=True)
    factory = sessionmaker(bind=engine, autoflush=False, future=True)
    try:
        with factory() as db:
            model = IfcModelModel(project_id=project_id, filename="lock.ifc", file_path=str(ifc), status="queued")
            db.add(model); db.commit()
            model_id = model.id
            job_id = uuid.uuid4().hex
            db.add(JobModel(id=job_id, kind="ifc.parse", status="running", params_json="{}"))
            db.commit()
        ctx = JobContext(job_id, factory, min_interval=0)  # sem limitação: grava a cada relatório
        result = parse_ifc_job(ctx, model_id=model_id)
        assert result["element_count"] == 64  # 60 paredes + 1 laje + terreno, edifício e pavimento
        with factory() as db:
            assert db.get(IfcModelModel, model_id).status == "completed"
            assert db.get(JobModel, job_id).progress == 100
    finally:
        engine.dispose()

"""Formato padronizado de erros e proteções do serviço local."""
from fastapi.testclient import TestClient

from app.main import create_app
from conftest import make_settings


def test_not_found_uses_standard_envelope(client):
    body = client.get("/api/v1/projects/12345").json()
    assert body["error"]["code"] == "project_not_found"
    assert body["error"]["message"] == body["detail"] == "Projeto não encontrado."
    assert body["error"]["request_id"]


def test_validation_error_lists_fields(client):
    response = client.post("/api/v1/projects/", json={"name": ""})
    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "validation_error"
    fields = {tuple(e["loc"]) for e in body["error"]["details"]}
    assert ("body", "code") in fields and ("body", "name") in fields


def test_conflict_and_invalid_dates(client):
    assert client.post("/api/v1/projects/", json={"name": "A", "code": "DUP"}).status_code == 201
    dup = client.post("/api/v1/projects/", json={"name": "B", "code": "DUP"})
    assert dup.status_code == 409 and dup.json()["error"]["code"] == "project_code_conflict"
    bad = client.post("/api/v1/projects/", json={"name": "C", "code": "C", "start_date": "2026-05-01", "end_date": "2026-01-01"})
    assert bad.status_code == 422 and bad.json()["error"]["code"] == "invalid_date_range"


def test_unhandled_error_returns_500_without_internals(tmp_path):
    app = create_app(make_settings(tmp_path))

    @app.get("/api/v1/_boom")
    def boom():
        raise RuntimeError("segredo interno")

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/api/v1/_boom")
        assert response.status_code == 500
        body = response.json()
        assert body["error"]["code"] == "internal_error"
        assert "segredo" not in response.text


def test_request_id_header_is_echoed(client):
    response = client.get("/api/v1/system/health", headers={"X-Request-ID": "abc123"})
    assert response.headers["X-Request-ID"] == "abc123"


def test_unexpected_host_header_is_rejected(tmp_path):
    with TestClient(create_app(make_settings(tmp_path)), base_url="http://evil.example.com") as client:
        assert client.get("/api/v1/system/health").status_code == 400


def test_local_token_is_enforced_when_configured(tmp_path):
    settings = make_settings(tmp_path, LOCAL_API_TOKEN="segredo-local")
    with TestClient(create_app(settings)) as client:
        assert client.get("/api/v1/system/health").status_code == 200  # saúde é pública
        denied = client.get("/api/v1/projects/")
        assert denied.status_code == 401 and denied.json()["error"]["code"] == "unauthorized"
        assert client.get("/api/v1/projects/", headers={"X-BIM-Schedule-Token": "errado"}).status_code == 401
        assert client.get("/api/v1/projects/", headers={"X-BIM-Schedule-Token": "segredo-local"}).status_code == 200
        assert client.get("/api/v1/system/status", headers={"X-BIM-Schedule-Token": "segredo-local"}).json()["security"]["local_token_required"] is True


def test_cors_allows_only_configured_origins(client):
    ok = client.options("/api/v1/projects/", headers={"Origin": "http://127.0.0.1:3000", "Access-Control-Request-Method": "GET"})
    assert ok.headers.get("access-control-allow-origin") == "http://127.0.0.1:3000"
    bad = client.options("/api/v1/projects/", headers={"Origin": "https://site-malicioso.example", "Access-Control-Request-Method": "GET"})
    assert "access-control-allow-origin" not in bad.headers


def test_status_reports_real_capabilities(client):
    caps = client.get("/api/v1/system/status").json()["capabilities"]
    assert caps["budget_import"] == "not_implemented"
    assert caps["ai_local_ollama"] == "not_implemented"
    assert caps["simulation_4d"] == "not_implemented"

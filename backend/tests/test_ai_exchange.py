"""Preparação para IA: pacote de pedido, validação de respostas e provedores (sem rede externa)."""
import httpx

from app.modules.ai.exchange import AIRequestPackage
from app.modules.ai.providers.base import ProviderNotImplemented
from app.modules.ai.providers.ollama import OllamaProvider


def setup_project(client):
    pid = client.post("/api/v1/projects/", json={"name": "Torre", "code": "IA-01", "start_date": "2026-01-01",
                                                   "end_date": "2026-12-31"}).json()["id"]
    wbs = client.post("/api/v1/activities/wbs", json={"project_id": pid, "name": "Estrutura", "code": "1"}).json()["id"]
    a = client.post("/api/v1/activities/", json={"project_id": pid, "wbs_id": wbs, "name": "Pilares", "code": "P", "duration": 5}).json()["id"]
    b = client.post("/api/v1/activities/", json={"project_id": pid, "wbs_id": wbs, "name": "Vigas", "code": "V", "duration": 4}).json()["id"]
    client.post("/api/v1/activities/precedences", json={"predecessor_id": a, "successor_id": b})
    return pid, a, b


def test_request_package_contains_project_data_and_validates(client):
    pid, a, b = setup_project(client)
    response = client.get(f"/api/v1/ai/projects/{pid}/request-package")
    assert response.status_code == 200
    assert "attachment" in response.headers["content-disposition"]
    package = AIRequestPackage.model_validate(response.json())
    assert package.format == "bim-schedule-ai-request" and package.schema_version == 1
    assert package.project.code == "IA-01" and package.project.target_duration_days == 364
    assert {x.code for x in package.activities} == {"P", "V"}
    assert package.precedences[0].relation_type == "FS"
    assert package.response_contract.format == "bim-schedule-ai-response"


def test_valid_response_is_accepted_without_changing_the_plan(client):
    pid, a, b = setup_project(client)
    before = client.get(f"/api/v1/activities/project/{pid}").json()
    payload = {
        "format": "bim-schedule-ai-response", "schema_version": 1,
        "provider": {"kind": "manual-claude", "model": "claude-opus-5-5"},
        "methodology_proposals": [{"title": "Estrutura convencional", "description": "Concreto moldado in loco."}],
        "activities_updates": [{"id": a, "optimistic": 4, "most_likely": 5, "pessimistic": 8}],
        "sequence_suggestions": [{"predecessor_id": a, "successor_id": b, "relation_type": "SS", "lag": 2}],
        "assumptions": ["Equipe de 6 armadores"],
    }
    result = client.post(f"/api/v1/ai/projects/{pid}/validate-response", json=payload).json()
    assert result["valid"] is True, result
    assert result["summary"]["activities_updates"] == 1
    assert client.get(f"/api/v1/activities/project/{pid}").json() == before


def test_invalid_responses_are_reported(client):
    pid, a, b = setup_project(client)
    wrong_order = {"format": "bim-schedule-ai-response", "schema_version": 1, "provider": {"kind": "manual-claude"},
                   "activities_updates": [{"id": a, "optimistic": 9, "most_likely": 5, "pessimistic": 8}]}
    result = client.post(f"/api/v1/ai/projects/{pid}/validate-response", json=wrong_order).json()
    assert result["valid"] is False and "otimista" in result["errors"][0]["msg"]

    foreign = {"format": "bim-schedule-ai-response", "schema_version": 1, "provider": {"kind": "ollama"},
               "activities_updates": [{"id": 99999}],
               "sequence_suggestions": [{"predecessor_id": a, "successor_id": a}]}
    result = client.post(f"/api/v1/ai/projects/{pid}/validate-response", json=foreign).json()
    assert result["valid"] is False and len(result["errors"]) == 2

    extra = {"format": "bim-schedule-ai-response", "schema_version": 1, "provider": {"kind": "manual-claude"},
             "inventado": True}
    assert client.post(f"/api/v1/ai/projects/{pid}/validate-response", json=extra).json()["valid"] is False

    assert client.post(f"/api/v1/ai/projects/{pid}/validate-response", json=[1, 2]).json()["valid"] is False


def test_legacy_demo_response_is_converted_with_warning(client):
    pid, a, _ = setup_project(client)
    legacy = {"activities_updates": [{"id": a, "optimistic": 3, "most_likely": 5, "pessimistic": 7, "risk_note": "chuva"}],
              "risks": [{"title": "Chuva", "probability": "média", "impact": "alto", "mitigation": "lona"}],
              "assumptions": []}
    result = client.post(f"/api/v1/ai/projects/{pid}/validate-response", json=legacy).json()
    assert result["valid"] is True
    assert result["summary"]["provider"] == "legacy-demo"
    assert any("formato antigo" in w for w in result["warnings"])


def test_schema_and_provider_endpoints(client):
    schema = client.get("/api/v1/ai/schema/response").json()
    assert "activities_updates" in schema["properties"]
    assert client.get("/api/v1/ai/schema/outro").status_code == 422
    providers = client.get("/api/v1/ai/providers").json()
    assert {p["kind"] for p in providers["providers"]} == {"manual-claude", "ollama"}
    assert client.get("/api/v1/ai/providers/manual-claude/status").json()["availability"] == "manual"
    assert client.get("/api/v1/ai/providers/desconhecido/status").status_code == 404


def test_ollama_status_without_server_and_with_mocked_server():
    unreachable = OllamaProvider("http://127.0.0.1:9", "qwen3.5:4b", timeout=0.5).status()
    assert unreachable.availability == "unavailable"

    def handler(request: httpx.Request):
        assert request.url.path == "/api/tags"
        return httpx.Response(200, json={"models": [{"name": "qwen3.5:4b"}]})

    provider = OllamaProvider("http://127.0.0.1:11434", "qwen3.5:4b", transport=httpx.MockTransport(handler))
    status = provider.status()
    assert status.availability == "not_implemented" and status.details["model_installed"] is True
    try:
        provider.analyze(None)  # type: ignore[arg-type]
    except ProviderNotImplemented:
        pass
    else:
        raise AssertionError("analyze deveria indicar que não está implementado")

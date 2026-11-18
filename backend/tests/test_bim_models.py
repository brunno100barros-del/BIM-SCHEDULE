"""Etapa 3 — Fase 1: modelos lógicos, revisões, remoção segura e isolamento entre arquivos."""
import hashlib
import json
from pathlib import Path

from ifc_factory import build_ifc

API = "/api/v1"


def project(client, code):
    response = client.post(f"{API}/projects/", json={"name": f"Projeto {code}", "code": code})
    assert response.status_code == 201, response.text
    return response.json()["id"]


def upload(client, project_id, path, **form):
    with Path(path).open("rb") as handle:
        return client.post(f"{API}/ifc/project/{project_id}/upload",
                           files={"file": (Path(path).name, handle, "application/octet-stream")},
                           data={k: str(v) for k, v in form.items() if v is not None})


def wait(runtime, job_id, timeout=60):
    result = runtime.jobs.wait(job_id, timeout=timeout)
    assert result["is_terminal"], result
    return result


def processed(client, runtime, project_id, path, **form):
    response = upload(client, project_id, path, **form)
    assert response.status_code == 202, response.text
    body = response.json()
    assert wait(runtime, body["job_id"])["status"] == "completed"
    return body


def bim_models(client, project_id):
    return client.get(f"{API}/ifc/project/{project_id}/bim-models").json()


# ------------------------------------------------------------------ modelos e revisões
def test_upload_creates_model_with_revision_metadata(client, runtime, tmp_path):
    pid = project(client, "BM-01")
    ifc = build_ifc(tmp_path / "Estrutura Torre A.ifc", walls=4)
    body = processed(client, runtime, pid, ifc, model_name="Estrutura Torre A", discipline_hint="estrutura_concreto")
    assert body["revision_number"] == 1 and body["warnings"] == []

    models = bim_models(client, pid)
    assert len(models) == 1
    m = models[0]
    assert m["name"] == "Estrutura Torre A" and m["discipline_hint"] == "estrutura_concreto"
    assert m["current_revision_id"] == body["id"]
    rev = m["revisions"][0]
    assert rev["revision_number"] == 1 and rev["is_current"] is True and rev["status"] == "completed"
    assert rev["file_size"] == ifc.stat().st_size
    assert rev["sha256"] == hashlib.sha256(ifc.read_bytes()).hexdigest()
    assert rev["schema_name"] == "IFC4"
    model = client.get(f"{API}/ifc/model/{body['id']}").json()
    assert model["ifc_project_global_id"]
    header = json.loads(model["header_json"])
    assert "IfcOpenShell" in str(header.get("originating_system", "")) + str(header.get("preprocessor_version", ""))


def test_new_revision_becomes_current_only_after_success(client, runtime, tmp_path):
    pid = project(client, "BM-02")
    v1 = processed(client, runtime, pid, build_ifc(tmp_path / "a.ifc", walls=2))
    bim_id = v1["bim_model_id"]
    bad = tmp_path / "a_rev2.ifc"
    bad.write_text("não é IFC", encoding="utf-8")
    failed = upload(client, pid, bad, bim_model_id=bim_id).json()
    assert failed["revision_number"] == 2
    assert wait(runtime, failed["job_id"])["status"] == "failed"
    revs = {r["revision_number"]: r for r in bim_models(client, pid)[0]["revisions"]}
    assert revs[1]["is_current"] is True and revs[2]["is_current"] is False  # falha não substitui a vigente

    v3 = processed(client, runtime, pid, build_ifc(tmp_path / "a_rev3.ifc", walls=3), bim_model_id=bim_id)
    assert v3["revision_number"] == 3
    m = bim_models(client, pid)[0]
    assert m["current_revision_id"] == v3["id"]
    assert [r["revision_number"] for r in m["revisions"] if r["is_current"]] == [3]


def test_duplicate_file_in_same_model_is_rejected_and_warned_elsewhere(client, runtime, tmp_path):
    pid = project(client, "BM-03")
    ifc = build_ifc(tmp_path / "x.ifc", walls=2)
    first = processed(client, runtime, pid, ifc)
    again = upload(client, pid, ifc, bim_model_id=first["bim_model_id"])
    assert again.status_code == 409 and again.json()["error"]["code"] == "ifc_revision_duplicate"
    other = upload(client, pid, ifc).json()  # novo modelo lógico: aceito, com aviso
    assert other["warnings"] and "SHA-256" in other["warnings"][0]
    wait(runtime, other["job_id"])
    assert len(list(runtime.storage.uploads_dir.iterdir())) == 2  # o arquivo recusado não ficou no disco


def test_invalid_inputs(client, tmp_path):
    pid = project(client, "BM-04")
    other_pid = project(client, "BM-04B")
    ifc = build_ifc(tmp_path / "y.ifc", walls=1)
    r = upload(client, pid, ifc, discipline_hint="marcenaria")
    assert r.status_code == 422 and r.json()["error"]["code"] == "invalid_discipline_hint"
    r = upload(client, pid, ifc, bim_model_id=9999)
    assert r.status_code == 404 and r.json()["error"]["code"] == "bim_model_not_found"
    foreign = upload(client, other_pid, ifc).json()["bim_model_id"]
    r = upload(client, pid, ifc, bim_model_id=foreign)  # modelo de outro projeto
    assert r.status_code == 404


def test_same_globalids_in_two_files_are_never_mixed(client, runtime, tmp_path):
    """Mesmo arquivo de origem em dois modelos: GlobalIds idênticos, elementos e vínculos isolados."""
    pid = project(client, "BM-05")
    ifc = build_ifc(tmp_path / "base.ifc", walls=3)
    a = processed(client, runtime, pid, ifc, model_name="Arquitetura")
    copy = tmp_path / "copia.ifc"
    copy.write_bytes(ifc.read_bytes() + b"\n")  # mesmo conteúdo IFC, SHA diferente
    b = processed(client, runtime, pid, copy, model_name="Arquitetura (cópia)")
    els_a = client.get(f"{API}/ifc/model/{a['id']}/elements").json()
    els_b = client.get(f"{API}/ifc/model/{b['id']}/elements").json()
    gids_a = {e["global_id"] for e in els_a}
    assert gids_a == {e["global_id"] for e in els_b}  # GlobalIds repetidos entre arquivos
    assert not ({e["id"] for e in els_a} & {e["id"] for e in els_b})  # identidades internas distintas
    assert all(e["model_id"] == a["id"] for e in els_a) and all(e["model_id"] == b["id"] for e in els_b)


def test_revision_candidates_and_regrouping(client, runtime, tmp_path):
    pid = project(client, "BM-06")
    ifc = build_ifc(tmp_path / "torre.ifc", walls=2)
    first = processed(client, runtime, pid, ifc)
    copy = tmp_path / "torre_r1.ifc"
    copy.write_bytes(ifc.read_bytes() + b"\n")
    second = processed(client, runtime, pid, copy)  # importado por engano como modelo novo
    assert first["bim_model_id"] != second["bim_model_id"]
    candidates = client.get(f"{API}/ifc/model/{second['id']}/revision-candidates").json()
    assert candidates[0]["bim_model_id"] == first["bim_model_id"]
    assert "mesmo GlobalId de IfcProject" in candidates[0]["reasons"] and candidates[0]["strength"] == "alta"

    moved = client.post(f"{API}/ifc/model/{second['id']}/move-to-bim-model",
                        json={"bim_model_id": first["bim_model_id"]}).json()
    assert moved["bim_model_id"] == first["bim_model_id"] and moved["revision_number"] == 2
    models = bim_models(client, pid)
    assert len(models) == 1  # o modelo de origem, agora vazio, foi encerrado
    assert [r["revision_number"] for r in models[0]["revisions"]] == [1, 2]
    assert models[0]["current_revision_id"] == second["id"]


def test_update_bim_model(client, runtime, tmp_path):
    pid = project(client, "BM-07")
    body = processed(client, runtime, pid, build_ifc(tmp_path / "e.ifc", walls=1))
    r = client.patch(f"{API}/ifc/bim-models/{body['bim_model_id']}", json={"name": "Elétrica", "discipline_hint": "eletrica"})
    assert r.status_code == 200 and r.json()["name"] == "Elétrica" and r.json()["discipline_hint"] == "eletrica"
    assert client.patch(f"{API}/ifc/bim-models/{body['bim_model_id']}", json={"discipline_hint": "x"}).status_code == 422


# ------------------------------------------------------------------ remoção segura
def link_first_element(client, project_id, model_id, code):
    element = client.get(f"{API}/ifc/model/{model_id}/elements").json()[0]
    act = client.post(f"{API}/activities/", json={"project_id": project_id, "name": code, "code": code, "duration": 1}).json()
    assert client.post(f"{API}/activities/{act['id']}/ifc-elements", json={"ifc_element_id": element["id"]}).status_code == 201
    return act["id"], element["id"]


def test_delete_revision_preserves_other_revisions_files_links_and_projects(client, runtime, tmp_path):
    pid = project(client, "DEL-01")
    other_pid = project(client, "DEL-02")
    v1 = processed(client, runtime, pid, build_ifc(tmp_path / "m.ifc", walls=3))
    v2 = processed(client, runtime, pid, build_ifc(tmp_path / "m_r2.ifc", walls=4), bim_model_id=v1["bim_model_id"])
    other = processed(client, runtime, other_pid, build_ifc(tmp_path / "outro.ifc", walls=2))
    act_v1, _ = link_first_element(client, pid, v1["id"], "A1")
    act_v2, el_v2 = link_first_element(client, pid, v2["id"], "A2")
    file_v1 = Path(client.get(f"{API}/ifc/model/{v1['id']}").json()["file_path"])
    file_v2 = Path(client.get(f"{API}/ifc/model/{v2['id']}").json()["file_path"])
    file_other = Path(client.get(f"{API}/ifc/model/{other['id']}").json()["file_path"])

    # Com vínculos: exige confirmação explícita.
    refused = client.delete(f"{API}/ifc/model/{v2['id']}")
    assert refused.status_code == 409 and refused.json()["error"]["details"]["linked_elements"] == 1

    accepted = client.delete(f"{API}/ifc/model/{v2['id']}?confirm_links=true")
    assert accepted.status_code == 202
    # Oculta de imediato e devolve a vigência à revisão anterior.
    assert [m["id"] for m in client.get(f"{API}/ifc/project/{pid}/models").json()] == [v1["id"]]
    assert bim_models(client, pid)[0]["current_revision_id"] == v1["id"]
    result = wait(runtime, accepted.json()["job_id"])
    assert result["status"] == "completed"
    assert result["result"] == {"model_id": v2["id"], "elements_deleted": 8, "links_deleted": 1, "file_deleted": True}  # 4 paredes + 1 laje + 3 espaciais

    assert not file_v2.exists()
    assert file_v1.exists() and file_other.exists()
    gone = client.get(f"{API}/ifc/model/{v2['id']}").json()
    assert gone["status"] == "deleted" and gone["is_current"] is False  # registro mantido para auditoria
    assert client.get(f"{API}/ifc/model/{v2['id']}/elements").status_code == 404
    assert client.get(f"{API}/activities/{act_v2}/ifc-elements").json() == []
    assert len(client.get(f"{API}/activities/{act_v1}/ifc-elements").json()) == 1  # vínculo da v1 intacto
    assert len(client.get(f"{API}/ifc/model/{v1['id']}/elements").json()) == 7  # 3 paredes + 1 laje + 3 espaciais
    assert len(client.get(f"{API}/ifc/model/{other['id']}/elements").json()) == 6
    assert client.get(f"{API}/projects/{pid}").status_code == 200
    assert client.get(f"{API}/activities/project/{pid}").json()  # atividades não foram removidas
    assert client.delete(f"{API}/ifc/model/{v2['id']}").status_code == 404  # já removida


def test_delete_bim_model_removes_only_its_revisions(client, runtime, tmp_path):
    pid = project(client, "DEL-03")
    a1 = processed(client, runtime, pid, build_ifc(tmp_path / "a.ifc", walls=2), model_name="A")
    a2 = processed(client, runtime, pid, build_ifc(tmp_path / "a2.ifc", walls=2), bim_model_id=a1["bim_model_id"])
    b = processed(client, runtime, pid, build_ifc(tmp_path / "b.ifc", walls=5), model_name="B")
    response = client.delete(f"{API}/ifc/bim-models/{a1['bim_model_id']}")
    assert response.status_code == 202
    for job in response.json()["jobs"]:
        assert wait(runtime, job["job_id"])["status"] == "completed"
    assert {m["name"] for m in bim_models(client, pid)} == {"B"}
    assert {client.get(f"{API}/ifc/model/{i}").json()["status"] for i in (a1["id"], a2["id"])} == {"deleted"}
    assert len(client.get(f"{API}/ifc/model/{b['id']}/elements").json()) == 9


def test_cannot_delete_revision_while_processing(client, runtime, tmp_path):
    pid = project(client, "DEL-04")
    blocker = runtime.jobs.submit("system.diagnostic", {"steps": 400, "step_seconds": 0.05})  # ocupa o único processo
    body = upload(client, pid, build_ifc(tmp_path / "p.ifc", walls=1)).json()
    r = client.delete(f"{API}/ifc/model/{body['id']}")
    assert r.status_code == 409 and r.json()["error"]["code"] == "ifc_model_busy"
    runtime.jobs.cancel(blocker["id"])
    wait(runtime, blocker["id"])
    wait(runtime, body["job_id"])


def test_cancelled_deletion_stays_hidden_and_can_resume(client, runtime, tmp_path):
    pid = project(client, "DEL-05")
    body = processed(client, runtime, pid, build_ifc(tmp_path / "c.ifc", walls=3))
    blocker = runtime.jobs.submit("system.diagnostic", {"steps": 400, "step_seconds": 0.05})
    job_id = client.delete(f"{API}/ifc/model/{body['id']}").json()["job_id"]
    runtime.jobs.cancel(job_id)  # ainda na fila: cancelada antes de começar
    assert wait(runtime, job_id)["status"] == "cancelled"
    model = client.get(f"{API}/ifc/model/{body['id']}").json()
    assert model["status"] == "deleting" and "Solicite a remoção novamente" in model["processing_message"]
    assert client.get(f"{API}/ifc/project/{pid}/models").json() == []  # continua oculta
    runtime.jobs.cancel(blocker["id"])
    wait(runtime, blocker["id"])
    retry = client.delete(f"{API}/ifc/model/{body['id']}").json()
    assert wait(runtime, retry["job_id"])["status"] == "completed"
    assert client.get(f"{API}/ifc/model/{body['id']}").json()["status"] == "deleted"


def test_linking_to_removed_revision_is_refused(client, runtime, tmp_path):
    pid = project(client, "DEL-06")
    body = processed(client, runtime, pid, build_ifc(tmp_path / "l.ifc", walls=1))
    element = client.get(f"{API}/ifc/model/{body['id']}/elements").json()[0]
    blocker = runtime.jobs.submit("system.diagnostic", {"steps": 400, "step_seconds": 0.05})
    client.delete(f"{API}/ifc/model/{body['id']}")  # fica 'deleting' enquanto a tarefa aguarda na fila
    act = client.post(f"{API}/activities/", json={"project_id": pid, "name": "X", "code": "X", "duration": 1}).json()
    r = client.post(f"{API}/activities/{act['id']}/ifc-elements", json={"ifc_element_id": element["id"]})
    assert r.status_code == 400 and "removida" in r.json()["detail"]
    runtime.jobs.cancel(blocker["id"])
    wait(runtime, blocker["id"])


def test_project_deletion_removes_only_its_files(client, runtime, tmp_path):
    keep = project(client, "PRJ-KEEP")
    drop = project(client, "PRJ-DROP")
    kept = processed(client, runtime, keep, build_ifc(tmp_path / "keep.ifc", walls=1))
    dropped = processed(client, runtime, drop, build_ifc(tmp_path / "drop.ifc", walls=1))
    kept_file = Path(client.get(f"{API}/ifc/model/{kept['id']}").json()["file_path"])
    dropped_file = Path(client.get(f"{API}/ifc/model/{dropped['id']}").json()["file_path"])
    outside = tmp_path / "fora_da_pasta.ifc"
    outside.write_text("x")
    assert client.delete(f"{API}/projects/{drop}").status_code == 204
    assert not dropped_file.exists() and kept_file.exists() and outside.exists()
    assert len(client.get(f"{API}/ifc/model/{kept['id']}/elements").json()) == 5  # 1 parede + 1 laje + 3 espaciais


def test_project_deletion_refused_while_jobs_are_active(client, runtime, tmp_path):
    pid = project(client, "PRJ-BUSY")
    blocker = runtime.jobs.submit("system.diagnostic", {"steps": 400, "step_seconds": 0.05})
    body = upload(client, pid, build_ifc(tmp_path / "busy.ifc", walls=1)).json()
    r = client.delete(f"{API}/projects/{pid}")
    assert r.status_code == 409 and r.json()["error"]["code"] == "project_busy"
    runtime.jobs.cancel(blocker["id"])
    wait(runtime, blocker["id"])
    wait(runtime, body["job_id"])
    assert client.delete(f"{API}/projects/{pid}").status_code == 204

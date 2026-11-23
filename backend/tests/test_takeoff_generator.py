"""Quantitativos por elemento (tarefa ifc.quantities) e gerador de cronograma por regras."""
import time

import ifcopenshell
import ifcopenshell.api
import pytest

from app.modules.takeoff.catalog import DEFAULT_SERVICES
from app.modules.takeoff.extractor import compute_takeoff
from app.modules.takeoff.generator import build_proposal
from ifc_factory import build_building_ifc


def wait_job(client, job_id, timeout=120):
    deadline = time.time() + timeout
    while time.time() < deadline:
        job = client.get(f"/api/v1/jobs/{job_id}").json()
        if job["status"] in ("completed", "failed", "cancelled", "interrupted"):
            return job
        time.sleep(0.1)
    raise AssertionError(f"tarefa {job_id} não terminou")


def by_type(rows, t):
    return [r for r in rows if r["ifc_type"] == t]


# --------------------------------------------------------------------------- extrator
def test_geometry_quantities_are_in_si_and_traceable(tmp_path):
    rows = compute_takeoff(str(build_building_ifc(tmp_path / "b.ifc")), threads=2)["rows"]
    assert len(rows) == 24 and not any(r["excluded"] for r in rows)
    col = by_type(rows, "IfcColumn")[0]
    assert col["volume_m3"] == pytest.approx(0.27, rel=1e-3)
    assert col["length_m"] == pytest.approx(3.0, rel=1e-3)
    assert col["sources"]["volume"] == {"source": "geometry", "method": "volume da malha"}
    wall = by_type(rows, "IfcWall")[0]
    assert wall["area_m2"] == pytest.approx(15.0, rel=1e-3)  # volume ÷ espessura
    slab = by_type(rows, "IfcSlab")[0]
    assert slab["area_m2"] == pytest.approx(25.0, rel=1e-3)
    assert {r["storey_name"] for r in rows} == {"Pavimento 1", "Pavimento 2"}
    assert col["material_class"] == "concrete"
    door = by_type(rows, "IfcDoor")[0]
    assert door["geometry_ok"] is False and door["count"] == 1.0 and door["volume_m3"] is None
    assert min(r["z_min_m"] for r in by_type(rows, "IfcFooting")) == pytest.approx(-0.5)


def test_qto_and_typed_pset_take_precedence_and_are_converted(tmp_path):
    run = ifcopenshell.api.run
    model = run("project.create_file", version="IFC4")
    project = run("root.create_entity", model, ifc_class="IfcProject", name="P")
    cm = run("unit.add_si_unit", model, unit_type="LENGTHUNIT", prefix="CENTI")
    run("unit.assign_unit", model, units=[cm])
    storey = run("root.create_entity", model, ifc_class="IfcBuildingStorey", name="Térreo")
    run("aggregate.assign_object", model, products=[storey], relating_object=project)
    pipe = run("root.create_entity", model, ifc_class="IfcPipeSegment", name="Tubo")
    beam = run("root.create_entity", model, ifc_class="IfcBeam", name="Viga")
    other = run("root.create_entity", model, ifc_class="IfcPipeSegment", name="Sem tipo")
    run("spatial.assign_container", model, products=[pipe, beam, other], relating_structure=storey)
    pset = run("pset.add_pset", model, product=pipe, name="Fabricante_Pset")
    pset.HasProperties = [model.create_entity("IfcPropertySingleValue", Name="Comprimento",
                                              NominalValue=model.create_entity("IfcLengthMeasure", 250.0))]
    pset2 = run("pset.add_pset", model, product=other, name="Fabricante_Pset")
    pset2.HasProperties = [model.create_entity("IfcPropertySingleValue", Name="Comprimento",
                                               NominalValue=model.create_entity("IfcReal", 250.0))]
    qto = run("pset.add_qto", model, product=beam, name="Qto_BeamBaseQuantities")
    run("pset.edit_qto", model, qto=qto, properties={"NetVolume": 0.75, "Length": 600.0})
    path = tmp_path / "q.ifc"
    model.write(str(path))
    rows = {r["name"]: r for r in compute_takeoff(str(path), threads=1)["rows"]}
    assert rows["Tubo"]["length_m"] == pytest.approx(2.5)  # 250 cm → 2,5 m
    assert rows["Tubo"]["sources"]["length"]["source"] == "author_pset"
    assert rows["Sem tipo"]["length_m"] is None  # IfcReal: unidade seria suposição → ignorado
    assert rows["Viga"]["volume_m3"] == pytest.approx(0.75)
    assert rows["Viga"]["length_m"] == pytest.approx(6.0)
    assert rows["Viga"]["sources"]["volume"] == {"source": "ifc_qto", "method": "Qto_BeamBaseQuantities.NetVolume",
                                                 "original": 0.75}


# --------------------------------------------------------------------------- gerador (puro)
def _row(gid, t, storey, z, **kw):
    base = dict(element_id=None, global_id=gid, ifc_type=t, mapping_type=t, storey_name=storey,
                storey_key=storey.upper() if storey else None, storey_elevation_m=None, z_min_m=z,
                material_class="concrete", volume_m3=None, area_m2=None, length_m=None, weight_kg=None,
                count=1.0, excluded=False)
    base.update(kw)
    return base


def _services(**productivity):
    out = []
    for d in DEFAULT_SERVICES:
        s = {"default_duration_days": 5.0, "is_active": True, "include_by_default": True, "productivity_per_day": None,
             "quantity_ifc_types": None, "material_class": None, "predecessors": None, "after_previous_level": None, **d}
        if d["code"] in productivity:
            s["productivity_per_day"] = productivity[d["code"]]
        out.append(s)
    return out


def test_proposal_levels_durations_and_precedences():
    rows = [
        _row("f1", "IfcFooting", "Térreo", -0.5, volume_m3=2.0),
        _row("c1", "IfcColumn", "Térreo", 0.0, volume_m3=1.2),
        _row("b1", "IfcBeam", "Térreo", 2.7, volume_m3=1.0),
        _row("s1", "IfcSlab", "Térreo", 3.0, area_m2=25.0),
        _row("c2", "IfcColumn", "Superior", 3.0, volume_m3=1.2),
        _row("s2", "IfcSlab", "Superior", 6.0, area_m2=25.0),
        _row("w2", "IfcWall", "Superior", 3.0, area_m2=None, material_class=None),
        _row("x", "IfcBuildingElementProxy", "Superior", 3.0),
    ]
    p = build_proposal(rows, _services(PIL=0.5))
    assert p["level_mode"] == "storey"
    assert [lv["name"] for lv in p["levels"]] == ["Térreo", "Superior"]
    acts = {a["code"]: a for a in p["activities"]}
    assert set(acts) == {"01-FUND", "01-PIL", "01-VIG", "01-LAJ", "02-PIL", "02-LAJ", "02-ALV", "02-OUT"}
    assert acts["01-PIL"]["duration"] == 3.0 and not acts["01-PIL"]["provisional"]  # ⌈1,2 ÷ 0,5⌉
    assert acts["01-VIG"]["provisional"] and acts["01-VIG"]["provisional_reason"] == "sem produtividade cadastrada"
    assert acts["02-ALV"]["coverage"] == 0.0
    assert acts["02-OUT"]["include"] is False  # "outros" fica desmarcado por padrão
    rel = {(a, b) for a, b in ((x["pred_key"].split("|")[1] + "@" + x["pred_key"].split("|")[0],
                                x["succ_key"].split("|")[1] + "@" + x["succ_key"].split("|")[0]) for x in p["precedences"])}
    assert ("FUND@TÉRREO", "PIL@TÉRREO") in rel
    assert ("PIL@TÉRREO", "VIG@TÉRREO") in rel
    assert ("LAJ@TÉRREO", "PIL@SUPERIOR") in rel  # pilares do pavimento seguinte após a laje anterior
    assert ("FUND@TÉRREO", "PIL@SUPERIOR") in rel  # predecessor ausente no nível: usa o do nível anterior
    assert ("LAJ@SUPERIOR", "ALV@SUPERIOR") in rel


def test_single_storey_models_use_elevation_bands():
    rows = [_row(f"m{i}", "IfcMember", "Default Storey", z, material_class="steel", weight_kg=100.0)
            for i, z in enumerate([0.1, 1.0, 4.0, 7.5])]
    p = build_proposal(rows, _services(EMET=150.0), band_height_m=3.0)
    assert p["level_mode"] == "elevation"
    assert [lv["element_count"] for lv in p["levels"]] == [2, 1, 1]
    acts = p["activities"]
    assert [a["service_code"] for a in acts] == ["EMET"] * 3
    assert acts[0]["quantity"] == 200.0 and acts[0]["unit"] == "kg" and acts[0]["duration"] == 2.0
    assert len(p["precedences"]) == 2  # EMET de cada faixa após a faixa anterior


def test_cyclic_rules_are_dropped_with_warning():
    services = _services()
    for s in services:
        if s["code"] == "PIL":
            s["predecessors"] = "VIG"
        if s["code"] == "VIG":
            s["predecessors"] = "PIL"
    p = build_proposal([_row("c", "IfcColumn", "T", 0.0, volume_m3=1), _row("b", "IfcBeam", "T", 2.0, volume_m3=1)], services)
    assert len(p["precedences"]) == 1
    assert any("ciclo" in w for w in p["warnings"])


# --------------------------------------------------------------------------- API ponta a ponta
def test_full_flow_from_ifc_to_cpm(client, tmp_path):
    project = client.post("/api/v1/projects/", json={"name": "Gerador", "code": "GEN-1"}).json()
    pid = project["id"]
    path = build_building_ifc(tmp_path / "edificio.ifc")
    with open(path, "rb") as fh:
        up = client.post(f"/api/v1/ifc/project/{pid}/upload", files={"file": ("edificio.ifc", fh, "application/octet-stream")}).json()
    assert wait_job(client, up["job_id"])["status"] == "completed"
    model_id = up["id"]

    r = client.post(f"/api/v1/schedule-generator/project/{pid}/preview", json={"model_ids": [model_id]})
    assert r.status_code == 409 and r.json()["error"]["code"] == "takeoff_not_ready"

    start = client.post(f"/api/v1/takeoff/model/{model_id}")
    assert start.status_code == 202
    job = wait_job(client, start.json()["job_id"])
    assert job["status"] == "completed", job
    takeoff = client.get(f"/api/v1/takeoff/model/{model_id}").json()
    assert takeoff["status"] == "completed"
    assert takeoff["totals"]["by_type"]["IfcColumn"]["volume_m3"] == pytest.approx(8 * 0.27, rel=1e-3)
    elements = client.get(f"/api/v1/takeoff/model/{model_id}/elements", params={"ifc_type": "IfcWall"}).json()
    assert elements["total"] == 4 and elements["items"][0]["element_id"] is not None

    services = client.get(f"/api/v1/schedule-generator/project/{pid}/services").json()
    assert len(services) == len(DEFAULT_SERVICES) and all(s["productivity_per_day"] is None for s in services)
    pil = next(s for s in services if s["code"] == "PIL")
    upd = client.put(f"/api/v1/schedule-generator/services/{pil['id']}", json={"productivity_per_day": 0.5})
    assert upd.json()["productivity_per_day"] == 0.5

    preview = client.post(f"/api/v1/schedule-generator/project/{pid}/preview", json={"model_ids": [model_id]}).json()
    codes = [a["code"] for a in preview["activities"]]
    assert codes == ["01-FUND", "01-PIL", "01-VIG", "01-LAJ", "01-ALV", "01-ESQ",
                     "02-PIL", "02-VIG", "02-LAJ", "02-ALV", "02-ESQ"]
    pil1 = next(a for a in preview["activities"] if a["code"] == "01-PIL")
    assert pil1["duration"] == 3.0 and pil1["quantity"] == pytest.approx(1.08, rel=1e-3)  # ⌈1,08 ÷ 0,5⌉

    key_esq = next(a["key"] for a in preview["activities"] if a["code"] == "02-ESQ")
    key_alv = next(a["key"] for a in preview["activities"] if a["code"] == "01-ALV")
    applied = client.post(f"/api/v1/schedule-generator/project/{pid}/apply", json={
        "model_ids": [model_id], "overrides": [{"key": key_esq, "include": False}, {"key": key_alv, "duration": 7}]})
    assert applied.status_code == 201, applied.text
    body = applied.json()
    assert body["activities"] == 10 and body["precedences"] > 0 and body["element_links"] == 23
    assert body["cpm"]["status"] == "success" and body["cpm"]["duration"] > 0

    acts = client.get(f"/api/v1/activities/project/{pid}").json()
    assert len(acts) == 10
    alv = next(a for a in acts if a["code"] == "G1-01-ALV")
    assert alv["duration"] == 7
    flags = client.get(f"/api/v1/schedule-generator/project/{pid}/activity-flags").json()
    assert flags[str(alv["id"])]["provisional"] is False  # duração editada pelo usuário
    assert client.get(f"/api/v1/activities/{alv['id']}/ifc-elements").json()

    again = client.post(f"/api/v1/schedule-generator/project/{pid}/apply", json={"model_ids": [model_id]}).json()
    assert again["removed_previous"] == 10 and again["number"] == 2
    acts = client.get(f"/api/v1/activities/project/{pid}").json()
    assert len(acts) == 11 and all(a["code"].startswith("G2-") for a in acts)
    assert len(client.get(f"/api/v1/schedule-generator/project/{pid}/generations").json()) == 2

    provisional = next(a for a in acts if client.get(f"/api/v1/schedule-generator/project/{pid}/activity-flags").json()[str(a["id"])]["provisional"])
    client.put(f"/api/v1/activities/{provisional['id']}", json={"duration": provisional["duration"] + 1})
    assert client.get(f"/api/v1/schedule-generator/project/{pid}/activity-flags").json()[str(provisional["id"])]["provisional"] is False


def test_takeoff_rows_follow_revision_deletion(client, tmp_path, db):
    from app.models.takeoff import IfcElementTakeoff

    pid = client.post("/api/v1/projects/", json={"name": "Del", "code": "DEL-1"}).json()["id"]
    path = build_building_ifc(tmp_path / "e.ifc", levels=1)
    with open(path, "rb") as fh:
        up = client.post(f"/api/v1/ifc/project/{pid}/upload", files={"file": ("e.ifc", fh, "application/octet-stream")}).json()
    wait_job(client, up["job_id"])
    wait_job(client, client.post(f"/api/v1/takeoff/model/{up['id']}").json()["job_id"])
    assert db.query(IfcElementTakeoff).filter(IfcElementTakeoff.model_id == up["id"]).count() == 14
    deletion = client.delete(f"/api/v1/ifc/model/{up['id']}")
    assert deletion.status_code == 202
    wait_job(client, deletion.json()["job_id"])
    db.expire_all()
    assert db.query(IfcElementTakeoff).filter(IfcElementTakeoff.model_id == up["id"],
                                              IfcElementTakeoff.element_id.isnot(None)).count() == 0


def test_steel_detection_and_implausible_solid_sections():
    from app.modules.takeoff.catalog import material_class

    assert material_class(["A-36"], None) == "steel"
    assert material_class(["ASTMA572GR50"], None) == "steel"
    assert material_class(["S235JRG2"], None) == "steel"
    assert material_class(["Concreto C30"], "steel") == "concrete"
    assert material_class(["Madeira"], None) is None
    assert material_class([], "steel") == "steel"  # sem material: usa o programa de autoria


def test_steel_weight_skips_solid_sections(tmp_path, monkeypatch):
    import app.modules.takeoff.extractor as ex

    path = build_building_ifc(tmp_path / "b.ifc", levels=1)
    monkeypatch.setattr(ex, "material_class", lambda mats, hint: "steel")
    rows = ex.compute_takeoff(str(path), threads=1)["rows"]
    col = by_type(rows, "IfcColumn")[0]  # 0,30×0,30 = 0,09 m² de seção: maciça, não é perfil
    assert col["weight_kg"] is None and "seção maciça" in col["sources"]["weight"]["method"]

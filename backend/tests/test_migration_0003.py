"""Migração 0003 sobre um banco real na revisão 0002 com dados: nada pode ser perdido."""
import hashlib
import sqlite3
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app
from conftest import make_settings

# A migração 0003 é testada sobre o upgrade completo até a revisão mais recente.
HEAD = "0004_takeoff_schedule"


SCHEMA_MAIN = Path(__file__).with_name("fixtures_schema_main_8a630a4.sql")


def build_db_at_0002(db_path: Path, uploads: Path, stamp: str | None = None) -> dict:
    """Banco com o esquema REAL da main antes da Etapa 3 (8a630a4) e dados.

    ``stamp=None`` reproduz instalações feitas com a Etapa 2, cujo ``alembic_version`` ficou
    vazio por causa do defeito corrigido em migrations/env.py; ``stamp='0001_bim_schedule'``
    reproduz instalações anteriores, migradas por ``alembic upgrade head``.
    """
    conn = sqlite3.connect(db_path)
    conn.executescript(SCHEMA_MAIN.read_text(encoding="utf-8"))
    if stamp:
        conn.execute("INSERT INTO alembic_version (version_num) VALUES (?)", (stamp,))
    conn.commit()
    conn.close()
    uploads.mkdir(parents=True)
    files = []
    for name in ("1_a_estrutura.ifc", "1_b_arquitetura.ifc"):
        f = uploads / name
        f.write_bytes(b"ISO-10303-21;\n" + name.encode() + b"\nEND-ISO-10303-21;\n")
        files.append(f)
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys=ON")
    ts = "2026-01-10 12:00:00"
    conn.execute("INSERT INTO projects (id, name, code, status, created_at, updated_at) VALUES (1,'Obra','OB-1','Planejamento',?,?)", (ts, ts))
    conn.execute("INSERT INTO activities (id, project_id, name, code, duration, percent_complete) VALUES (1,1,'Pilares','P',5,0)")
    for mid, (f, ver) in enumerate(zip(files, (1, 2)), start=1):
        conn.execute("INSERT INTO ifc_models (id, project_id, filename, file_path, version, status, element_count, progress, uploaded_at) "
                     "VALUES (?,1,?,?,?,'completed',2,100,?)", (mid, f.name.split('_', 2)[2], str(f), ver, ts))
        for k in range(2):
            conn.execute("INSERT INTO ifc_elements (model_id, global_id, name, ifc_type, properties_json) VALUES (?,?,?,?,?)",
                         (mid, f"GID-{k}", f"El {k}", "IfcWall", '{"Pset_WallCommon": {"LoadBearing": true}}'))
    conn.execute("INSERT INTO activity_ifc_elements (activity_id, ifc_element_id) VALUES (1, 1)")
    conn.execute("INSERT INTO activity_ifc_elements (activity_id, ifc_element_id) VALUES (1, 3)")
    conn.commit()
    snapshot = {t: conn.execute(f"SELECT * FROM {t} ORDER BY id").fetchall()
                for t in ("projects", "activities", "ifc_elements", "activity_ifc_elements")}
    conn.close()
    return {"snapshot": snapshot, "hashes": {f: hashlib.sha256(f.read_bytes()).hexdigest() for f in files}}


import pytest


@pytest.mark.parametrize("stamp", [None, "0001_bim_schedule"])
def test_upgrade_0002_to_0003_keeps_every_row_and_creates_models(tmp_path, stamp):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    db_path = data_dir / "bim_schedule.db"
    before = build_db_at_0002(db_path, data_dir / "uploads", stamp=stamp)

    with TestClient(create_app(make_settings(tmp_path))) as client:
        assert client.get("/api/v1/system/status").json()["database"]["revision"] == HEAD
        models = client.get("/api/v1/ifc/project/1/bim-models").json()
        # Cada arquivo existente vira a revisão 1 de um modelo lógico próprio.
        assert [(m["name"], [r["revision_number"] for r in m["revisions"]], m["current_revision_id"]) for m in models] == [
            ("estrutura.ifc", [1], 1), ("arquitetura.ifc", [1], 2)]
        assert models[0]["revisions"][0]["file_size"] == (data_dir / "uploads" / "1_a_estrutura.ifc").stat().st_size
        links = client.get("/api/v1/activities/1/ifc-elements").json()
        assert sorted(e["id"] for e in links) == [1, 3]  # vínculos intactos

    conn = sqlite3.connect(db_path)
    try:
        for table, rows in before["snapshot"].items():
            assert conn.execute(f"SELECT * FROM {table} ORDER BY id").fetchall() == rows, table  # byte a byte
        assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
        cols = {r[1] for r in conn.execute("PRAGMA table_info(ifc_models)")}
        assert {"bim_model_id", "revision_number", "is_current", "sha256", "deleted_at"} <= cols
        jobs_cols = {r[1] for r in conn.execute("PRAGMA table_info(jobs)")}
        assert {"recovery_pending", "recovery_error", "recovery_attempts"} <= jobs_cols
    finally:
        conn.close()
    for f, digest in before["hashes"].items():
        assert hashlib.sha256(f.read_bytes()).hexdigest() == digest  # arquivos intactos
    conn = sqlite3.connect(db_path)
    try:
        assert conn.execute("SELECT version_num FROM alembic_version").fetchall() == [(HEAD,)]
    finally:
        conn.close()
    backups = list((data_dir / "backups").glob(f"*antes-{HEAD}.db"))
    assert len(backups) == 1
    conn = sqlite3.connect(backups[0])
    try:
        assert conn.execute("SELECT COUNT(*) FROM ifc_elements").fetchone()[0] == 4  # backup completo
    finally:
        conn.close()


def test_upgrade_is_idempotent_on_restart(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    build_db_at_0002(data_dir / "bim_schedule.db", data_dir / "uploads")
    settings = make_settings(tmp_path)
    with TestClient(create_app(settings)) as client:
        first = client.get("/api/v1/ifc/project/1/bim-models").json()
    with TestClient(create_app(settings)) as client:
        assert client.get("/api/v1/ifc/project/1/bim-models").json() == first
    assert len(list((data_dir / "backups").glob("*.db"))) == 1  # sem nova migração, sem novo backup


def test_fresh_database_is_stamped_and_not_remigrated(tmp_path):
    """Regressão: migrations/env.py desfazia o registro em alembic_version (e qualquer dado
    gravado por migração), fazendo o serviço migrar de novo e criar backup a cada inicialização."""
    settings = make_settings(tmp_path)
    with TestClient(create_app(settings)) as client:
        client.post("/api/v1/projects/", json={"name": "P", "code": "P-1"})
        first = client.app.state.runtime.schema
    with TestClient(create_app(settings)) as client:
        second = client.app.state.runtime.schema
    db = tmp_path / "data" / "bim_schedule.db"
    conn = sqlite3.connect(db)
    try:
        assert conn.execute("SELECT version_num FROM alembic_version").fetchall() == [(HEAD,)]
    finally:
        conn.close()
    assert first["from"] is None and first["to"] == HEAD
    assert second == {"from": HEAD, "to": HEAD, "backup": None}
    assert not list((tmp_path / "data" / "backups").glob("*.db"))

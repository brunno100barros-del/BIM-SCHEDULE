"""Preservação de dados: migração da instalação legada (backend/) para a pasta de dados do usuário.

Os testes montam uma instalação legada com o esquema anterior à Etapa 2 (criado
pelo próprio Alembic na revisão 0001), um projeto com EAP, atividade e um IFC
enviado, e verificam:

* dados acessíveis antes da mudança (modo legado) e depois da migração;
* caminhos dos IFC reescritos para a nova pasta de uploads;
* arquivos e banco legados intactos (hash idêntico antes/depois);
* nenhuma nova migração em reinícios subsequentes;
* falha de migração mantém o uso do local legado, sem perda de dados.
"""
import hashlib
import json
import sqlite3
from pathlib import Path

from alembic import command
from fastapi.testclient import TestClient

from app.core.schema_migrations import alembic_config
from app.core.storage import resolve_storage
from app.main import create_app
from conftest import make_settings

from alembic.script import ScriptDirectory

HEAD = ScriptDirectory.from_config(alembic_config("sqlite://")).get_current_head()


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_legacy_install(legacy_dir: Path) -> dict:
    """Instalação com o layout antigo: backend/bim_schedule.db e backend/uploads/."""
    legacy_dir.mkdir(parents=True)
    uploads = legacy_dir / "uploads"
    uploads.mkdir()
    db_path = legacy_dir / "bim_schedule.db"
    cfg = alembic_config(f"sqlite:///{db_path.as_posix()}")
    command.upgrade(cfg, "0001_bim_schedule")  # esquema exatamente como na versão anterior
    ifc_file = uploads / "1_abc_modelo.ifc"
    ifc_file.write_bytes(b"ISO-10303-21;\nconteudo de teste\nEND-ISO-10303-21;\n")
    conn = sqlite3.connect(db_path)
    conn.execute("INSERT INTO projects (id, name, code, status, created_at, updated_at) VALUES (1, 'Obra legada', 'LEG-01', 'Planejamento', '2026-01-10 12:00:00', '2026-01-10 12:00:00')")
    conn.execute("INSERT INTO wbs_nodes (id, project_id, name, code, sort_order) VALUES (1, 1, 'Fundações', '1', 0)")
    conn.execute("INSERT INTO activities (id, project_id, wbs_id, name, code, duration, percent_complete) "
                 "VALUES (1, 1, 1, 'Escavação', 'ESC', 5, 0)")
    conn.execute("INSERT INTO ifc_models (id, project_id, filename, file_path, version, status, element_count, progress) "
                 "VALUES (1, 1, 'modelo.ifc', ?, 1, 'completed', 0, 100)", (str(ifc_file),))
    conn.commit()
    conn.close()
    return {"db": db_path, "ifc": ifc_file, "db_hash": sha(db_path), "ifc_hash": sha(ifc_file)}


def test_legacy_data_is_readable_before_migration(tmp_path):
    legacy = build_legacy_install(tmp_path / "legacy")
    settings = make_settings(tmp_path, AUTO_MIGRATE_LEGACY_DATA=False)
    with TestClient(create_app(settings)) as client:
        status = client.get("/api/v1/system/status").json()["storage"]
        assert status["mode"] == "legacy" and status["legacy_data_detected"] is True
        projects = client.get("/api/v1/projects/").json()
        assert [p["code"] for p in projects] == ["LEG-01"]
    # Mesmo no modo legado, o esquema é atualizado (com backup prévio fora da pasta legada).
    backups = list((tmp_path / "data" / "backups").glob("*.db"))
    assert len(backups) == 1
    assert legacy["ifc_hash"] == sha(legacy["ifc"])


def test_legacy_data_is_migrated_validated_and_preserved(tmp_path):
    legacy = build_legacy_install(tmp_path / "legacy")
    settings = make_settings(tmp_path)
    data_dir = tmp_path / "data"

    with TestClient(create_app(settings)) as client:
        storage = client.get("/api/v1/system/status").json()["storage"]
        assert storage["mode"] == "data_dir"
        assert storage["migration"]["status"] == "migrated"
        assert storage["migration"]["table_counts"]["projects"] == 1
        assert storage["migration"]["files_copied"] == 1
        assert storage["migration"]["rewritten_paths"] == 1

        projects = client.get("/api/v1/projects/").json()
        assert [p["code"] for p in projects] == ["LEG-01"]
        activities = client.get("/api/v1/activities/project/1").json()
        assert activities[0]["name"] == "Escavação"
        model = client.get("/api/v1/ifc/model/1").json()
        assert Path(model["file_path"]) == data_dir / "uploads" / "1_abc_modelo.ifc"
        download = client.get("/api/v1/ifc/model/1/download")
        assert download.status_code == 200 and download.content == legacy["ifc"].read_bytes()

        # Novos dados vão para a nova pasta.
        assert client.post("/api/v1/projects/", json={"name": "Nova", "code": "NOVA-01"}).status_code == 201

    assert (data_dir / "bim_schedule.db").is_file()
    assert json.loads((data_dir / "migration-report.json").read_text(encoding="utf-8"))["status"] == "migrated"
    # Os dados legados permanecem byte a byte iguais.
    assert sha(legacy["db"]) == legacy["db_hash"]
    assert sha(legacy["ifc"]) == legacy["ifc_hash"]
    assert not any(p.name.startswith(".migration-") for p in data_dir.iterdir())

    # Reinício: não migra de novo e mantém os dados criados após a migração.
    with TestClient(create_app(settings)) as client:
        codes = sorted(p["code"] for p in client.get("/api/v1/projects/").json())
        assert codes == ["LEG-01", "NOVA-01"]
    assert sha(legacy["db"]) == legacy["db_hash"]


def test_failed_migration_keeps_using_legacy_location(tmp_path, monkeypatch):
    legacy = build_legacy_install(tmp_path / "legacy")
    import app.core.storage as storage_module

    def broken(*_args, **_kwargs):
        raise storage_module.MigrationError("falha simulada de validação")

    monkeypatch.setattr(storage_module, "migrate_legacy_data", broken)
    settings = make_settings(tmp_path)
    layout = resolve_storage(settings)
    assert layout.mode == "legacy"
    assert layout.database_path == legacy["db"].resolve()
    assert layout.migration.status == "failed"
    assert not (tmp_path / "data" / "bim_schedule.db").exists()


def test_migration_validation_rejects_divergent_copy(tmp_path, monkeypatch):
    legacy = build_legacy_install(tmp_path / "legacy")
    import app.core.storage as storage_module

    real_counts = storage_module._table_counts
    calls = {"n": 0}

    def tampered(path):
        counts = real_counts(path)
        calls["n"] += 1
        if calls["n"] == 2:  # segunda chamada = contagem da cópia
            counts["projects"] = 0
        return counts

    monkeypatch.setattr(storage_module, "_table_counts", tampered)
    layout = resolve_storage(make_settings(tmp_path))
    assert layout.mode == "legacy" and layout.migration.status == "failed"
    assert "divergente" in layout.migration.message
    assert not (tmp_path / "data" / "bim_schedule.db").exists()
    assert not any(p.name.startswith(".migration-") for p in (tmp_path / "data").iterdir())
    assert sha(legacy["db"]) == legacy["db_hash"]


def test_explicit_database_url_is_respected(tmp_path):
    db_path = tmp_path / "custom" / "meu.db"
    db_path.parent.mkdir()
    settings = make_settings(tmp_path, BIM_SCHEDULE_DATABASE_URL=f"sqlite:///{db_path.as_posix()}")
    with TestClient(create_app(settings)) as client:
        assert client.get("/api/v1/system/status").json()["storage"]["mode"] == "explicit_database_url"
        client.post("/api/v1/projects/", json={"name": "X", "code": "X-1"})
    assert db_path.is_file()


def test_schema_upgrade_from_previous_revision_keeps_rows(tmp_path):
    """Banco existente na revisão 0001 recebe a tabela de tarefas sem perder registros."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    db_path = data_dir / "bim_schedule.db"
    command.upgrade(alembic_config(f"sqlite:///{db_path.as_posix()}"), "0001_bim_schedule")
    conn = sqlite3.connect(db_path)
    conn.execute("INSERT INTO projects (name, code, status, created_at, updated_at) VALUES ('Antiga', 'OLD-1', 'Planejamento', '2026-01-10 12:00:00', '2026-01-10 12:00:00')")
    conn.commit()
    conn.close()
    with TestClient(create_app(make_settings(tmp_path))) as client:
        assert [p["code"] for p in client.get("/api/v1/projects/").json()] == ["OLD-1"]
        assert client.get("/api/v1/system/status").json()["database"]["revision"] == HEAD
    backups = list((data_dir / "backups").glob(f"*antes-{HEAD}.db"))
    assert len(backups) == 1
    conn = sqlite3.connect(backups[0])
    assert conn.execute("SELECT code FROM projects").fetchall() == [("OLD-1",)]
    conn.close()

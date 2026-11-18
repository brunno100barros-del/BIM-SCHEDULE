"""Etapa 3 — Fase 1: modelos lógicos (bim_models), revisões e recuperação pendente das tarefas.

Migração **aditiva**. Atenção ao SQLite: as colunas são acrescentadas com
``ALTER TABLE ... ADD COLUMN`` e nunca por recriação da tabela (modo batch), porque
recriar ``ifc_models`` com ``foreign_keys=ON`` apagaria em cascata os elementos IFC e os
vínculos com atividades.

Cada arquivo IFC existente vira a revisão 1 de um modelo lógico próprio (nome = arquivo):
os dados atuais não permitem saber quais arquivos são revisões uns dos outros. O usuário
pode reagrupá-los depois (``POST /ifc/model/{id}/move-to-bim-model``).
"""
import os
from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0003_bim_models"
down_revision = "0002_jobs"
branch_labels = None
depends_on = None


def _columns(bind, table):
    return {c["name"] for c in inspect(bind).get_columns(table)}


def _add(bind, table, name, ddl):
    if name not in _columns(bind, table):
        op.execute(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}")


def _index(bind, table, name, columns):
    if name not in {i["name"] for i in inspect(bind).get_indexes(table)}:
        op.create_index(name, table, columns)


def upgrade():
    bind = op.get_bind()
    tables = set(inspect(bind).get_table_names())

    if "bim_models" not in tables:
        op.create_table(
            "bim_models",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
            sa.Column("name", sa.String(length=255), nullable=False),
            sa.Column("discipline_hint", sa.String(length=50), nullable=True),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.Column("deleted_at", sa.DateTime(), nullable=True),
        )
    _index(bind, "bim_models", "ix_bim_models_id", ["id"])
    _index(bind, "bim_models", "ix_bim_models_project_id", ["project_id"])

    _add(bind, "ifc_models", "bim_model_id", "INTEGER REFERENCES bim_models(id) ON DELETE SET NULL")
    _add(bind, "ifc_models", "revision_number", "INTEGER")
    _add(bind, "ifc_models", "is_current", "BOOLEAN NOT NULL DEFAULT 0")
    _add(bind, "ifc_models", "file_size", "INTEGER")
    _add(bind, "ifc_models", "sha256", "VARCHAR(64)")
    _add(bind, "ifc_models", "ifc_project_global_id", "VARCHAR(50)")
    _add(bind, "ifc_models", "header_json", "TEXT")
    _add(bind, "ifc_models", "deleted_at", "DATETIME")
    _index(bind, "ifc_models", "ix_ifc_models_bim_model_id", ["bim_model_id"])
    _index(bind, "ifc_models", "ix_ifc_models_sha256", ["sha256"])
    _index(bind, "ifc_models", "ix_ifc_models_ifc_project_global_id", ["ifc_project_global_id"])

    _add(bind, "jobs", "recovery_pending", "BOOLEAN NOT NULL DEFAULT 0")
    _add(bind, "jobs", "recovery_error", "TEXT")
    _add(bind, "jobs", "recovery_attempts", "INTEGER NOT NULL DEFAULT 0")
    _add(bind, "jobs", "recovery_updated_at", "DATETIME")
    _index(bind, "jobs", "ix_jobs_recovery_pending", ["recovery_pending"])

    # Preenchimento: cada arquivo existente vira a revisão 1 de um modelo lógico próprio.
    rows = bind.execute(sa.text(
        "SELECT id, project_id, filename, file_path, uploaded_at FROM ifc_models WHERE bim_model_id IS NULL ORDER BY id"
    )).fetchall()
    # Texto no mesmo formato que o SQLAlchemy grava (evita o adaptador datetime obsoleto do sqlite3).
    now = datetime.now(timezone.utc).replace(tzinfo=None).strftime("%Y-%m-%d %H:%M:%S.%f")
    for model_id, project_id, filename, file_path, uploaded_at in rows:
        created = uploaded_at or now
        result = bind.execute(sa.text(
            "INSERT INTO bim_models (project_id, name, created_at, updated_at) VALUES (:p, :n, :c, :c)"
        ), {"p": project_id, "n": filename, "c": created})
        bim_id = result.lastrowid
        size = os.path.getsize(file_path) if file_path and os.path.isfile(file_path) else None
        bind.execute(sa.text(
            "UPDATE ifc_models SET bim_model_id = :b, revision_number = 1, is_current = 1, file_size = :s "
            "WHERE id = :id"
        ), {"b": bim_id, "s": size, "id": model_id})


def downgrade():
    # Conservador: não remove dados.
    pass

"""Adiciona a tabela de tarefas em segundo plano e o vínculo do modelo IFC com sua tarefa.

Migração aditiva e idempotente: não remove nem altera dados existentes.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0002_jobs"
down_revision = "0001_bim_schedule"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = set(inspector.get_table_names())
    if "jobs" not in tables:
        op.create_table(
            "jobs",
            sa.Column("id", sa.String(length=32), primary_key=True),
            sa.Column("kind", sa.String(length=50), nullable=False),
            sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id", ondelete="SET NULL"), nullable=True),
            sa.Column("status", sa.String(length=20), nullable=False, server_default="queued"),
            sa.Column("progress", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("message", sa.String(length=500), nullable=True),
            sa.Column("error", sa.Text(), nullable=True),
            sa.Column("params_json", sa.Text(), nullable=True),
            sa.Column("result_json", sa.Text(), nullable=True),
            sa.Column("cancel_requested", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("cancel_requested_at", sa.DateTime(), nullable=True),
            sa.Column("pid", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("started_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.Column("finished_at", sa.DateTime(), nullable=True),
        )
        op.create_index("ix_jobs_kind", "jobs", ["kind"])
        op.create_index("ix_jobs_project_id", "jobs", ["project_id"])
        op.create_index("ix_jobs_status", "jobs", ["status"])

    if "ifc_models" in tables:
        columns = {c["name"] for c in inspect(bind).get_columns("ifc_models")}
        if "job_id" not in columns:
            op.add_column("ifc_models", sa.Column("job_id", sa.String(length=32), nullable=True))
            op.create_index("ix_ifc_models_job_id", "ifc_models", ["job_id"])


def downgrade():
    # Conservador: não remove dados.
    pass

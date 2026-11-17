"""Cria tabelas e amplia o esquema inicial do BIM SCHEDULE."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from app.core.database import Base
from app import models  # noqa: F401

revision = "0001_bim_schedule"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    # Cria tabelas ausentes sem apagar os dados de instalações anteriores.
    Base.metadata.create_all(bind=bind)
    inspector = inspect(bind)
    additions = {
        "wbs_nodes": [
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        ],
        "activities": [
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("quantity", sa.Float(), nullable=True),
            sa.Column("unit", sa.String(length=30), nullable=True),
            sa.Column("productivity", sa.Float(), nullable=True),
            sa.Column("percent_complete", sa.Float(), nullable=False, server_default="0"),
        ],
        "ifc_models": [
            sa.Column("status", sa.String(length=30), nullable=False, server_default="pending"),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("schema_name", sa.String(length=50), nullable=True),
            sa.Column("element_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("progress", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("processing_message", sa.String(length=255), nullable=True),
        ],
        "ifc_elements": [
            sa.Column("object_type", sa.String(length=255), nullable=True),
            sa.Column("predefined_type", sa.String(length=100), nullable=True),
            sa.Column("properties_json", sa.Text(), nullable=True),
            sa.Column("quantities_json", sa.Text(), nullable=True),
            sa.Column("materials_json", sa.Text(), nullable=True),
            sa.Column("storey_name", sa.String(length=255), nullable=True),
        ],
    }
    for table, columns in additions.items():
        existing = {c["name"] for c in inspect(bind).get_columns(table)}
        for column in columns:
            if column.name not in existing:
                op.add_column(table, column)


def downgrade():
    # Migração conservadora: não remove colunas/tabelas para evitar perda de dados.
    pass

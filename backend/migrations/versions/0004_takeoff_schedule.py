"""Etapa 4: quantitativos por elemento, catálogo de serviços e gerações de cronograma.

Migração **aditiva**: só cria tabelas novas. Nenhuma tabela existente é alterada.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0004_takeoff_schedule"
down_revision = "0003_bim_models"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    tables = set(inspect(bind).get_table_names())
    now = sa.text("CURRENT_TIMESTAMP")

    if "ifc_takeoff_runs" not in tables:
        op.create_table(
            "ifc_takeoff_runs",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("model_id", sa.Integer(), sa.ForeignKey("ifc_models.id", ondelete="CASCADE"), nullable=False, unique=True),
            sa.Column("status", sa.String(30), nullable=False, server_default="queued"),
            sa.Column("job_id", sa.String(32), nullable=True),
            sa.Column("summary_json", sa.Text(), nullable=True),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=now),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=now),
        )
        op.create_index("ix_ifc_takeoff_runs_model_id", "ifc_takeoff_runs", ["model_id"], unique=True)
        op.create_index("ix_ifc_takeoff_runs_job_id", "ifc_takeoff_runs", ["job_id"])

    if "ifc_element_takeoff" not in tables:
        op.create_table(
            "ifc_element_takeoff",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("model_id", sa.Integer(), sa.ForeignKey("ifc_models.id", ondelete="CASCADE"), nullable=False),
            sa.Column("element_id", sa.Integer(), sa.ForeignKey("ifc_elements.id", ondelete="CASCADE"), nullable=True),
            sa.Column("global_id", sa.String(50), nullable=False),
            sa.Column("ifc_type", sa.String(100), nullable=False),
            sa.Column("mapping_type", sa.String(100), nullable=False),
            sa.Column("predefined_type", sa.String(100), nullable=True),
            sa.Column("name", sa.String(255), nullable=True),
            sa.Column("storey_name", sa.String(255), nullable=True),
            sa.Column("storey_key", sa.String(255), nullable=True),
            sa.Column("storey_elevation_m", sa.Float(), nullable=True),
            sa.Column("z_min_m", sa.Float(), nullable=True),
            sa.Column("z_max_m", sa.Float(), nullable=True),
            sa.Column("discipline", sa.String(30), nullable=True),
            sa.Column("material", sa.String(255), nullable=True),
            sa.Column("material_class", sa.String(20), nullable=True),
            sa.Column("volume_m3", sa.Float(), nullable=True),
            sa.Column("area_m2", sa.Float(), nullable=True),
            sa.Column("length_m", sa.Float(), nullable=True),
            sa.Column("weight_kg", sa.Float(), nullable=True),
            sa.Column("count", sa.Float(), nullable=False, server_default="1"),
            sa.Column("geometry_ok", sa.Boolean(), nullable=False, server_default=sa.text("0")),
            sa.Column("excluded", sa.Boolean(), nullable=False, server_default=sa.text("0")),
            sa.Column("excluded_reason", sa.String(255), nullable=True),
            sa.Column("sources_json", sa.Text(), nullable=True),
        )
        op.create_index("ix_ifc_element_takeoff_model_id", "ifc_element_takeoff", ["model_id"])
        op.create_index("ix_ifc_element_takeoff_element_id", "ifc_element_takeoff", ["element_id"])
        op.create_index("ix_ifc_element_takeoff_global_id", "ifc_element_takeoff", ["global_id"])

    if "schedule_services" not in tables:
        op.create_table(
            "schedule_services",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
            sa.Column("code", sa.String(20), nullable=False),
            sa.Column("name", sa.String(255), nullable=False),
            sa.Column("discipline", sa.String(30), nullable=True),
            sa.Column("sequence", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("quantity_basis", sa.String(20), nullable=False, server_default="count"),
            sa.Column("ifc_types", sa.Text(), nullable=False, server_default=""),
            sa.Column("quantity_ifc_types", sa.Text(), nullable=True),
            sa.Column("material_class", sa.String(20), nullable=True),
            sa.Column("predecessors", sa.Text(), nullable=True),
            sa.Column("after_previous_level", sa.Text(), nullable=True),
            sa.Column("productivity_per_day", sa.Float(), nullable=True),
            sa.Column("productivity_note", sa.Text(), nullable=True),
            sa.Column("default_duration_days", sa.Float(), nullable=False, server_default="5"),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
            sa.Column("include_by_default", sa.Boolean(), nullable=False, server_default=sa.text("1")),
            sa.UniqueConstraint("project_id", "code", name="uq_schedule_service_code"),
        )
        op.create_index("ix_schedule_services_project_id", "schedule_services", ["project_id"])

    if "schedule_generations" not in tables:
        op.create_table(
            "schedule_generations",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
            sa.Column("number", sa.Integer(), nullable=False),
            sa.Column("options_json", sa.Text(), nullable=True),
            sa.Column("summary_json", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=now),
        )
        op.create_index("ix_schedule_generations_project_id", "schedule_generations", ["project_id"])

    if "schedule_generated_activities" not in tables:
        op.create_table(
            "schedule_generated_activities",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("generation_id", sa.Integer(), sa.ForeignKey("schedule_generations.id", ondelete="CASCADE"), nullable=False),
            sa.Column("activity_id", sa.Integer(), sa.ForeignKey("activities.id", ondelete="CASCADE"), nullable=False, unique=True),
            sa.Column("service_code", sa.String(20), nullable=True),
            sa.Column("level_name", sa.String(255), nullable=True),
            sa.Column("provisional", sa.Boolean(), nullable=False, server_default=sa.text("0")),
            sa.Column("provisional_reason", sa.String(255), nullable=True),
            sa.Column("quantity_coverage", sa.Float(), nullable=True),
        )
        op.create_index("ix_schedule_generated_activities_generation_id", "schedule_generated_activities", ["generation_id"])
        op.create_index("ix_schedule_generated_activities_activity_id", "schedule_generated_activities", ["activity_id"], unique=True)


def downgrade():
    for table in ("schedule_generated_activities", "schedule_generations", "schedule_services",
                  "ifc_element_takeoff", "ifc_takeoff_runs"):
        op.drop_table(table)

"""Quantitativos por elemento (takeoff), catálogo de serviços e gerações automáticas de cronograma.

Etapa 4. Tabelas novas e independentes (migração 0004): nada nas tabelas anteriores é alterado.
"""
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint, text

from app.core.database import Base


def _now():
    return datetime.now(timezone.utc)


class IfcTakeoffRun(Base):
    """Estado do cálculo de quantitativos de uma revisão IFC (uma linha por revisão)."""

    __tablename__ = "ifc_takeoff_runs"
    id = Column(Integer, primary_key=True, index=True)
    model_id = Column(Integer, ForeignKey("ifc_models.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    status = Column(String(30), nullable=False, default="queued")  # queued, processing, completed, failed, cancelled
    job_id = Column(String(32), nullable=True, index=True)
    summary_json = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=_now)
    updated_at = Column(DateTime, nullable=False, default=_now, onupdate=_now)


class IfcElementTakeoff(Base):
    """Quantidades de um elemento físico, sempre em SI, com a fonte de cada medida.

    ``sources_json`` guarda, por medida, ``{"source": ..., "method": ..., "original": ..., "original_unit": ...}``.
    Fontes: ``ifc_qto`` (IfcElementQuantity), ``author_pset`` (Pset com medida tipada),
    ``geometry`` (calculada pelo IfcOpenShell) e ``count``.
    """

    __tablename__ = "ifc_element_takeoff"
    id = Column(Integer, primary_key=True, index=True)
    model_id = Column(Integer, ForeignKey("ifc_models.id", ondelete="CASCADE"), nullable=False, index=True)
    element_id = Column(Integer, ForeignKey("ifc_elements.id", ondelete="CASCADE"), nullable=True, index=True)
    global_id = Column(String(50), nullable=False, index=True)
    ifc_type = Column(String(100), nullable=False)
    mapping_type = Column(String(100), nullable=False)  # tipo usado nas regras (o do conjunto pai, p.ex. IfcCurtainWall)
    predefined_type = Column(String(100), nullable=True)
    name = Column(String(255), nullable=True)
    storey_name = Column(String(255), nullable=True)
    storey_key = Column(String(255), nullable=True)
    storey_elevation_m = Column(Float, nullable=True)
    z_min_m = Column(Float, nullable=True)
    z_max_m = Column(Float, nullable=True)
    discipline = Column(String(30), nullable=True)
    material = Column(String(255), nullable=True)
    material_class = Column(String(20), nullable=True)  # steel, concrete ou nulo
    volume_m3 = Column(Float, nullable=True)
    area_m2 = Column(Float, nullable=True)
    length_m = Column(Float, nullable=True)
    weight_kg = Column(Float, nullable=True)
    count = Column(Float, nullable=False, default=1.0)
    geometry_ok = Column(Boolean, nullable=False, default=False, server_default=text("0"))
    excluded = Column(Boolean, nullable=False, default=False, server_default=text("0"))
    excluded_reason = Column(String(255), nullable=True)
    sources_json = Column(Text, nullable=True)


class ScheduleService(Base):
    """Serviço do catálogo do projeto: regra tipo IFC → serviço, unidade, produtividade e precedências."""

    __tablename__ = "schedule_services"
    __table_args__ = (UniqueConstraint("project_id", "code", name="uq_schedule_service_code"),)
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    code = Column(String(20), nullable=False)
    name = Column(String(255), nullable=False)
    discipline = Column(String(30), nullable=True)
    sequence = Column(Integer, nullable=False, default=0)
    quantity_basis = Column(String(20), nullable=False, default="count")  # volume_m3, area_m2, length_m, weight_kg, count
    ifc_types = Column(Text, nullable=False, default="")  # lista separada por vírgula; "*" = demais tipos
    quantity_ifc_types = Column(Text, nullable=True)  # subconjunto que soma quantidade (vazio = todos)
    material_class = Column(String(20), nullable=True)  # steel, not_steel ou nulo (qualquer)
    predecessors = Column(Text, nullable=True)  # códigos, mesmo pavimento
    after_previous_level = Column(Text, nullable=True)  # códigos, pavimento anterior
    productivity_per_day = Column(Float, nullable=True)  # unidade da base por dia; nulo = sem índice
    productivity_note = Column(Text, nullable=True)
    default_duration_days = Column(Float, nullable=False, default=5.0)
    is_active = Column(Boolean, nullable=False, default=True, server_default=text("1"))
    include_by_default = Column(Boolean, nullable=False, default=True, server_default=text("1"))


class ScheduleGeneration(Base):
    """Registro de uma geração automática aceita pelo usuário."""

    __tablename__ = "schedule_generations"
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    number = Column(Integer, nullable=False)
    options_json = Column(Text, nullable=True)
    summary_json = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=_now)


class ScheduleGeneratedActivity(Base):
    """Atividade criada por uma geração (permite substituir a geração e marcar durações provisórias)."""

    __tablename__ = "schedule_generated_activities"
    id = Column(Integer, primary_key=True, index=True)
    generation_id = Column(Integer, ForeignKey("schedule_generations.id", ondelete="CASCADE"), nullable=False, index=True)
    activity_id = Column(Integer, ForeignKey("activities.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    service_code = Column(String(20), nullable=True)
    level_name = Column(String(255), nullable=True)
    provisional = Column(Boolean, nullable=False, default=False, server_default=text("0"))
    provisional_reason = Column(String(255), nullable=True)
    quantity_coverage = Column(Float, nullable=True)

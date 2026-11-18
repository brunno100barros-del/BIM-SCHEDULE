from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text, text

from app.core.database import Base


def _utcnow():
    return datetime.now(timezone.utc)


class JobModel(Base):
    """Tarefa de processamento em segundo plano, persistida para acompanhamento e recuperação."""

    __tablename__ = "jobs"
    id = Column(String(32), primary_key=True)
    kind = Column(String(50), nullable=False, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="SET NULL"), nullable=True, index=True)
    status = Column(String(20), nullable=False, default="queued", index=True)
    progress = Column(Integer, nullable=False, default=0)
    message = Column(String(500), nullable=True)
    error = Column(Text, nullable=True)
    params_json = Column(Text, nullable=True)
    result_json = Column(Text, nullable=True)
    cancel_requested = Column(Boolean, nullable=False, default=False)
    cancel_requested_at = Column(DateTime, nullable=True)
    pid = Column(Integer, nullable=True)
    created_at = Column(DateTime, nullable=False, default=_utcnow)
    started_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, nullable=False, default=_utcnow, onupdate=_utcnow)
    finished_at = Column(DateTime, nullable=True)
    # Etapa 3: a rotina de consistência falhou e precisa ser executada novamente.
    recovery_pending = Column(Boolean, nullable=False, default=False, server_default=text("0"), index=True)
    recovery_error = Column(Text, nullable=True)
    recovery_attempts = Column(Integer, nullable=False, default=0, server_default=text("0"))
    recovery_updated_at = Column(DateTime, nullable=True)

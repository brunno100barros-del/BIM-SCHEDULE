from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Text
from datetime import datetime, timezone
from app.core.database import Base

class IfcModelModel(Base):
    __tablename__ = "ifc_models"
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    filename = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    version = Column(Integer, default=1, nullable=False)
    status = Column(String(30), default="pending", nullable=False)
    error_message = Column(Text, nullable=True)
    schema_name = Column(String(50), nullable=True)
    element_count = Column(Integer, default=0, nullable=False)
    progress = Column(Integer, default=0, nullable=False)
    processing_message = Column(String(255), nullable=True)
    uploaded_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    # Tarefa de processamento mais recente deste modelo (tabela jobs).
    job_id = Column(String(32), nullable=True, index=True)

class IfcElementModel(Base):
    __tablename__ = "ifc_elements"
    id = Column(Integer, primary_key=True, index=True)
    model_id = Column(Integer, ForeignKey("ifc_models.id", ondelete="CASCADE"), nullable=False, index=True)
    global_id = Column(String(50), index=True, nullable=False)
    name = Column(String(255), nullable=True)
    ifc_type = Column(String(100), nullable=False)
    description = Column(String(500), nullable=True)
    object_type = Column(String(255), nullable=True)
    predefined_type = Column(String(100), nullable=True)
    properties_json = Column(Text, nullable=True)
    quantities_json = Column(Text, nullable=True)
    materials_json = Column(Text, nullable=True)
    storey_name = Column(String(255), nullable=True)

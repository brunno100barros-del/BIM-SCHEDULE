from sqlalchemy import Column, Integer, String, ForeignKey, DateTime
from datetime import datetime
from app.core.database import Base

class IfcModelModel(Base):
    __tablename__ = "ifc_models"
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    filename = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    version = Column(Integer, default=1)
    uploaded_at = Column(DateTime, default=datetime.utcnow)

class IfcElementModel(Base):
    __tablename__ = "ifc_elements"
    id = Column(Integer, primary_key=True, index=True)
    model_id = Column(Integer, ForeignKey("ifc_models.id", ondelete="CASCADE"), nullable=False)
    global_id = Column(String(50), index=True, nullable=False)
    name = Column(String(255), nullable=True)
    ifc_type = Column(String(100), nullable=False)
    description = Column(String(500), nullable=True)

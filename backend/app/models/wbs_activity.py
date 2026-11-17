from sqlalchemy import Column, Integer, String, Float, ForeignKey, Text, UniqueConstraint
from app.core.database import Base

class WbsNodeModel(Base):
    __tablename__ = "wbs_nodes"
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    code = Column(String(50), nullable=False)
    description = Column(Text, nullable=True)
    parent_id = Column(Integer, ForeignKey("wbs_nodes.id", ondelete="CASCADE"), nullable=True, index=True)
    sort_order = Column(Integer, default=0, nullable=False)

class ActivityModel(Base):
    __tablename__ = "activities"
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    wbs_id = Column(Integer, ForeignKey("wbs_nodes.id", ondelete="SET NULL"), nullable=True, index=True)
    name = Column(String(255), nullable=False)
    code = Column(String(50), nullable=False)
    description = Column(Text, nullable=True)
    duration = Column(Float, default=1.0, nullable=False)
    quantity = Column(Float, nullable=True)
    unit = Column(String(30), nullable=True)
    productivity = Column(Float, nullable=True)
    optimistic = Column(Float, nullable=True)
    most_likely = Column(Float, nullable=True)
    pessimistic = Column(Float, nullable=True)
    percent_complete = Column(Float, default=0.0, nullable=False)
    status = Column(String(50), default="Não Iniciado")
    es = Column(Float, default=0.0)
    ef = Column(Float, default=0.0)
    ls = Column(Float, default=0.0)
    lf = Column(Float, default=0.0)
    tf = Column(Float, default=0.0)
    ff = Column(Float, default=0.0)
    is_critical = Column(Integer, default=0)

class PrecedenceModel(Base):
    __tablename__ = "precedences"
    id = Column(Integer, primary_key=True, index=True)
    predecessor_id = Column(Integer, ForeignKey("activities.id", ondelete="CASCADE"), nullable=False, index=True)
    successor_id = Column(Integer, ForeignKey("activities.id", ondelete="CASCADE"), nullable=False, index=True)
    relation_type = Column(String(10), default="FS", nullable=False)
    lag = Column(Float, default=0.0, nullable=False)

class ActivityIfcElementModel(Base):
    __tablename__ = "activity_ifc_elements"
    __table_args__ = (UniqueConstraint("activity_id", "ifc_element_id", name="uq_activity_ifc_element"),)
    id = Column(Integer, primary_key=True, index=True)
    activity_id = Column(Integer, ForeignKey("activities.id", ondelete="CASCADE"), nullable=False, index=True)
    ifc_element_id = Column(Integer, ForeignKey("ifc_elements.id", ondelete="CASCADE"), nullable=False, index=True)

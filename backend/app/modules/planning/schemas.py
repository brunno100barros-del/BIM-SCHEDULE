"""Esquemas de entrada da EAP, atividades e precedências."""
from typing import Optional

from pydantic import BaseModel, Field


class ActivityCreate(BaseModel):
    project_id: int
    wbs_id: Optional[int] = None
    name: str = Field(min_length=1, max_length=255)
    code: str = Field(min_length=1, max_length=50)
    description: Optional[str] = None
    duration: float = Field(default=1.0, ge=0)
    quantity: Optional[float] = Field(default=None, ge=0)
    unit: Optional[str] = None
    productivity: Optional[float] = Field(default=None, gt=0)
    optimistic: Optional[float] = Field(default=None, ge=0)
    most_likely: Optional[float] = Field(default=None, ge=0)
    pessimistic: Optional[float] = Field(default=None, ge=0)

class ActivityUpdate(BaseModel):
    wbs_id: Optional[int] = None
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    code: Optional[str] = Field(default=None, min_length=1, max_length=50)
    description: Optional[str] = None
    duration: Optional[float] = Field(default=None, ge=0)
    quantity: Optional[float] = Field(default=None, ge=0)
    unit: Optional[str] = None
    productivity: Optional[float] = Field(default=None, gt=0)
    percent_complete: Optional[float] = Field(default=None, ge=0, le=100)
    status: Optional[str] = None

class PrecedenceCreate(BaseModel):
    predecessor_id: int
    successor_id: int
    relation_type: str = "FS"
    lag: float = 0.0

class WbsCreate(BaseModel):
    project_id: int
    name: str = Field(min_length=1, max_length=255)
    code: str = Field(min_length=1, max_length=50)
    description: Optional[str] = None
    parent_id: Optional[int] = None
    sort_order: int = 0

class WbsUpdate(BaseModel):
    name: Optional[str] = None
    code: Optional[str] = None
    description: Optional[str] = None
    parent_id: Optional[int] = None
    sort_order: Optional[int] = None

class ElementLink(BaseModel):
    ifc_element_id: int

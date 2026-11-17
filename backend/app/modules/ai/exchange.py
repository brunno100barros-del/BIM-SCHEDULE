"""Formato padronizado de intercâmbio entre o BIM SCHEDULE e qualquer IA.

O mesmo contrato é usado pela IA local (Ollama) e pela integração manual com o
Claude (arquivos exportados/importados pelo usuário). A IA **propõe**; quem
calcula datas, CPM, folgas e caminho crítico é sempre o motor de engenharia.

- Pedido:  ``format = "bim-schedule-ai-request"``,  ``schema_version = 1``
- Resposta: ``format = "bim-schedule-ai-response"``, ``schema_version = 1``

A resposta da demonstração antiga (``activities_updates``, ``risks``,
``assumptions`` sem cabeçalho) é aceita e convertida, com aviso.
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

REQUEST_FORMAT = "bim-schedule-ai-request"
RESPONSE_FORMAT = "bim-schedule-ai-response"
SCHEMA_VERSION = 1

RelationType = Literal["FS", "SS", "FF", "SF"]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ----------------------------------------------------------------------------- pedido
class GeneratorInfo(_Strict):
    app: str = "BIM SCHEDULE"
    version: str


class ProjectContext(_Strict):
    id: int
    code: str
    name: str
    client: Optional[str] = None
    description: Optional[str] = None
    location: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    target_duration_days: Optional[float] = None


class WbsNodeContext(_Strict):
    id: int
    code: str
    name: str
    parent_id: Optional[int] = None


class ActivityContext(_Strict):
    id: int
    code: str
    name: str
    wbs_id: Optional[int] = None
    duration: float
    quantity: Optional[float] = None
    unit: Optional[str] = None
    optimistic: Optional[float] = None
    most_likely: Optional[float] = None
    pessimistic: Optional[float] = None


class PrecedenceContext(_Strict):
    predecessor_id: int
    successor_id: int
    relation_type: RelationType
    lag: float = 0.0


class IfcModelSummary(_Strict):
    id: int
    filename: str
    version: int
    schema_name: Optional[str] = None
    status: str
    element_count: int
    elements_by_type: dict[str, int] = Field(default_factory=dict)
    storeys: list[str] = Field(default_factory=list)


class ResponseContract(_Strict):
    format: Literal["bim-schedule-ai-response"] = RESPONSE_FORMAT
    schema_version: Literal[1] = SCHEMA_VERSION


class AIRequestPackage(_Strict):
    format: Literal["bim-schedule-ai-request"] = REQUEST_FORMAT
    schema_version: Literal[1] = SCHEMA_VERSION
    package_id: str
    created_at: datetime
    generator: GeneratorInfo
    project: ProjectContext
    wbs: list[WbsNodeContext] = Field(default_factory=list)
    activities: list[ActivityContext] = Field(default_factory=list)
    precedences: list[PrecedenceContext] = Field(default_factory=list)
    ifc_models: list[IfcModelSummary] = Field(default_factory=list)
    budget: Optional[dict] = None  # reservado para o importador de orçamento (etapa futura)
    instructions: str
    response_contract: ResponseContract = Field(default_factory=ResponseContract)


# --------------------------------------------------------------------------- resposta
class ProviderInfo(_Strict):
    kind: Literal["ollama", "manual-claude", "manual-other", "legacy-demo"]
    model: Optional[str] = None


class MethodologyProposal(_Strict):
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1)
    rationale: Optional[str] = None
    assumptions: list[str] = Field(default_factory=list)


class ActivityUpdate(_Strict):
    id: int
    optimistic: Optional[float] = Field(default=None, ge=0)
    most_likely: Optional[float] = Field(default=None, ge=0)
    pessimistic: Optional[float] = Field(default=None, ge=0)
    duration_suggestion: Optional[float] = Field(default=None, ge=0)
    risk_note: Optional[str] = None

    @model_validator(mode="after")
    def _pert_order(self):
        o, m, p = self.optimistic, self.most_likely, self.pessimistic
        if None not in (o, m, p) and not (o <= m <= p):
            raise ValueError("As estimativas devem obedecer otimista ≤ mais provável ≤ pessimista.")
        return self


class NewActivitySuggestion(_Strict):
    code: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=1, max_length=255)
    wbs_code: Optional[str] = None
    estimated_duration_days: float = Field(ge=0)
    rationale: Optional[str] = None


class SequenceSuggestion(_Strict):
    predecessor_id: int
    successor_id: int
    relation_type: RelationType = "FS"
    lag: float = 0.0
    rationale: Optional[str] = None


class RiskItem(_Strict):
    title: str = Field(min_length=1)
    probability: Optional[str | float] = None
    impact: Optional[str | float] = None
    mitigation: Optional[str] = None


class AIResponsePackage(_Strict):
    format: Literal["bim-schedule-ai-response"] = RESPONSE_FORMAT
    schema_version: Literal[1] = SCHEMA_VERSION
    request_package_id: Optional[str] = None
    provider: ProviderInfo
    methodology_proposals: list[MethodologyProposal] = Field(default_factory=list)
    activities_updates: list[ActivityUpdate] = Field(default_factory=list)
    new_activity_suggestions: list[NewActivitySuggestion] = Field(default_factory=list)
    sequence_suggestions: list[SequenceSuggestion] = Field(default_factory=list)
    risks: list[RiskItem] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


DEFAULT_INSTRUCTIONS = (
    "Você é um assistente de planejamento de obras. Analise o projeto e proponha metodologias construtivas, "
    "estimativas de duração (otimista, mais provável, pessimista), novas atividades e sequências. Não invente dados "
    "que não estejam no pacote; registre premissas em 'assumptions'. Não calcule datas nem caminho crítico: o motor "
    "do BIM SCHEDULE fará esses cálculos. Não altere identificadores (id, GlobalId). Responda somente com JSON "
    "no formato 'bim-schedule-ai-response', schema_version 1."
)

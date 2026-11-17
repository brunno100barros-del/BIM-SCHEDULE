"""Interface comum aos provedores de IA.

Trocar de IA significa trocar o provedor; o motor de engenharia e o formato de
intercâmbio permanecem os mesmos.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Literal, Optional, Protocol

from app.modules.ai.exchange import AIRequestPackage, AIResponsePackage

Availability = Literal["available", "unavailable", "not_configured", "not_implemented", "manual"]


@dataclass
class ProviderStatus:
    kind: str
    availability: Availability
    message: str
    details: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


class ProviderNotImplemented(NotImplementedError):
    """O provedor ainda não executa análises nesta versão."""


class AIProvider(Protocol):
    kind: str

    def status(self) -> ProviderStatus:
        """Verifica se o provedor pode ser usado agora (sem executar análises)."""

    def analyze(self, request: AIRequestPackage) -> Optional[AIResponsePackage]:
        """Executa a análise. Provedores manuais retornam ``None`` (a resposta chega por arquivo)."""

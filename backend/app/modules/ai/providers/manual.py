"""Provedor manual: o usuário leva o pacote ao Claude (ou outra IA) e traz a resposta.

Não há chamada de API nem custo por consulta. O BIM SCHEDULE exporta o pedido
(:class:`AIRequestPackage`) e valida o arquivo de retorno (:class:`AIResponsePackage`).
"""
from __future__ import annotations

from typing import Optional

from app.modules.ai.exchange import AIRequestPackage, AIResponsePackage
from app.modules.ai.providers.base import ProviderStatus


class ManualExchangeProvider:
    kind = "manual-claude"

    def status(self) -> ProviderStatus:
        return ProviderStatus(self.kind, "manual",
                              "Exporte o pacote do projeto, analise na interface do Claude e importe o JSON de resposta.")

    def analyze(self, request: AIRequestPackage) -> Optional[AIResponsePackage]:
        return None

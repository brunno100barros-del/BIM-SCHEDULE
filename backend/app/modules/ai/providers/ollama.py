"""Provedor de IA local via Ollama — somente preparação nesta etapa.

``status()`` consulta o Ollama instalado na própria máquina (``/api/tags``) para
informar se o executor e o modelo configurado estão presentes. Nenhum modelo é
baixado e nenhuma análise é executada: ``analyze()`` lança
:class:`ProviderNotImplemented` até a etapa de planejamento inteligente.
"""
from __future__ import annotations

from typing import Optional

import httpx

from app.modules.ai.exchange import AIRequestPackage, AIResponsePackage
from app.modules.ai.providers.base import ProviderNotImplemented, ProviderStatus


class OllamaProvider:
    kind = "ollama"

    def __init__(self, base_url: str, model: str, *, timeout: float = 2.0, transport: Optional[httpx.BaseTransport] = None):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self._transport = transport

    def status(self) -> ProviderStatus:
        details = {"base_url": self.base_url, "model": self.model}
        try:
            with httpx.Client(timeout=self.timeout, transport=self._transport, trust_env=False) as client:
                response = client.get(f"{self.base_url}/api/tags")
                response.raise_for_status()
                models = [m.get("name") for m in response.json().get("models", [])]
        except (httpx.HTTPError, ValueError) as exc:
            return ProviderStatus(self.kind, "unavailable", "Ollama não está acessível nesta máquina.",
                                  {**details, "error": str(exc)})
        details["installed_models"] = models
        details["model_installed"] = self.model in models
        message = ("Ollama acessível. A análise inteligente será implementada em etapa futura."
                   if self.model in models else
                   f"Ollama acessível, mas o modelo '{self.model}' não está instalado.")
        return ProviderStatus(self.kind, "not_implemented", message, details)

    def analyze(self, request: AIRequestPackage) -> Optional[AIResponsePackage]:
        raise ProviderNotImplemented("A análise com Ollama ainda não foi implementada.")

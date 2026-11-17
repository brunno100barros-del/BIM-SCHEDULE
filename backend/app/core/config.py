"""Configuração central do serviço BIM SCHEDULE.

As variáveis de ambiente usam o prefixo ``BIM_SCHEDULE_``. Por compatibilidade
com instalações anteriores, ``DATABASE_URL`` (sem prefixo) continua aceito.

A configuração é lida sob demanda por :func:`get_settings`, o que permite que
testes e o aplicativo desktop definam o ambiente antes da inicialização.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal, Optional

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]
"""Diretório ``backend/`` do código-fonte (usado para localizar dados legados)."""

APP_VERSION = "0.6.0-dev"


class Settings(BaseSettings):
    PROJECT_NAME: str = "BIM SCHEDULE"
    VERSION: str = APP_VERSION
    API_V1_STR: str = "/api/v1"

    ENVIRONMENT: Literal["development", "desktop", "server", "test"] = "development"

    # Armazenamento. Quando DATA_DIR não é informado, usa-se a pasta de dados do
    # usuário (%LOCALAPPDATA%\BIM-SCHEDULE no Windows).
    DATA_DIR: Optional[Path] = None
    # URL explícita do banco. Se definida, desativa a migração automática de dados legados.
    DATABASE_URL: Optional[str] = Field(
        default=None, validation_alias=AliasChoices("BIM_SCHEDULE_DATABASE_URL", "DATABASE_URL")
    )
    AUTO_MIGRATE_LEGACY_DATA: bool = True
    LEGACY_DIR: Path = BACKEND_DIR

    # Rede e segurança local
    HOST: str = "127.0.0.1"
    PORT: int = 8000
    CORS_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:4173",
        "http://127.0.0.1:4173",
    ]
    ALLOWED_HOSTS: list[str] = ["127.0.0.1", "localhost", "::1"]
    # Token opcional exigido no cabeçalho X-BIM-Schedule-Token (definido pelo app desktop).
    LOCAL_API_TOKEN: Optional[str] = None

    # Processamento
    MAX_IFC_UPLOAD_MB: int = 1024
    JOB_MAX_WORKERS: int = 1
    JOB_CANCEL_GRACE_SECONDS: float = 10.0
    JOB_POLL_INTERVAL_SECONDS: float = 0.2

    LOG_LEVEL: str = "INFO"

    # Inteligência artificial (somente preparação nesta etapa)
    AI_PROVIDER: Literal["none", "ollama", "manual"] = "manual"
    OLLAMA_BASE_URL: str = "http://127.0.0.1:11434"
    OLLAMA_MODEL: str = "qwen3.5:4b"

    model_config = SettingsConfigDict(
        env_prefix="BIM_SCHEDULE_",
        env_file=".env",
        extra="ignore",
        case_sensitive=True,
    )

    @property
    def max_ifc_bytes(self) -> int:
        return self.MAX_IFC_UPLOAD_MB * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()


def reset_settings() -> None:
    """Descarta a configuração em cache (usado por testes e pelo bootstrap)."""
    get_settings.cache_clear()

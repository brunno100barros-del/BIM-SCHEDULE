import os
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    PROJECT_NAME: str = "BIM SCHEDULE"
    VERSION: str = "0.3.0-dev"
    API_V1_STR: str = "/api/v1"
    DATABASE_URL: str = "sqlite:///./bim_schedule.db"
    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]
    model_config = SettingsConfigDict(case_sensitive=True, env_file=".env", extra="ignore")

settings = Settings()

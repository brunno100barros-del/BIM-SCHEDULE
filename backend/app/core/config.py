import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "BIM SCHEDULE"
    VERSION: str = "0.2.0"
    API_V1_STR: str = "/api/v1"
    DATABASE_URL: str = "sqlite:///./bim_schedule.db"

    class Config:
        case_sensitive = True
        env_file = ".env"

settings = Settings()

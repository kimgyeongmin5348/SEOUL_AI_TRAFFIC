from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = Field(default="RoadPulse", validation_alias="APP_NAME")
    app_env: str = Field(default="development", validation_alias="APP_ENV")
    debug: bool = Field(default=True, validation_alias="DEBUG")

    database_url: str = Field(validation_alias="DATABASE_URL")

    seoul_traffic_api_key: str | None = Field(
        default=None,
        validation_alias="SEOUL_TRAFFIC_API_KEY",
    )
    seoul_incident_api_key: str | None = Field(
        default=None,
        validation_alias="SEOUL_INCIDENT_API_KEY",
    )
    kma_api_key: str | None = Field(default=None, validation_alias="KMA_API_KEY")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

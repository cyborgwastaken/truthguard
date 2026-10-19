from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="TRUTHGUARD_", env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://truthguard:truthguard@localhost:5433/truthguard"
    cors_origins: str = "http://localhost:5173"
    llm_model: str = "claude-sonnet-5-5"


settings = Settings()

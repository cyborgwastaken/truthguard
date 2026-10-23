from __future__ import annotations

from pathlib import Path
from typing import Optional

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Recorded model replies (fictional fixtures only) live in the repo so the demo can replay them.
DEFAULT_REPLY_CACHE = Path(__file__).resolve().parents[2] / "AGENT" / "datasets" / "recorded" / "replies.jsonl"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="TRUTHGUARD_", env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://truthguard:truthguard@localhost:5433/truthguard"
    cors_origins: str = "http://localhost:5173"
    llm_model: str = "openai/gpt-oss-120b"
    # live: call Groq. record: call Groq and store every reply. cache: reuse stored replies, call Groq for
    # the rest. replay: stored replies only (no key needed; a missing reply is a visible failure).
    llm_mode: str = "live"
    llm_temperature: float = 0.0
    llm_cache_path: str = str(DEFAULT_REPLY_CACHE)
    # Where benchmark runs are read from. Empty: AGENT/datasets/benchmark/results.
    benchmark_results_dir: str = ""
    # The key may be given as GROQ_API_KEY (environment or BACKEND/.env) or TRUTHGUARD_GROQ_API_KEY.
    groq_api_key: Optional[str] = Field(
        default=None, validation_alias=AliasChoices("GROQ_API_KEY", "TRUTHGUARD_GROQ_API_KEY")
    )


settings = Settings()

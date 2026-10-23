"""The model key can be given as GROQ_API_KEY or TRUTHGUARD_GROQ_API_KEY, in the environment or in BACKEND/.env."""
from app.config import Settings


def test_the_key_is_read_from_groq_api_key(monkeypatch):
    monkeypatch.delenv("TRUTHGUARD_GROQ_API_KEY", raising=False)
    monkeypatch.setenv("GROQ_API_KEY", "from-env")
    assert Settings(_env_file=None).groq_api_key == "from-env"


def test_the_prefixed_name_works_too(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.setenv("TRUTHGUARD_GROQ_API_KEY", "prefixed")
    assert Settings(_env_file=None).groq_api_key == "prefixed"


def test_the_key_is_read_from_an_env_file(monkeypatch, tmp_path):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("TRUTHGUARD_GROQ_API_KEY", raising=False)
    env = tmp_path / ".env"
    env.write_text("GROQ_API_KEY=from-file\nTRUTHGUARD_LLM_MODE=replay\nSOMETHING_ELSE=1\n")
    settings = Settings(_env_file=str(env))
    assert settings.groq_api_key == "from-file" and settings.llm_mode == "replay"


def test_no_key_means_none_and_the_defaults_are_safe(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("TRUTHGUARD_GROQ_API_KEY", raising=False)
    settings = Settings(_env_file=None)
    assert settings.groq_api_key is None and settings.llm_mode == "live" and settings.llm_temperature == 0.0

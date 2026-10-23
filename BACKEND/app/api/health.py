from fastapi import APIRouter

from ..config import settings

router = APIRouter()


@router.get("/health")
def health() -> dict:
    """Liveness plus how the language model is set up. Makes no model call."""
    return {
        "status": "ok",
        "llm": {
            "model": settings.llm_model,
            "mode": settings.llm_mode,
            "key_present": bool(settings.groq_api_key),
        },
    }

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api import documents, evaluations, health, questions
from .config import settings

app = FastAPI(title="TruthGuard API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(documents.router)
app.include_router(questions.router)
app.include_router(evaluations.router)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api import health
from .config import settings

app = FastAPI(title="TruthGuard API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)

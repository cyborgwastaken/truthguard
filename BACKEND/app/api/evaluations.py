from __future__ import annotations

import json
import re
from pathlib import Path
from typing import List

from fastapi import APIRouter, HTTPException
from truthguard_agent.evaluation import runner
from truthguard_agent.evaluation.runner import BenchmarkRun

from ..config import settings

router = APIRouter(prefix="/evaluations", tags=["evaluations"])

RUN_ID = re.compile(r"^\d{8}T\d{6}Z$")
NONE_YET = "No benchmark has been run yet. Run it with: cd BACKEND && python -m app.benchmark"


def _dir() -> Path:
    return Path(settings.benchmark_results_dir) if settings.benchmark_results_dir else runner.RESULTS_DIR


def _read(name: str) -> BenchmarkRun:
    path = _dir() / name
    if not path.is_file():
        raise HTTPException(status_code=404, detail=NONE_YET if name == "latest.json" else "Run not found")
    return BenchmarkRun.model_validate(json.loads(path.read_text(encoding="utf-8")))


@router.get("/latest", response_model=BenchmarkRun)
def latest_run():
    """The most recent benchmark run, with every per-case result behind its numbers."""
    return _read("latest.json")


@router.get("/runs", response_model=List[dict])
def list_runs():
    """All stored runs, newest first (summary only)."""
    runs = []
    for path in sorted(_dir().glob("run-*.json"), reverse=True):
        data = json.loads(path.read_text(encoding="utf-8"))
        runs.append({k: data[k] for k in ("run_id", "created_at", "dataset_version", "settings")})
    return runs


@router.get("/runs/{run_id}", response_model=BenchmarkRun)
def get_run(run_id: str):
    if not RUN_ID.match(run_id):
        raise HTTPException(status_code=404, detail="Run not found")
    return _read("run-%s.json" % run_id)

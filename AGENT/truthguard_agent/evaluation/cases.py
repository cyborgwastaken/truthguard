from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import List

from pydantic import BaseModel, Field

from ..schemas import AnswerStatus

DEFAULT_CASES = Path(__file__).resolve().parents[2] / "datasets" / "benchmark" / "cases_v1.json"


class BenchmarkCase(BaseModel):
    case_id: str
    case_type: str  # superseded, unresolved_conflict, insufficient_evidence, hard_negative, draft_trap, ...
    question: str
    as_of: date
    expected_status: AnswerStatus
    relevant_document_ids: List[str] = Field(default_factory=list)
    expected_winner_document_ids: List[str] = Field(default_factory=list)
    expected_stale_document_ids: List[str] = Field(default_factory=list)
    # Case-insensitive substring checks on the answer text. Every group needs at least one of its strings.
    expected_answer_contains: List[List[str]] = Field(default_factory=list)
    forbidden_answer_contains: List[str] = Field(default_factory=list)
    note: str = ""


def load_cases(path: Path = DEFAULT_CASES) -> List[BenchmarkCase]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return [BenchmarkCase(**c) for c in data["cases"]]


def dataset_version(path: Path = DEFAULT_CASES) -> str:
    return json.loads(Path(path).read_text(encoding="utf-8"))["dataset_version"]

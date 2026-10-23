"""Request and response shapes for /questions and /answers. The frontend mirrors these in TypeScript."""
from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel
from truthguard_agent.orchestrator import PipelineResult
from truthguard_agent.schemas import AnswerStatus, QuestionIn


class QuestionRequest(QuestionIn):
    """The question, and optionally the date to judge it as of (default: today)."""

    as_of: Optional[date] = None


class AnswerResponse(PipelineResult):
    """The answer and everything behind it: answer + verification (see AGENT orchestrator)."""

    llm_mode: str = "live"  # live, record, cache or replay: a replayed answer is labelled as such


class AnswerSummary(BaseModel):
    answer_id: str
    question: str
    status: AnswerStatus
    as_of: Optional[date] = None
    created_at: datetime

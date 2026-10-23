from __future__ import annotations

from datetime import date
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session
from truthguard_agent.llm import CachingLLM, GroqLLM, LLMClient, LLMError
from truthguard_agent.orchestrator import answer_question

from ..config import settings
from ..db.models import AnswerCitationRow, AnswerRow, ClaimRow, EvidenceLinkRow
from ..db.search import PostgresPassageStore
from ..db.session import get_session
from ..schemas.answers import AnswerResponse, AnswerSummary, QuestionRequest

router = APIRouter(tags=["questions"])


def get_llm() -> LLMClient:
    """The model client for one request, chosen by TRUTHGUARD_LLM_MODE. Tests override this dependency."""
    mode = settings.llm_mode
    try:
        if mode == "replay":
            return CachingLLM(None, settings.llm_cache_path, "replay", model_name=settings.llm_model)
        if not settings.groq_api_key:
            raise HTTPException(
                status_code=503,
                detail="No language-model key is configured. Set GROQ_API_KEY (environment or BACKEND/.env), "
                "or start the backend with TRUTHGUARD_LLM_MODE=replay to use recorded replies.",
            )
        inner = GroqLLM(settings.llm_model, api_key=settings.groq_api_key, temperature=settings.llm_temperature)
        if mode == "live":
            return inner
        return CachingLLM(inner, settings.llm_cache_path, mode)
    except (LLMError, ValueError) as error:
        raise HTTPException(status_code=503, detail="The language model could not be set up: %s" % error)


def _save(session: Session, response: AnswerResponse, as_of: date) -> None:
    answer = response.answer
    row = AnswerRow(
        answer_id=answer.answer_id,
        question=answer.question,
        answer=answer.answer,
        status=answer.status.value,
        conflicts_detected=answer.conflicts_detected,
        resolution_reason=answer.resolution_reason,
        model_version=answer.model_version,
        prompt_version=answer.prompt_version,
        as_of=as_of,
        created_at=answer.created_at,  # the pipeline's own timestamp, not the transaction's now()
        details=response.model_dump(mode="json"),
    )
    row.claims = [
        ClaimRow(
            claim_id=c.claim_id,
            answer_id=answer.answer_id,
            text=c.text,
            claim_type=c.claim_type,
            status=c.status.value,
            evidence_links=[
                EvidenceLinkRow(
                    chunk_id=link.chunk_id,
                    source_id=link.source_id,
                    relation=link.relation.value,
                    rationale=link.rationale,
                    verifier_version=link.verifier_version,
                )
                for link in answer.evidence_links
                if link.claim_id == c.claim_id
            ],
        )
        for c in answer.claims
    ]
    row.citations = [AnswerCitationRow(chunk_id=c.chunk_id, source_id=c.source_id) for c in answer.citations]
    session.add(row)
    session.commit()


@router.post("/questions", response_model=AnswerResponse, status_code=201)
def ask_question(
    payload: QuestionRequest,
    session: Session = Depends(get_session),
    llm: LLMClient = Depends(get_llm),
):
    """Run the full verification pipeline on a question, store the answer and return it.

    Synchronous: with the real model it takes a few seconds (three model calls). A failed check is not a
    server error: it is a normal 201 response whose status is verification_failed."""
    as_of = payload.as_of or date.today()
    try:
        result = answer_question(payload.question, PostgresPassageStore(session), llm, as_of)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error))
    response = AnswerResponse(answer=result.answer, verification=result.verification,
                              llm_mode=getattr(llm, "mode", "live"))
    _save(session, response, as_of)
    return response


@router.get("/answers", response_model=List[AnswerSummary])
def list_answers(limit: int = Query(20, ge=1, le=100), session: Session = Depends(get_session)):
    """The most recent answers, newest first."""
    rows = session.scalars(select(AnswerRow).order_by(AnswerRow.created_at.desc()).limit(limit)).all()
    return [
        AnswerSummary(answer_id=r.answer_id, question=r.question, status=r.status, as_of=r.as_of, created_at=r.created_at)
        for r in rows
    ]


@router.get("/answers/{answer_id}", response_model=AnswerResponse)
def get_answer(answer_id: str, session: Session = Depends(get_session)):
    """A stored answer, exactly as it was produced."""
    row = session.get(AnswerRow, answer_id)
    if row is None or row.details is None:
        raise HTTPException(status_code=404, detail="Answer not found: %s" % answer_id)
    return AnswerResponse.model_validate(row.details)

"""Baseline RAG: retrieve passages, ask the model to answer, return a FinalAnswer.

No conflict checking and no resolver. This is the deliberate \"before\" picture that the benchmark
compares against the full TruthGuard pipeline.
"""
from __future__ import annotations

import uuid
from typing import Optional

from .llm import LLMClient, LLMError
from .retriever import PassageStore, retrieve
from .schemas import AnswerStatus, Claim, ClaimStatus, EvidenceRef, FinalAnswer
from .synthesizer import synthesize

BASELINE_VERSION = "baseline-v1"


def answer_baseline(
    question: str,
    store: PassageStore,
    llm: LLMClient,
    k: int = 8,
    answer_id: Optional[str] = None,
) -> FinalAnswer:
    """Retrieve passages and ask the model to answer from them. No critic, no resolver.

    Returns a FinalAnswer with:
    - status=resolved   when the model produced at least one cited claim.
    - status=insufficient_evidence  when nothing was retrieved, or the model
      produced no usable reply after its allowed attempts.

    conflicts_detected is always 0: the baseline never checks for conflicts.
    That is exactly the weakness the benchmark is designed to measure.
    """
    if not question.strip():
        raise ValueError("question must not be blank")

    aid = answer_id or str(uuid.uuid4())
    passages = retrieve(question, store, k=k, expand_related=True)

    if not passages:
        return FinalAnswer(
            answer_id=aid,
            question=question,
            answer="",
            status=AnswerStatus.INSUFFICIENT_EVIDENCE,
            citations=[],
            conflicts_detected=0,
            resolution_reason="No passages were retrieved for this question.",
            model_version=llm.model_name,
            prompt_version=BASELINE_VERSION,
        )

    result = synthesize(question, passages, llm)

    if not result.ok or not result.claims:
        return FinalAnswer(
            answer_id=aid,
            question=question,
            answer="",
            status=AnswerStatus.INSUFFICIENT_EVIDENCE,
            citations=[],
            conflicts_detected=0,
            resolution_reason=result.failure_reason or "The model produced no usable answer.",
            model_version=llm.model_name,
            prompt_version=BASELINE_VERSION,
        )

    # Build a human-readable answer from the claims.
    answer_text = " ".join(c.text for c in result.claims)
    if result.caveats:
        answer_text += " Note: " + " ".join(result.caveats)

    # Collect unique citations from all claims.
    seen_chunk_ids: set = set()
    citations = []
    for synth_claim in result.claims:
        for chunk_id in synth_claim.citation_chunk_ids:
            if chunk_id not in seen_chunk_ids:
                seen_chunk_ids.add(chunk_id)
                # source_id is the document_id part before "::chunk_"
                source_id = chunk_id.split("::chunk_")[0]
                citations.append(EvidenceRef(source_id=source_id, chunk_id=chunk_id))

    # Wrap synthesized claims into schema Claim objects.
    claims = [
        Claim(
            claim_id=str(uuid.uuid4()),
            answer_id=aid,
            text=c.text,
            claim_type="factual",
            status=ClaimStatus.UNVERIFIED,
        )
        for c in result.claims
    ]

    return FinalAnswer(
        answer_id=aid,
        question=question,
        answer=answer_text,
        status=AnswerStatus.RESOLVED,
        citations=citations,
        conflicts_detected=0,
        resolution_reason=None,
        claims=claims,
        model_version=llm.model_name,
        prompt_version=BASELINE_VERSION,
    )

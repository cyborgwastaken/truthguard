"""Baseline RAG: retrieve passages, ask the model to answer, return a FinalAnswer.

No conflict checking and no resolver. This is the deliberate "before" picture that the benchmark
compares against the full TruthGuard pipeline. It uses plain search only (expand_related=False): pulling
in the documents that supersede or are superseded by a hit is part of what TruthGuard adds, so the
baseline must not get it for free.
"""
from __future__ import annotations

import uuid
from typing import Optional

from .llm import LLMClient
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
    - status=resolved  when the model produced at least one cited claim.
    - status=insufficient_evidence  when nothing was retrieved, or the model answered but made no claim.
    - status=verification_failed  when the model call failed or gave no usable reply after its allowed
      attempts. A failure is not an abstention: the benchmark counts the two separately.

    conflicts_detected is always 0: the baseline never checks for conflicts.
    That is exactly the weakness the benchmark is designed to measure.
    """
    if not question.strip():
        raise ValueError("question must not be blank")

    aid = answer_id or str(uuid.uuid4())
    passages = retrieve(question, store, k=k, expand_related=False)

    def no_answer(status: AnswerStatus, reason: str) -> FinalAnswer:
        return FinalAnswer(
            answer_id=aid,
            question=question,
            answer="",
            status=status,
            citations=[],
            conflicts_detected=0,
            resolution_reason=reason,
            model_version=llm.model_name,
            prompt_version=BASELINE_VERSION,
        )

    if not passages:
        return no_answer(AnswerStatus.INSUFFICIENT_EVIDENCE, "No passages were retrieved for this question.")

    result = synthesize(question, passages, llm)

    if not result.ok:
        return no_answer(AnswerStatus.VERIFICATION_FAILED, result.failure_reason or "The model call failed.")
    if not result.claims:
        return no_answer(
            AnswerStatus.INSUFFICIENT_EVIDENCE,
            " ".join(result.caveats) or "The model produced no usable answer.",
        )

    # Build a human-readable answer from the claims.
    answer_text = " ".join(c.text for c in result.claims)
    if result.caveats:
        answer_text += " Note: " + " ".join(result.caveats)

    # Unique citations from all claims. The synthesizer only returns chunk ids that were retrieved, so
    # the document of each one is looked up in the passages (not guessed from the chunk id's spelling).
    document_of = {p.chunk.chunk_id: p.document.document_id for p in passages}
    seen_chunk_ids: set = set()
    citations = []
    for synth_claim in result.claims:
        for chunk_id in synth_claim.citation_chunk_ids:
            if chunk_id not in seen_chunk_ids:
                seen_chunk_ids.add(chunk_id)
                citations.append(EvidenceRef(source_id=document_of[chunk_id], chunk_id=chunk_id))

    # Claim ids are derived from the answer id, so the same run gives the same ids (benchmark traceability).
    claims = [
        Claim(
            claim_id="%s::c%d" % (aid, number),
            answer_id=aid,
            text=c.text,
            claim_type="factual",
            status=ClaimStatus.UNVERIFIED,
        )
        for number, c in enumerate(result.claims, start=1)
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

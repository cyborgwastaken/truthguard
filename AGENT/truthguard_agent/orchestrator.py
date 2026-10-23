"""The full verification pipeline: retrieve -> synthesize -> critic -> resolve, with explicit failure states.

The orchestrator is plain Python that passes typed results between the agents (DOCS/truthguard_intital_roadmap.md,
section 3). It never lets a failure look like success:

- no passages                              -> insufficient_evidence (no model call)
- synthesizer or critic failed (ok=False)  -> verification_failed
- the model made no claim                  -> insufficient_evidence (D5)
- no current, supported claim is left      -> insufficient_evidence (D5)
- otherwise the resolver decides: resolved or conflict_unresolved

Retrieval is noisy (many retrieved documents have nothing to do with the question), so the critic and the
resolver only see the *scope* of the answer: the documents the drafted claims cite, plus every retrieved
document linked to those by supersession, in either direction. Nothing outside it can create a conflict.

The result is a FinalAnswer (what the user reads) plus a Verification (everything behind it: the passages,
each conflict and who won it, the stale sources, what role each claim plays), so the answer view, the evidence
graph and the trust report can all be built from one self-contained record."""
from __future__ import annotations

import time
import uuid
from collections import Counter
from datetime import date
from typing import Dict, List, Optional, Set

from pydantic import BaseModel, Field

from .critic import UnsupportedClaimFinding, critique
from .llm import LLMClient
from .resolver import resolve
from .retriever import PassageStore, retrieve
from .schemas import (
    AnswerStatus,
    AuthorityLevel,
    Claim,
    ClaimStatus,
    Contradiction,
    CriticResult,
    EvidenceLink,
    EvidenceRef,
    EvidenceRelation,
    FinalAnswer,
    RetrievedPassage,
    Severity,
    StalenessFinding,
)
from .synthesizer import SynthesizedClaim, synthesize

PIPELINE_VERSION = "pipeline-v1"

# What a claim is in the answer. current: the answer rests on it. superseded: it rests only on documents that
# lost (stale, or the losing side of a resolved conflict). conflict_side: one side of an unresolved conflict.
# unsupported: its cited passages do not back it up.
ROLE_CURRENT = "current"
ROLE_SUPERSEDED = "superseded"
ROLE_CONFLICT_SIDE = "conflict_side"
ROLE_UNSUPPORTED = "unsupported"


class PassageView(BaseModel):
    """One retrieved passage with the metadata a reader needs to judge it."""

    chunk_id: str
    document_id: str
    title: str
    text: str
    version: Optional[str] = None
    effective_date: Optional[date] = None
    authority_level: AuthorityLevel = AuthorityLevel.UNKNOWN
    supersedes_document_id: Optional[str] = None
    score: Optional[float] = None  # None for passages added because they supersede/are superseded by a hit
    in_scope: bool = True  # False: retrieved, but unrelated to the claims, so the critic never saw it


class ConflictVerdict(BaseModel):
    """One contradiction the critic found, and what the resolver decided about it."""

    claim: str
    severity: Severity
    source_ids: List[str]
    evidence: List[EvidenceRef]
    status: AnswerStatus  # resolved or conflict_unresolved
    winner_source_ids: List[str] = Field(default_factory=list)
    reason: str


class Verification(BaseModel):
    """Everything behind an answer. `stage` is the last stage that ran."""

    as_of: date
    stage: str = "retrieval"
    critic_ok: bool = False  # True only if the critic finished: an empty list of findings means nothing only then
    passages: List[PassageView] = Field(default_factory=list)
    scope_document_ids: List[str] = Field(default_factory=list)
    conflicts: List[ConflictVerdict] = Field(default_factory=list)
    stale: List[StalenessFinding] = Field(default_factory=list)
    unsupported: List[UnsupportedClaimFinding] = Field(default_factory=list)
    winning_source_ids: List[str] = Field(default_factory=list)
    stale_source_ids: List[str] = Field(default_factory=list)
    claim_roles: Dict[str, str] = Field(default_factory=dict)
    caveats: List[str] = Field(default_factory=list)
    off_topic_ignored: int = 0
    failure_reason: Optional[str] = None
    model_attempts: int = 0
    timings_ms: Dict[str, int] = Field(default_factory=dict)


class PipelineResult(BaseModel):
    answer: FinalAnswer
    verification: Verification


def _view(passage: RetrievedPassage, in_scope: bool) -> PassageView:
    doc = passage.document
    return PassageView(
        chunk_id=passage.chunk.chunk_id,
        document_id=doc.document_id,
        title=doc.title,
        text=passage.chunk.text,
        version=doc.version,
        effective_date=doc.effective_date,
        authority_level=doc.authority_level,
        supersedes_document_id=doc.supersedes_document_id,
        score=passage.score,
        in_scope=in_scope,
    )


def _scope(passages: List[RetrievedPassage], claims: List[SynthesizedClaim]) -> List[RetrievedPassage]:
    """The passages of the documents the claims cite, plus every retrieved document linked to them by a
    supersedes_document_id link (either direction, along chains)."""
    document_of = {p.chunk.chunk_id: p.document.document_id for p in passages}
    documents = {p.document.document_id: p.document for p in passages}
    neighbours: Dict[str, Set[str]] = {doc_id: set() for doc_id in documents}
    for doc_id, doc in documents.items():
        if doc.supersedes_document_id in documents:
            neighbours[doc_id].add(doc.supersedes_document_id)
            neighbours[doc.supersedes_document_id].add(doc_id)
    reached = {document_of[c] for claim in claims for c in claim.citation_chunk_ids}
    frontier = list(reached)
    while frontier:
        for other in neighbours[frontier.pop()]:
            if other not in reached:
                reached.add(other)
                frontier.append(other)
    return [p for p in passages if p.document.document_id in reached]


def _unsupported_indexes(claims: List[SynthesizedClaim], findings: List[UnsupportedClaimFinding]) -> Set[int]:
    """Which claims the critic judged unsupported. The critic reports claim texts."""
    remaining = Counter(f.claim for f in findings)
    flagged: Set[int] = set()
    for index, claim in enumerate(claims):
        if remaining[claim.text] > 0:
            remaining[claim.text] -= 1
            flagged.add(index)
    return flagged


def _links(
    claims: List[Claim],
    synth_claims: List[SynthesizedClaim],
    contradictions: List[Contradiction],
    document_of: Dict[str, str],
) -> List[EvidenceLink]:
    """supports/context links from each claim to the chunks it cites, and contradicts links from a claim to
    the evidence that conflicts with what it cites (only for contradictions the critic found)."""
    links: List[EvidenceLink] = []
    seen = set()

    def add(claim_id: str, chunk_id: str, relation: EvidenceRelation, rationale: str) -> None:
        key = (claim_id, chunk_id, relation)
        if key not in seen:
            seen.add(key)
            links.append(
                EvidenceLink(
                    claim_id=claim_id,
                    chunk_id=chunk_id,
                    source_id=document_of[chunk_id],
                    relation=relation,
                    rationale=rationale,
                    verifier_version=PIPELINE_VERSION,
                )
            )

    for claim, synth in zip(claims, synth_claims):
        relation = EvidenceRelation.SUPPORTS if claim.status == ClaimStatus.SUPPORTED else EvidenceRelation.CONTEXT
        for chunk_id in synth.citation_chunk_ids:
            add(claim.claim_id, chunk_id, relation, "cited by the answer; checked against the passage by the critic")
        cited_docs = {document_of[c] for c in synth.citation_chunk_ids}
        for contradiction in contradictions:
            evidence = [e.chunk_id for e in contradiction.evidence]
            if not cited_docs & {document_of[c] for c in evidence}:
                continue
            for chunk_id in evidence:
                if document_of[chunk_id] not in cited_docs:
                    add(claim.claim_id, chunk_id, EvidenceRelation.CONTRADICTS, contradiction.claim)
    return links


def answer_question(
    question: str,
    store: PassageStore,
    llm: LLMClient,
    as_of: date,
    k: int = 8,
    answer_id: Optional[str] = None,
    use_resolver: bool = True,
) -> PipelineResult:
    """Run the full pipeline. `as_of` is the question date: it decides which supersessions are in force and is
    given to both the critic and the resolver, so they cannot disagree about what is current.

    use_resolver=False is the benchmark's "RAG + critic" setup: the critic's findings are shown, but nothing
    decides between sources, so any contradiction that bears on the question is an unresolved conflict and
    stale sources are not filtered out."""
    if not question.strip():
        raise ValueError("question must not be blank")
    aid = answer_id or str(uuid.uuid4())
    timings: Dict[str, int] = {}
    started = time.monotonic()

    def lap(name: str) -> None:
        nonlocal started
        now = time.monotonic()
        timings[name] = int((now - started) * 1000)
        started = now

    passages = retrieve(question, store, k=k, expand_related=True)
    lap("retrieval")
    # Nothing is in scope until the claims are known: the critic only ever sees the scope.
    verification = Verification(as_of=as_of, passages=[_view(p, False) for p in passages])
    document_of = {p.chunk.chunk_id: p.document.document_id for p in passages}

    def finish(
        status: AnswerStatus,
        reason: str,
        text: str = "",
        claims: Optional[List[Claim]] = None,
        links: Optional[List[EvidenceLink]] = None,
        citations: Optional[List[EvidenceRef]] = None,
        conflicts: int = 0,
        versions: str = PIPELINE_VERSION,
    ) -> PipelineResult:
        verification.timings_ms = dict(timings)
        answer = FinalAnswer(
            answer_id=aid,
            question=question,
            answer=text,
            status=status,
            citations=citations or [],
            conflicts_detected=conflicts,
            resolution_reason=reason,
            claims=claims or [],
            evidence_links=links or [],
            model_version=llm.model_name,
            prompt_version=versions,
        )
        return PipelineResult(answer=answer, verification=verification)

    if not passages:
        return finish(AnswerStatus.INSUFFICIENT_EVIDENCE, "No passages were retrieved for this question.")

    synth = synthesize(question, passages, llm)
    lap("synthesis")
    verification.stage = "synthesis"
    verification.model_attempts += synth.attempts
    verification.caveats = list(synth.caveats)
    versions = "%s+%s" % (synth.prompt_version, PIPELINE_VERSION)
    if not synth.ok:
        verification.failure_reason = synth.failure_reason
        return finish(AnswerStatus.VERIFICATION_FAILED, synth.failure_reason or "The model call failed.", versions=versions)
    if not synth.claims:
        why = " ".join(synth.caveats) or "The model found nothing in the retrieved passages that answers the question."
        return finish(AnswerStatus.INSUFFICIENT_EVIDENCE, why, versions=versions)

    scope = _scope(passages, synth.claims)
    scope_chunks = {p.chunk.chunk_id for p in scope}
    verification.passages = [_view(p, p.chunk.chunk_id in scope_chunks) for p in passages]
    verification.scope_document_ids = sorted({p.document.document_id for p in scope})

    crit = critique(question, synth.claims, scope, llm, as_of)
    lap("critic")
    verification.stage = "critic"
    verification.model_attempts += crit.attempts
    versions = "%s+%s+%s" % (synth.prompt_version, crit.prompt_version, PIPELINE_VERSION)
    if not crit.ok:
        verification.failure_reason = crit.failure_reason
        return finish(AnswerStatus.VERIFICATION_FAILED, crit.failure_reason or "The check failed.", versions=versions)

    findings = crit.findings
    verification.critic_ok = True
    verification.stale = list(findings.staleness)
    verification.unsupported = list(crit.unsupported_findings)
    verification.off_topic_ignored = crit.off_topic_ignored
    flagged = _unsupported_indexes(synth.claims, crit.unsupported_findings)

    # ---- decide ----
    if use_resolver:
        outcome = resolve(scope, findings, as_of)
        status = outcome.status
        reason = outcome.reason
        winners = set(outcome.winning_source_ids)
        stale = set(outcome.stale_source_ids)
        verdicts = [
            resolve(scope, CriticResult(contradictions=[c], needs_resolution=True), as_of)
            for c in findings.contradictions
        ]
    else:
        status = AnswerStatus.CONFLICT_UNRESOLVED if findings.contradictions else AnswerStatus.RESOLVED
        reason = (
            "The critic found a contradiction and no resolver was applied, so no source is preferred."
            if findings.contradictions
            else "No contradiction was detected among the cited sources."
        )
        winners, stale = set(), set()
        verdicts = [None] * len(findings.contradictions)
    lap("resolution")
    verification.stage = "resolution"
    verification.winning_source_ids = sorted(winners)
    verification.stale_source_ids = sorted(stale)
    verification.conflicts = [
        ConflictVerdict(
            claim=c.claim,
            severity=c.severity,
            source_ids=c.source_ids,
            evidence=c.evidence,
            status=v.status if v else AnswerStatus.CONFLICT_UNRESOLVED,
            winner_source_ids=list(v.winning_source_ids) if v else [],
            reason=v.reason if v else reason,
        )
        for c, v in zip(findings.contradictions, verdicts)
    ]

    # ---- what each claim is ----
    losers: Set[str] = set()
    unresolved_sides: Set[str] = set()
    for conflict in verification.conflicts:
        if conflict.status == AnswerStatus.RESOLVED:
            losers |= set(conflict.source_ids) - set(conflict.winner_source_ids)
        else:
            unresolved_sides |= set(conflict.source_ids)
    excluded = (stale | losers) - winners
    roles: List[str] = []
    for index, claim in enumerate(synth.claims):
        docs = {document_of[c] for c in claim.citation_chunk_ids}
        if index in flagged:
            roles.append(ROLE_UNSUPPORTED)
        elif docs <= excluded:
            roles.append(ROLE_SUPERSEDED)
        elif docs & unresolved_sides:
            roles.append(ROLE_CONFLICT_SIDE)
        else:
            roles.append(ROLE_CURRENT)
    claim_status = {
        ROLE_UNSUPPORTED: ClaimStatus.UNSUPPORTED,
        ROLE_SUPERSEDED: ClaimStatus.CONTRADICTED,
    }
    claims = [
        Claim(
            claim_id="%s::c%d" % (aid, number),
            answer_id=aid,
            text=c.text,
            claim_type="factual",
            status=claim_status.get(role, ClaimStatus.SUPPORTED),
        )
        for number, (c, role) in enumerate(zip(synth.claims, roles), start=1)
    ]
    verification.claim_roles = {c.claim_id: role for c, role in zip(claims, roles)}
    links = _links(claims, synth.claims, findings.contradictions, document_of)

    # ---- the answer ----
    in_answer = [
        (c, s) for c, s, role in zip(claims, synth.claims, roles)
        if role in (ROLE_CURRENT, ROLE_CONFLICT_SIDE)
    ]
    if not in_answer:
        # D5: nothing is left that is supported and current, so the passages do not answer the question
        return finish(
            AnswerStatus.INSUFFICIENT_EVIDENCE,
            "The drafted claims were unsupported by their passages or rested only on superseded sources, "
            "so there is not enough evidence. " + reason,
            claims=claims,
            links=links,
            conflicts=len(findings.contradictions),
            versions=versions,
        )

    if status == AnswerStatus.CONFLICT_UNRESOLVED:
        text = "The sources disagree, and nothing in their metadata settles which one applies. " + " ".join(
            "[%s] %s" % (document_of[s.citation_chunk_ids[0]], c.text) for c, s in in_answer
        )
    else:
        text = " ".join(c.text for c, _ in in_answer)
    seen: Set[str] = set()
    citations: List[EvidenceRef] = []
    for _, synth_claim in in_answer:
        for chunk_id in synth_claim.citation_chunk_ids:
            if chunk_id not in seen:
                seen.add(chunk_id)
                citations.append(EvidenceRef(source_id=document_of[chunk_id], chunk_id=chunk_id))
    if flagged:
        reason += " %d claim(s) not backed by their cited passages were left out." % len(flagged)

    return finish(
        status,
        reason,
        text=text,
        claims=claims,
        links=links,
        citations=citations,
        conflicts=len(findings.contradictions),
        versions=versions,
    )

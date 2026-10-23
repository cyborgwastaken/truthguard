"""A trust report: what was checked about an answer, as separate, explained dimensions.

There is deliberately no single score. A "92% trustworthy" number would have to be invented, so each
dimension reports what it measures, its numerator and denominator, and a level (ok, attention, problem or
unknown). Unknown metadata and checks that did not run are reported as unknown, never as fine. A high
evidence coverage cannot hide an unresolved conflict: that is always a warning of its own.
See DOCS/truthguard_expansion_roadmap.md, Feature B."""
from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field

from .orchestrator import PipelineResult
from .schemas import AnswerStatus

OK, ATTENTION, PROBLEM, UNKNOWN = "ok", "attention", "problem", "unknown"


class TrustDimension(BaseModel):
    key: str
    label: str
    definition: str
    numerator: Optional[int] = None
    denominator: Optional[int] = None
    value: Optional[float] = None
    level: str
    detail: str


class TrustReport(BaseModel):
    answer_id: str
    status: AnswerStatus
    dimensions: List[TrustDimension]
    warnings: List[str] = Field(default_factory=list)


def _dimension(key, label, definition, num, den, level, detail) -> TrustDimension:
    return TrustDimension(key=key, label=label, definition=definition, numerator=num, denominator=den,
                          value=(num / den) if den else None, level=level, detail=detail)


def build_trust_report(result: PipelineResult) -> TrustReport:
    answer, check = result.answer, result.verification
    claims, links = answer.claims, answer.evidence_links
    checked = check.critic_ok  # a check that failed or never ran is unknown, not clean
    passages = {p.chunk_id: p for p in check.passages}
    dimensions: List[TrustDimension] = []

    # 1. Evidence coverage: does every drafted claim have evidence attached? (Says nothing about whether it is right.)
    with_evidence = len({link.claim_id for link in links})
    if claims:
        level = OK if with_evidence == len(claims) else ATTENTION
        detail = "%d of %d drafted claims cite at least one passage." % (with_evidence, len(claims))
    else:
        level, detail = UNKNOWN, "No claim was drafted, so there is nothing to cover."
    dimensions.append(_dimension("evidence_coverage", "Evidence coverage",
                                 "drafted claims with at least one cited passage / drafted claims. A citation existing does not prove support: see the next dimension.",
                                 with_evidence if claims else None, len(claims) or None, level, detail))

    # 2. Citation support: did the critic judge each claim backed by the passages it cites?
    if not claims:
        support = _dimension("citation_support", "Citation support", "claims judged backed by their cited passages / drafted claims",
                             None, None, UNKNOWN, "No claim was drafted.")
    elif not checked:
        support = _dimension("citation_support", "Citation support", "claims judged backed by their cited passages / drafted claims",
                             None, len(claims), UNKNOWN, "The check did not finish, so support is unknown.")
    else:
        backed = len(claims) - len(check.unsupported)
        level = OK if backed == len(claims) else (PROBLEM if backed == 0 else ATTENTION)
        detail = ("All drafted claims are backed by their cited passages." if backed == len(claims)
                  else "%d claim(s) were not backed by their cited passages and are left out of the answer." % len(check.unsupported))
        support = _dimension("citation_support", "Citation support", "claims judged backed by their cited passages / drafted claims",
                             backed, len(claims), level, detail)
    dimensions.append(support)

    # 3. Conflicts between sources, and whether the metadata settled them.
    definition = "conflicts between sources that the rules settled / conflicts found. Unresolved conflicts are never counted as settled."
    if not checked:
        dimensions.append(_dimension("conflicts", "Conflicts between sources", definition, None, None, UNKNOWN, "The check did not finish."))
    elif not check.conflicts:
        dimensions.append(_dimension("conflicts", "Conflicts between sources", definition, 0, 0, OK,
                                     "The critic found no contradiction between the sources that bear on the question."))
    else:
        settled = sum(c.status == AnswerStatus.RESOLVED for c in check.conflicts)
        unresolved = len(check.conflicts) - settled
        dimensions.append(_dimension("conflicts", "Conflicts between sources", definition, settled, len(check.conflicts),
                                     PROBLEM if unresolved else OK,
                                     "%d conflict(s): %d settled by explicit metadata, %d unresolved." % (len(check.conflicts), settled, unresolved)))

    # 4. Freshness of the sources the answer rests on.
    cited_docs = list(dict.fromkeys(c.source_id for c in answer.citations))
    stale = set(check.stale_source_ids) | {s.source_id for s in check.stale}
    stale_cited = [d for d in cited_docs if d in stale]
    dated = [d for d in cited_docs if any(p.document_id == d and p.effective_date for p in check.passages)]
    definition = "cited documents with a known effective date / cited documents. A cited document that a newer one supersedes is a problem; an unknown date is reported as unknown."
    if not cited_docs:
        dimensions.append(_dimension("freshness", "Freshness of sources", definition, None, None, UNKNOWN, "The answer cites no document."))
    elif stale_cited:
        dimensions.append(_dimension("freshness", "Freshness of sources", definition, len(dated), len(cited_docs), PROBLEM,
                                     "Cited source(s) already superseded: %s." % ", ".join(stale_cited)))
    elif len(dated) < len(cited_docs):
        dimensions.append(_dimension("freshness", "Freshness of sources", definition, len(dated), len(cited_docs), ATTENTION,
                                     "%d cited document(s) have no effective date, so their currency is unknown (judged as of %s)." % (len(cited_docs) - len(dated), check.as_of)))
    else:
        dimensions.append(_dimension("freshness", "Freshness of sources", definition, len(dated), len(cited_docs), OK,
                                     "Every cited document has an effective date, and none is superseded (judged as of %s)." % check.as_of))

    # 5. Provenance: can every citation and evidence link be traced to a stored passage?
    records = [c.chunk_id for c in answer.citations] + [link.chunk_id for link in links]
    traceable = sum(chunk in passages for chunk in records)
    definition = "citations and evidence links that point to a stored passage with its document and version / all citations and evidence links"
    if records:
        dimensions.append(_dimension("provenance", "Provenance", definition, traceable, len(records),
                                     OK if traceable == len(records) else PROBLEM,
                                     "%d of %d citations and evidence links trace to a stored passage." % (traceable, len(records))))
    else:
        dimensions.append(_dimension("provenance", "Provenance", definition, None, None, UNKNOWN, "There are no citations to trace."))

    # 6. How the verification ended.
    level = {AnswerStatus.RESOLVED: OK, AnswerStatus.CONFLICT_UNRESOLVED: ATTENTION,
             AnswerStatus.INSUFFICIENT_EVIDENCE: ATTENTION, AnswerStatus.VERIFICATION_FAILED: PROBLEM}[answer.status]
    detail = "Ended as %s after the %s stage; %d model call(s)." % (answer.status.value, check.stage, check.model_attempts)
    if check.failure_reason:
        detail += " Failure: %s" % check.failure_reason
    dimensions.append(TrustDimension(key="verification", label="Verification status",
                                     definition="how the pipeline ended: the stage it reached and the status it gave",
                                     level=level, detail=detail))

    warnings: List[str] = []
    unresolved = [c for c in check.conflicts if c.status != AnswerStatus.RESOLVED]
    if unresolved:
        warnings.append("The sources disagree and nothing in their metadata settles it. Coverage and support above do not change that: "
                        "the answer shows both positions and does not choose one.")
    if check.unsupported:
        warnings.append("%d drafted claim(s) were not backed by their cited passages and were left out." % len(check.unsupported))
    if answer.status == AnswerStatus.VERIFICATION_FAILED:
        warnings.append("The check did not finish, so nothing about this answer was verified.")
    if answer.status == AnswerStatus.INSUFFICIENT_EVIDENCE:
        warnings.append("The documents do not answer this question; no claim is made.")
    return TrustReport(answer_id=answer.answer_id, status=answer.status, dimensions=dimensions, warnings=warnings)

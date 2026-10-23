"""Benchmark metrics. Each metric is a ratio with its numerator and denominator spelled out, so the number can
be traced to the cases behind it. A failed check (verification_failed) is never counted as a correct answer
or a correct abstention: it is wrong for status accuracy and is reported on its own."""
from __future__ import annotations

import math
from typing import Callable, Dict, List, Optional

from pydantic import BaseModel, Field

from ..schemas import AnswerStatus
from .cases import BenchmarkCase

CONFIGS = ("baseline", "rag_critic", "full")
CONFIG_LABELS = {
    "baseline": "Plain RAG (search + answer)",
    "rag_critic": "RAG + critic (no resolver)",
    "full": "Full TruthGuard (critic + resolver)",
}


class CaseResult(BaseModel):
    """What one setup produced for one case in one repeat."""

    case_id: str
    config: str
    repeat: int = 1
    status: AnswerStatus
    answer: str = ""
    answer_id: Optional[str] = None
    citation_document_ids: List[str] = Field(default_factory=list)
    retrieved_document_ids: List[str] = Field(default_factory=list)
    winner_document_ids: List[str] = Field(default_factory=list)
    stale_document_ids: List[str] = Field(default_factory=list)
    conflicts_detected: int = 0
    claims_total: int = 0
    claims_supported: int = 0
    latency_ms: int = 0
    failure_reason: Optional[str] = None


class Metric(BaseModel):
    key: str
    label: str
    definition: str
    numerator: Optional[float] = None
    denominator: Optional[float] = None
    value: Optional[float] = None  # None when the denominator is zero or the setup does not produce the data
    unit: str = "ratio"  # ratio or ms
    higher_is_better: Optional[bool] = True
    applies: bool = True
    note: str = ""


def _ratio(key, label, definition, num, den, higher=True, applies=True, note="") -> Metric:
    value = (num / den) if applies and den else None
    return Metric(key=key, label=label, definition=definition, numerator=num if applies else None,
                  denominator=den if applies else None, value=value, higher_is_better=higher, applies=applies, note=note)


def answer_contains_all(answer: str, groups: List[List[str]]) -> bool:
    text = answer.casefold()
    return all(any(option.casefold() in text for option in group) for group in groups)


def answer_contains_any(answer: str, forbidden: List[str]) -> bool:
    text = answer.casefold()
    return any(item.casefold() in text for item in forbidden)


def compute_metrics(config: str, cases: List[BenchmarkCase], results: List[CaseResult]) -> Dict[str, Metric]:
    """The metrics of one setup over all its results (every repeat counts as one result)."""
    by_case = {c.case_id: c for c in cases}
    rows = [(by_case[r.case_id], r) for r in results if r.case_id in by_case]
    produces_winners = config == "full"
    produces_stale = config in ("rag_critic", "full")
    checks_claims = config in ("rag_critic", "full")
    n = len(rows)
    metrics: Dict[str, Metric] = {}

    def add(metric: Metric) -> None:
        metrics[metric.key] = metric

    add(_ratio("status_accuracy", "Status accuracy", "answers whose status equals the expected status / all answers",
               sum(r.status == c.expected_status for c, r in rows), n))
    add(_ratio("verification_failed_rate", "Failed checks", "answers with status verification_failed / all answers (reported on its own; a failure is never a correct answer)",
               sum(r.status == AnswerStatus.VERIFICATION_FAILED for _, r in rows), n, higher=False))

    expect_insufficient = [(c, r) for c, r in rows if c.expected_status == AnswerStatus.INSUFFICIENT_EVIDENCE]
    predicted_insufficient = [(c, r) for c, r in rows if r.status == AnswerStatus.INSUFFICIENT_EVIDENCE]
    add(_ratio("abstention_recall", "Abstains when it should", "no-evidence cases answered insufficient_evidence / no-evidence cases",
               sum(r.status == AnswerStatus.INSUFFICIENT_EVIDENCE for _, r in expect_insufficient), len(expect_insufficient)))
    add(_ratio("abstention_precision", "Abstentions that were right", "insufficient_evidence answers on no-evidence cases / all insufficient_evidence answers",
               sum(c.expected_status == AnswerStatus.INSUFFICIENT_EVIDENCE for c, _ in predicted_insufficient), len(predicted_insufficient)))

    expect_conflict = [(c, r) for c, r in rows if c.expected_status == AnswerStatus.CONFLICT_UNRESOLVED]
    add(_ratio("conflict_recall", "Flags real conflicts", "real-conflict cases answered conflict_unresolved / real-conflict cases",
               sum(r.status == AnswerStatus.CONFLICT_UNRESOLVED for _, r in expect_conflict), len(expect_conflict)))
    expect_resolved = [(c, r) for c, r in rows if c.expected_status == AnswerStatus.RESOLVED]
    add(_ratio("false_conflict_rate", "False conflicts", "cases that should be resolved but were answered conflict_unresolved / cases that should be resolved",
               sum(r.status == AnswerStatus.CONFLICT_UNRESOLVED for _, r in expect_resolved), len(expect_resolved), higher=False))

    with_facts = [(c, r) for c, r in rows if c.expected_answer_contains]
    add(_ratio("key_fact_accuracy", "Key facts present", "answers containing every expected fact / answers to cases that have expected facts",
               sum(answer_contains_all(r.answer, c.expected_answer_contains) for c, r in with_facts), len(with_facts)))
    with_forbidden = [(c, r) for c, r in rows if c.forbidden_answer_contains]
    add(_ratio("outdated_value_rate", "States the outdated value", "answers containing a superseded value / answers to superseded cases",
               sum(answer_contains_any(r.answer, c.forbidden_answer_contains) for c, r in with_forbidden), len(with_forbidden), higher=False))

    with_winner = [(c, r) for c, r in rows if c.expected_winner_document_ids]
    add(_ratio("winner_accuracy", "Picks the right source", "cases whose winning documents equal the expected winners / cases with an expected winner",
               sum(set(r.winner_document_ids) == set(c.expected_winner_document_ids) for c, r in with_winner), len(with_winner),
               applies=produces_winners, note="" if produces_winners else "This setup has no resolver, so it never names a winner."))
    with_stale = [(c, r) for c, r in rows if c.expected_stale_document_ids]
    add(_ratio("stale_detection", "Spots outdated sources", "cases where every expected superseded document is reported stale / cases with a superseded document",
               sum(set(c.expected_stale_document_ids) <= set(r.stale_document_ids) for c, r in with_stale), len(with_stale),
               applies=produces_stale, note="" if produces_stale else "This setup does not check for superseded documents."))

    relevant_total = sum(len(c.relevant_document_ids) for c, _ in rows)
    found = sum(len(set(c.relevant_document_ids) & set(r.retrieved_document_ids)) for c, r in rows)
    add(_ratio("retrieval_recall", "Retrieval recall", "relevant documents retrieved / relevant documents (counted per answer)", found, relevant_total))
    cited = sum(len(r.citation_document_ids) for c, r in rows if c.relevant_document_ids)
    cited_ok = sum(sum(d in c.relevant_document_ids for d in r.citation_document_ids) for c, r in rows if c.relevant_document_ids)
    add(_ratio("citation_precision", "Citations on relevant documents", "citations pointing at a relevant document / all citations (cases with relevant documents)", cited_ok, cited))
    claims = sum(r.claims_total for _, r in rows)
    add(_ratio("claim_support_rate", "Claims backed by their passages", "claims the critic judged supported / all drafted claims", sum(r.claims_supported for _, r in rows), claims,
               applies=checks_claims, note="" if checks_claims else "This setup never checks whether a claim is backed."))

    latencies = sorted(r.latency_ms for _, r in rows)
    mean = (sum(latencies) / n) if n else None
    p95 = latencies[min(n - 1, math.ceil(0.95 * n) - 1)] if n else None
    for key, label, value in (("latency_mean_ms", "Mean time per answer", mean), ("latency_p95_ms", "Slowest 5% (p95)", p95)):
        metrics[key] = Metric(key=key, label=label, definition="wall-clock time of one answer, in milliseconds", value=value,
                              unit="ms", higher_is_better=False, numerator=None, denominator=n)
    return metrics


def consistency(results: List[CaseResult]) -> Dict[str, float]:
    """For repeated runs: per case, the share of repeats that agree with the most common status."""
    by_case: Dict[str, List[str]] = {}
    for r in results:
        by_case.setdefault(r.case_id, []).append(r.status.value)
    return {cid: max(statuses.count(s) for s in set(statuses)) / len(statuses) for cid, statuses in by_case.items()}

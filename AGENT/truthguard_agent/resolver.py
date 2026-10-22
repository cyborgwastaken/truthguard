"""Deterministic resolution rules (no language model, no clock). The rules, their order and the reasons
behind them are in DOCS/resolver-rules.md; the comments here only point at them (R1 to R7, D1 to D11)."""
from __future__ import annotations

from datetime import date, datetime
from typing import Dict, List, Optional, Tuple

from pydantic import BaseModel, Field

from .schemas import (
    AnswerStatus,
    AuthorityLevel,
    CriticResult,
    Document,
    RetrievedPassage,
)

# R3: draft and informal rank equal (D3); unknown has no rank, so it neither outranks nor is outranked.
_AUTHORITY_RANK = {
    AuthorityLevel.OFFICIAL: 2,
    AuthorityLevel.DRAFT: 1,
    AuthorityLevel.INFORMAL: 1,
}


_Ignored = Tuple[str, str, str]  # (superseder id, target id, why the supersession does not apply)


class ResolutionOutcome(BaseModel):
    status: AnswerStatus
    winning_source_ids: List[str] = Field(default_factory=list)
    stale_source_ids: List[str] = Field(default_factory=list)
    reason: str = Field(min_length=1)


def resolve(passages: List[RetrievedPassage], critic: CriticResult, as_of: date) -> ResolutionOutcome:
    """Decide whether the retrieved evidence justifies one answer, and say why.

    `as_of` is required: the resolver never reads the clock (D4). Statuses returned are resolved,
    conflict_unresolved and insufficient_evidence; verification_failed belongs to the orchestrator.
    """
    if isinstance(as_of, datetime):
        raise TypeError("as_of must be a date, not a datetime: effective dates are compared by day")
    if not passages:
        return ResolutionOutcome(
            status=AnswerStatus.INSUFFICIENT_EVIDENCE,
            reason="No relevant passages were retrieved; rule: no relevant evidence.",
        )

    docs = _documents(passages)
    superseded_by, ignored = _supersessions(docs, as_of)
    stale = [doc_id for doc_id in docs if doc_id in superseded_by]

    if not critic.contradictions:
        if critic.needs_resolution:
            # D9: a flagged conflict must come with evidence, so the result is not trusted
            return ResolutionOutcome(
                status=AnswerStatus.CONFLICT_UNRESOLVED,
                stale_source_ids=stale,
                reason="The critic reported a conflict that needs resolution but gave no contradiction to "
                "resolve, so no source can be preferred.",
            )
        return ResolutionOutcome(
            status=AnswerStatus.RESOLVED,
            stale_source_ids=stale,
            reason="No contradiction was detected among the retrieved sources.",
        )

    winners: List[str] = []
    reasons: List[str] = []
    unresolved = False
    for contradiction in critic.contradictions:
        winner, why = _judge_conflict(_unique(contradiction.source_ids), docs, superseded_by, ignored)
        if winner is None:
            unresolved = True
        else:
            winners.append(winner)
        reasons.append(why)
    return ResolutionOutcome(
        status=AnswerStatus.CONFLICT_UNRESOLVED if unresolved else AnswerStatus.RESOLVED,
        winning_source_ids=_unique(winners),
        stale_source_ids=stale,
        reason=" ".join(_unique(reasons)),  # the critic reports one contradiction per claim, often for one pair
    )


def _documents(passages: List[RetrievedPassage]) -> Dict[str, Document]:
    docs: Dict[str, Document] = {}
    for passage in passages:
        docs.setdefault(passage.document.document_id, passage.document)
    return docs


def _unique(items: List[str]) -> List[str]:
    return list(dict.fromkeys(items))


def _in_force(doc: Document, as_of: date) -> bool:
    return doc.effective_date is not None and doc.effective_date <= as_of


def _may_supersede(superseder: Document, target: Document) -> bool:
    # D2: official can supersede anything; unknown only a non-official document; draft and informal never.
    if superseder.authority_level == AuthorityLevel.OFFICIAL:
        return True
    if superseder.authority_level == AuthorityLevel.UNKNOWN:
        return target.authority_level != AuthorityLevel.OFFICIAL
    return False


def _supersessions(docs: Dict[str, Document], as_of: date) -> Tuple[Dict[str, List[str]], List[_Ignored]]:
    """R1 and R2 over all retrieved documents.

    Returns (superseded_by, ignored). superseded_by maps a document to the retrieved documents that
    supersede it and are in force. ignored lists the supersessions that do not apply, with the reason.
    A document is superseded only by a document that names it directly: staleness is not inherited
    along a chain. A target that was not retrieved is skipped (nothing to compare).
    """
    superseded_by: Dict[str, List[str]] = {}
    ignored: List[_Ignored] = []
    for doc_id, doc in docs.items():
        target = docs.get(doc.supersedes_document_id) if doc.supersedes_document_id else None
        if target is None:
            continue
        if doc.effective_date is None:
            why = "%s names %s but its effective date is unknown" % (doc_id, target.document_id)
        elif not _in_force(doc, as_of):
            why = "%s names %s but takes effect on %s, after %s" % (
                doc_id, target.document_id, doc.effective_date.isoformat(), as_of.isoformat())
        elif not _may_supersede(doc, target):
            why = "%s (%s) cannot supersede %s (%s)" % (
                doc_id, doc.authority_level.value, target.document_id, target.authority_level.value)
        else:
            why = ""
        if why:
            ignored.append((doc_id, target.document_id, why))
        else:
            superseded_by.setdefault(target.document_id, []).append(doc_id)
    return superseded_by, ignored


def _outranked(doc: Document, others: List[Document]) -> Optional[Document]:
    rank = _AUTHORITY_RANK.get(doc.authority_level)
    if rank is None:
        return None
    for other in others:
        if _AUTHORITY_RANK.get(other.authority_level, 0) > rank:
            return other
    return None


def _close_under_supersession(
    source_ids: List[str], superseded_by: Dict[str, List[str]]
) -> Tuple[List[str], List[str]]:
    """Step 1, first part: add every retrieved document linked to a side by an applicable supersession, in
    either direction and along chains. Returns (all sides, why each added document joined)."""
    supersedes: Dict[str, List[str]] = {}
    for target_id, superseder_ids in superseded_by.items():
        for superseder_id in superseder_ids:
            supersedes.setdefault(superseder_id, []).append(target_id)

    sides = list(source_ids)
    joined: List[str] = []
    for doc_id in sides:  # the list grows while we walk it, so chains are followed
        for superseder_id in superseded_by.get(doc_id, []):
            if superseder_id not in sides:
                sides.append(superseder_id)
                joined.append("%s joins the conflict because it supersedes %s." % (superseder_id, doc_id))
        for target_id in supersedes.get(doc_id, []):
            if target_id not in sides:
                sides.append(target_id)
                joined.append("%s joins the conflict because %s supersedes it." % (target_id, doc_id))
    return sides, joined


def _judge_conflict(
    source_ids: List[str],
    docs: Dict[str, Document],
    superseded_by: Dict[str, List[str]],
    ignored: List[_Ignored],
) -> Tuple[Optional[str], str]:
    """One conflict: (winner id or None, reason). Resolved only if exactly one side remains."""
    missing = [i for i in source_ids if i not in docs]
    if missing:
        return None, "The contradiction cites %s, not among the retrieved passages, so it cannot be judged." % (
            ", ".join(missing))
    if len(source_ids) < 2:
        return None, "The contradiction names fewer than two sources, so it cannot be judged."

    sides, parts = _close_under_supersession(source_ids, superseded_by)
    remaining = list(sides)
    for doc_id in sides:
        if doc_id in superseded_by:
            remaining.remove(doc_id)
            by = superseded_by[doc_id][0]
            parts.append("%s explicitly supersedes %s (effective %s); rule: explicit supersession." % (
                by, doc_id, docs[by].effective_date.isoformat()))

    for doc_id in list(remaining):
        beater = _outranked(docs[doc_id], [docs[i] for i in remaining if i != doc_id])
        if beater is not None:
            remaining.remove(doc_id)
            parts.append("%s is %s and %s is %s; rule: authority." % (
                beater.document_id, beater.authority_level.value, doc_id, docs[doc_id].authority_level.value))

    if len(remaining) == 1:
        if all(i in superseded_by for i in source_ids):
            parts.append("Every source listed in the contradiction is superseded, so the conflict is moot and "
                         "%s holds the position." % remaining[0])
        return remaining[0], " ".join(parts)

    if not remaining:
        parts.append("Every source in this conflict is superseded by another (a supersession loop among %s), so "
                     "no position is established." % ", ".join(sides))
    else:
        levels = ", ".join("%s is %s" % (i, docs[i].authority_level.value) for i in remaining)
        parts.append("%s have no established precedence (%s) and none supersedes another; rule: equal "
                     "authority, no supersession." % (" and ".join(remaining), levels))
        undated = [i for i in remaining if docs[i].effective_date is None]
        if undated:
            parts.append("Effective date unknown for %s." % ", ".join(undated))
    for superseder_id, target_id, why in ignored:
        if superseder_id in sides or target_id in sides:
            parts.append("Ignored supersession: %s." % why)
    return None, " ".join(parts)

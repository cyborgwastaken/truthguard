"""Tests for baseline.py.

All tests use FakeLLM and InMemoryPassageStore so they run offline and cost nothing.
"""
from __future__ import annotations

import json
from datetime import date

import pytest

from truthguard_agent.baseline import BASELINE_VERSION, answer_baseline
from truthguard_agent.llm import FakeLLM, LLMError
from truthguard_agent.retriever import InMemoryPassageStore, retrieve
from truthguard_agent.schemas import AnswerStatus, Document


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _doc(document_id: str, content: str, **kwargs) -> Document:
    defaults = dict(
        title=document_id,
        version="1",
        created_at=date(2026, 1, 1),
        effective_date=date(2026, 1, 1),
    )
    defaults.update(kwargs)
    return Document(document_id=document_id, content=content, **defaults)


def _reply(claims: list, caveats: list = None) -> str:
    return json.dumps({"claims": claims, "caveats": caveats or []})


def _claim(text: str, *chunk_ids: str) -> dict:
    return {"text": text, "citation_chunk_ids": list(chunk_ids)}


def _store_with(*docs: Document) -> InMemoryPassageStore:
    return InMemoryPassageStore(docs)


# ---------------------------------------------------------------------------
# Core behaviour
# ---------------------------------------------------------------------------

def test_returns_resolved_when_model_gives_claims():
    doc = _doc("remote_policy", "Employees may work remotely three days per week.")
    store = _store_with(doc)
    good_reply = _reply([_claim("Employees may work remotely three days.", "remote_policy::chunk_000")])
    llm = FakeLLM([good_reply])

    answer = answer_baseline("How many remote days are allowed?", store, llm)

    assert answer.status == AnswerStatus.RESOLVED
    assert answer.answer != ""
    assert len(answer.citations) == 1
    assert answer.citations[0].source_id == "remote_policy"
    assert answer.citations[0].chunk_id == "remote_policy::chunk_000"
    assert answer.conflicts_detected == 0


def test_returns_insufficient_evidence_when_nothing_retrieved():
    # An empty store has no passages at all, so retrieve() returns [].
    store = InMemoryPassageStore([])
    llm = FakeLLM([])  # should never be called

    answer = answer_baseline("What is the gym membership policy?", store, llm)

    assert answer.status == AnswerStatus.INSUFFICIENT_EVIDENCE
    assert answer.answer == ""
    assert answer.citations == []
    assert len(llm.calls) == 0  # llm was never called


def test_returns_verification_failed_when_model_call_fails():
    """A failed call is not an abstention: the benchmark must be able to count it separately."""
    doc = _doc("policy", "Employees get 10 sick days per year.")
    store = _store_with(doc)
    llm = FakeLLM([LLMError("API timeout")])

    answer = answer_baseline("How many sick days?", store, llm)

    assert answer.status == AnswerStatus.VERIFICATION_FAILED
    assert answer.answer == ""
    assert answer.citations == []
    assert "API timeout" in answer.resolution_reason


def test_returns_verification_failed_when_the_model_gives_two_unusable_replies():
    doc = _doc("policy", "Employees get 10 sick days per year.")
    store = _store_with(doc)
    llm = FakeLLM(["not json", "still not json"])

    answer = answer_baseline("How many sick days?", store, llm)

    assert answer.status == AnswerStatus.VERIFICATION_FAILED
    assert len(llm.calls) == 2  # one try and one retry, then a visible failure


def test_returns_insufficient_evidence_when_model_produces_no_claims():
    doc = _doc("policy", "Employees get 10 sick days per year.")
    store = _store_with(doc)
    # Model gives caveats only, no claims
    no_claim_reply = _reply([], ["I could not answer from the given passages."])
    llm = FakeLLM([no_claim_reply])

    answer = answer_baseline("How many sick days?", store, llm)

    assert answer.status == AnswerStatus.INSUFFICIENT_EVIDENCE


def test_conflicts_detected_is_always_zero():
    """The baseline never flags conflicts. That is the point of having a baseline."""
    doc_a = _doc("policy_a", "The expense limit is $150.")
    doc_b = _doc("policy_b", "The expense limit is $300.")
    store = _store_with(doc_a, doc_b)
    good_reply = _reply([
        _claim("Policy A says $150.", "policy_a::chunk_000"),
        _claim("Policy B says $300.", "policy_b::chunk_000"),
    ])
    llm = FakeLLM([good_reply])

    answer = answer_baseline("What is the expense limit?", store, llm)

    assert answer.conflicts_detected == 0


def test_citations_are_deduplicated():
    """If two claims cite the same chunk, it appears once in citations."""
    doc = _doc("policy", "The limit is $150 per event.")
    store = _store_with(doc)
    reply = _reply([
        _claim("Claim one.", "policy::chunk_000"),
        _claim("Claim two.", "policy::chunk_000"),
    ])
    llm = FakeLLM([reply])

    answer = answer_baseline("What is the limit?", store, llm)

    assert len(answer.citations) == 1


def test_answer_id_is_passed_through():
    doc = _doc("policy", "The limit is $150.")
    store = _store_with(doc)
    reply = _reply([_claim("The limit is $150.", "policy::chunk_000")])
    llm = FakeLLM([reply])

    answer = answer_baseline("What is the limit?", store, llm, answer_id="test-id-123")

    assert answer.answer_id == "test-id-123"


def test_model_version_and_prompt_version_are_set():
    doc = _doc("policy", "Parental leave is 16 weeks.")
    store = _store_with(doc)
    reply = _reply([_claim("Parental leave is 16 weeks.", "policy::chunk_000")])
    llm = FakeLLM([reply], model_name="fake-model-v1")

    answer = answer_baseline("How long is parental leave?", store, llm)

    assert answer.model_version == "fake-model-v1"
    assert answer.prompt_version == BASELINE_VERSION


def test_claims_are_attached_to_answer():
    doc = _doc("policy", "Employees get 25 annual leave days.")
    store = _store_with(doc)
    reply = _reply([_claim("Employees get 25 annual leave days.", "policy::chunk_000")])
    llm = FakeLLM([reply])

    answer = answer_baseline("How many annual leave days?", store, llm)

    assert len(answer.claims) == 1
    assert answer.claims[0].answer_id == answer.answer_id
    assert answer.claims[0].text == "Employees get 25 annual leave days."


def test_blank_question_raises():
    store = _store_with(_doc("doc", "Some content."))
    llm = FakeLLM([])

    with pytest.raises(ValueError):
        answer_baseline("   ", store, llm)


def test_caveats_are_appended_to_answer_text():
    doc = _doc("policy", "The budget is $200 per day.")
    store = _store_with(doc)
    reply = _reply(
        [_claim("The budget is $200.", "policy::chunk_000")],
        ["Figures may vary by region."],
    )
    llm = FakeLLM([reply])

    answer = answer_baseline("What is the daily budget?", store, llm)

    assert "Figures may vary by region." in answer.answer


# ---------------------------------------------------------------------------
# The baseline is plain search: no supersession expansion, deterministic ids
# ---------------------------------------------------------------------------

def _superseded_pair():
    v1 = _doc("remote_v1", "Employees may work remotely five days per week.", authority_level="official")
    # shares no word with the question below, so plain search finds only v1
    v2 = _doc(
        "remote_v2",
        "This amendment replaces the earlier rule with three.",
        authority_level="official",
        supersedes_document_id="remote_v1",
        effective_date=date(2026, 4, 15),
    )
    return _store_with(v1, v2)


QUESTION = "How many days per week can employees work remotely?"


def test_the_pair_is_a_real_test_the_default_retriever_would_add_the_amendment():
    store = _superseded_pair()
    assert {p.document.document_id for p in retrieve(QUESTION, store)} == {"remote_v1", "remote_v2"}
    assert {p.document.document_id for p in retrieve(QUESTION, store, expand_related=False)} == {"remote_v1"}


def test_baseline_does_not_pull_in_the_superseding_document():
    """Expansion is part of what TruthGuard adds; a baseline that gets it is not a baseline."""
    llm = FakeLLM([_reply([_claim("Five days.", "remote_v1::chunk_000")])])

    answer = answer_baseline(QUESTION, _superseded_pair(), llm)

    shown_to_the_model = llm.calls[0]["user"]
    assert "remote_v1::chunk_000" in shown_to_the_model
    assert "remote_v2" not in shown_to_the_model
    assert [c.source_id for c in answer.citations] == ["remote_v1"]


def test_citation_source_id_is_the_document_of_the_passage():
    paragraph = "alpha " * 100
    doc = _doc("policy", paragraph + "\n\n" + paragraph.replace("alpha", "alpha beta"))
    store = _store_with(doc)
    llm = FakeLLM([_reply([_claim("A claim.", "policy::chunk_001")])])

    answer = answer_baseline("alpha beta", store, llm)

    assert [(c.source_id, c.chunk_id) for c in answer.citations] == [("policy", "policy::chunk_001")]


def test_claim_ids_come_from_the_answer_id_so_runs_are_reproducible():
    doc = _doc("policy", "The limit is $150. The deadline is 14 days.")
    store = _store_with(doc)
    reply = _reply([_claim("Limit.", "policy::chunk_000"), _claim("Deadline.", "policy::chunk_000")])

    first = answer_baseline("limit deadline", store, FakeLLM([reply]), answer_id="a1")
    second = answer_baseline("limit deadline", store, FakeLLM([reply]), answer_id="a1")

    assert [c.claim_id for c in first.claims] == ["a1::c1", "a1::c2"]
    assert [c.claim_id for c in second.claims] == [c.claim_id for c in first.claims]

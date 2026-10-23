"""The full pipeline on the real T01 fixtures, with scripted model replies (no network).

Reply order for FakeLLM: 1 synthesizer, 2 critic contradictions (only if the passages come from two or more
documents), 3 critic support verdicts (only if there are claims)."""
import json
import pathlib
from datetime import date

import pytest

from truthguard_agent.llm import FakeLLM, LLMError
from truthguard_agent.orchestrator import answer_question
from truthguard_agent.retriever import InMemoryPassageStore
from truthguard_agent.schemas import AnswerStatus, ClaimStatus, Document, EvidenceRelation

FIXTURES = pathlib.Path(__file__).resolve().parents[1] / "datasets" / "fixtures"
AS_OF = date(2026, 10, 20)


@pytest.fixture(scope="module")
def store():
    docs = [Document(**json.loads(p.read_text(encoding="utf-8"))) for p in sorted(FIXTURES.glob("*.json"))]
    return InMemoryPassageStore(docs)


def synth(claims, caveats=None):
    return json.dumps({"claims": [{"text": t, "citation_chunk_ids": c} for t, c in claims], "caveats": caveats or []})


def contradictions(*items):
    return json.dumps(
        {"contradictions": [{"claim": c, "chunk_ids": ids, "severity": "high", "bears_on_question": True} for c, ids in items]}
    )


def verdicts(*supported):
    return json.dumps({"verdicts": [{"claim_index": i, "supported": s, "reason": "r"} for i, s in enumerate(supported)]})


V1, V2 = "remote_policy_v1::chunk_000", "remote_policy_v2::chunk_000"
Q_REMOTE = "How many days per week can employees work remotely?"


def run(store, question, replies, as_of=AS_OF):
    llm = FakeLLM(replies)
    return answer_question(question, store, llm, as_of, answer_id="a1"), llm


# ---- the three required demo scenarios, plus a hard negative ---------------------------------------------

def test_superseded_policy_is_resolved_in_favor_of_the_amendment(store):
    result, llm = run(store, Q_REMOTE, [
        synth([("Employees may work remotely five days per week.", [V1]), ("Employees may work remotely three days per week.", [V2])]),
        contradictions(("remote days per week", [V1, V2])),
        verdicts(True, True),
    ])
    answer, check = result.answer, result.verification
    assert answer.status == AnswerStatus.RESOLVED
    assert "three days" in answer.answer and "five days" not in answer.answer
    assert [c.chunk_id for c in answer.citations] == [V2]  # only the winner is cited as the answer
    assert answer.conflicts_detected == 1
    assert "remote_policy_v2" in answer.resolution_reason and "remote_policy_v1" in answer.resolution_reason
    assert check.winning_source_ids == ["remote_policy_v2"]
    assert check.stale_source_ids == ["remote_policy_v1"]
    assert [s.source_id for s in check.stale] == ["remote_policy_v1"]
    assert check.stage == "resolution"
    assert len(llm.calls) == 3


def test_superseded_policy_links_the_winning_claim_to_the_evidence_it_beat(store):
    result, _ = run(store, Q_REMOTE, [
        synth([("Five days.", [V1]), ("Three days.", [V2])]),
        contradictions(("remote days", [V1, V2])),
        verdicts(True, True),
    ])
    links = {(l.claim_id, l.chunk_id, l.relation) for l in result.answer.evidence_links}
    assert ("a1::c2", V2, EvidenceRelation.SUPPORTS) in links
    assert ("a1::c2", V1, EvidenceRelation.CONTRADICTS) in links
    assert ("a1::c1", V1, EvidenceRelation.CONTEXT) in links  # the superseded claim: context, not support
    assert ("a1::c1", V2, EvidenceRelation.CONTRADICTS) in links


def test_same_date_before_the_amendment_takes_effect_is_not_resolved(store):
    """as_of before remote_policy_v2's effective date (2026-04-15): both documents are official, nothing supersedes."""
    result, _ = run(store, Q_REMOTE, [
        synth([("Five days.", [V1]), ("Three days.", [V2])]),
        contradictions(("remote days", [V1, V2])),
        verdicts(True, True),
    ], as_of=date(2026, 1, 20))
    assert result.answer.status == AnswerStatus.CONFLICT_UNRESOLVED
    assert result.verification.winning_source_ids == []


def test_unresolved_conflict_shows_both_positions(store):
    fin, hr = "expense_receipt_deadline_finance::chunk_000", "expense_receipt_deadline_hr::chunk_000"
    result, _ = run(store, "How long do employees have to submit expense receipts?", [
        synth([("Finance requires receipts within 14 days.", [fin]), ("HR allows 30 days.", [hr])]),
        contradictions(("receipt deadline", [fin, hr])),
        verdicts(True, True),
    ])
    answer = result.answer
    assert answer.status == AnswerStatus.CONFLICT_UNRESOLVED
    assert "14 days" in answer.answer and "30 days" in answer.answer
    assert {c.chunk_id for c in answer.citations} == {fin, hr}
    assert result.verification.winning_source_ids == []
    assert "no established precedence" in answer.resolution_reason


def test_insufficient_evidence_when_the_model_finds_nothing(store):
    result, llm = run(store, "What is Acme Corp's policy on employee stock options?", [
        synth([], ["The passages do not mention stock options."]),
    ])
    assert result.answer.status == AnswerStatus.INSUFFICIENT_EVIDENCE
    assert result.answer.answer == "" and result.answer.citations == []
    assert "stock options" in result.answer.resolution_reason
    assert len(llm.calls) == 1  # the critic is not asked about an answer that has no claims


def test_hard_negative_different_groups_are_not_a_conflict(store):
    mgr, intern = "remote_work_managers::chunk_000", "remote_work_interns::chunk_000"
    result, _ = run(store, "How many remote days per week can managers take versus interns?", [
        synth([("Managers may work remotely two days.", [mgr]), ("Interns have a different rule.", [intern])]),
        contradictions(),
        verdicts(True, True),
    ])
    assert result.answer.status == AnswerStatus.RESOLVED
    assert result.answer.conflicts_detected == 0
    assert "Managers" in result.answer.answer and "Interns" in result.answer.answer


# ---- failure and edge paths ------------------------------------------------------------------------------

def test_no_passages_is_insufficient_evidence_without_calling_the_model():
    llm = FakeLLM([])
    result = answer_question("anything", InMemoryPassageStore([]), llm, AS_OF)
    assert result.answer.status == AnswerStatus.INSUFFICIENT_EVIDENCE
    assert llm.calls == []


def test_synthesizer_failure_is_verification_failed(store):
    result, _ = run(store, Q_REMOTE, [LLMError("Groq API error 503")])
    assert result.answer.status == AnswerStatus.VERIFICATION_FAILED
    assert "503" in result.answer.resolution_reason and result.verification.failure_reason
    assert result.answer.answer == "" and result.verification.stage == "synthesis"


def test_bad_synthesizer_replies_are_verification_failed(store):
    result, llm = run(store, Q_REMOTE, ["not json", "still not json"])
    assert result.answer.status == AnswerStatus.VERIFICATION_FAILED
    assert len(llm.calls) == 2


def test_critic_failure_is_verification_failed_never_a_clean_pass(store):
    result, _ = run(store, Q_REMOTE, [synth([("Three days.", [V2])]), LLMError("timeout")])
    assert result.answer.status == AnswerStatus.VERIFICATION_FAILED
    assert "timeout" in result.answer.resolution_reason
    assert result.answer.answer == "" and result.verification.stage == "critic"


def test_all_claims_unsupported_is_insufficient_evidence(store):
    result, _ = run(store, Q_REMOTE, [
        synth([("Seven days.", [V1])]),
        contradictions(),
        verdicts(False),
    ])
    assert result.answer.status == AnswerStatus.INSUFFICIENT_EVIDENCE
    assert result.answer.answer == ""
    assert [c.status for c in result.answer.claims] == [ClaimStatus.UNSUPPORTED]


def test_an_unsupported_claim_is_left_out_of_the_answer_but_kept_and_flagged(store):
    result, _ = run(store, Q_REMOTE, [
        synth([("Three days per week.", [V2]), ("Remote work is paid double.", [V2])]),
        contradictions(),
        verdicts(True, False),
    ])
    answer = result.answer
    assert answer.status == AnswerStatus.RESOLVED
    assert answer.answer == "Three days per week."
    assert [c.status for c in answer.claims] == [ClaimStatus.SUPPORTED, ClaimStatus.UNSUPPORTED]
    assert "1 claim(s) not backed" in answer.resolution_reason
    assert [u.claim for u in result.verification.unsupported] == ["Remote work is paid double."]


def test_no_contradiction_but_a_stale_document_still_lists_it_and_answers_from_the_current_one(store):
    result, _ = run(store, Q_REMOTE, [
        synth([("Five days.", [V1]), ("Three days.", [V2])]),
        contradictions(),  # the critic missed the conflict
        verdicts(True, True),
    ])
    assert result.answer.status == AnswerStatus.RESOLVED
    assert result.answer.answer == "Three days."  # the claim resting only on the stale document is not the answer
    assert "remote_policy_v1" in result.verification.stale_source_ids


def test_ids_versions_and_timings_are_filled_in(store):
    result, _ = run(store, Q_REMOTE, [synth([("Three days.", [V2])]), contradictions(), verdicts(True)])
    answer = result.answer
    assert answer.answer_id == "a1" and [c.claim_id for c in answer.claims] == ["a1::c1"]
    assert answer.model_version == "fake-llm"
    assert "synthesizer-v1" in answer.prompt_version and "critic-v1" in answer.prompt_version
    assert set(result.verification.timings_ms) == {"retrieval", "synthesis", "critic", "resolution"}


def test_the_verification_carries_every_retrieved_passage_with_its_metadata(store):
    result, _ = run(store, Q_REMOTE, [synth([("Three days.", [V2])]), contradictions(), verdicts(True)])
    by_chunk = {p.chunk_id: p for p in result.verification.passages}
    assert by_chunk[V2].effective_date == date(2026, 4, 15)
    assert by_chunk[V2].supersedes_document_id == "remote_policy_v1"
    assert by_chunk[V2].text and by_chunk[V2].title


def test_blank_question_is_rejected(store):
    with pytest.raises(ValueError):
        answer_question("   ", store, FakeLLM([]), AS_OF)


def test_the_result_round_trips_through_json(store):
    result, _ = run(store, Q_REMOTE, [synth([("Three days.", [V2])]), contradictions(), verdicts(True)])
    restored = type(result).model_validate_json(result.model_dump_json())
    assert restored == result


def test_unrelated_superseded_documents_are_out_of_scope_and_never_reach_the_critic(store):
    """Retrieval pulls in noise such as annual_leave_policy_v1/v2; they are stale but irrelevant to this answer."""
    result, llm = run(store, Q_REMOTE, [synth([("Three days.", [V2])]), contradictions(), verdicts(True)])
    check = result.verification
    by_doc = {p.document_id: p for p in check.passages}
    assert "annual_leave_policy_v1" in by_doc and by_doc["annual_leave_policy_v1"].in_scope is False
    assert by_doc["remote_policy_v1"].in_scope is True  # linked to the cited v2 by supersession
    assert "annual_leave_policy_v1" not in check.stale_source_ids
    assert all(s.source_id != "annual_leave_policy_v1" for s in check.stale)
    critic_prompt = llm.calls[1]["user"]
    assert "remote_policy_v2" in critic_prompt and "annual_leave_policy_v1" not in critic_prompt
    assert check.scope_document_ids == ["remote_policy_v1", "remote_policy_v2"]


def test_each_conflict_gets_its_own_verdict(store):
    result, _ = run(store, Q_REMOTE, [
        synth([("Five days.", [V1]), ("Three days.", [V2])]),
        contradictions(("remote days", [V1, V2])),
        verdicts(True, True),
    ])
    (conflict,) = result.verification.conflicts
    assert conflict.status == AnswerStatus.RESOLVED
    assert conflict.winner_source_ids == ["remote_policy_v2"]
    assert set(conflict.source_ids) == {"remote_policy_v1", "remote_policy_v2"}
    assert [e.chunk_id for e in conflict.evidence] == [V1, V2] or {e.chunk_id for e in conflict.evidence} == {V1, V2}
    assert "explicit supersession" in conflict.reason


def test_unresolved_conflict_verdict_has_no_winner(store):
    fin, hr = "expense_receipt_deadline_finance::chunk_000", "expense_receipt_deadline_hr::chunk_000"
    result, _ = run(store, "How long do employees have to submit expense receipts?", [
        synth([("14 days.", [fin]), ("30 days.", [hr])]),
        contradictions(("receipt deadline", [fin, hr])),
        verdicts(True, True),
    ])
    (conflict,) = result.verification.conflicts
    assert conflict.status == AnswerStatus.CONFLICT_UNRESOLVED and conflict.winner_source_ids == []


def test_claim_roles_and_statuses(store):
    result, _ = run(store, Q_REMOTE, [
        synth([("Five days.", [V1]), ("Three days.", [V2]), ("Free lunch.", [V2])]),
        contradictions(("remote days", [V1, V2])),
        verdicts(True, True, False),
    ])
    roles = result.verification.claim_roles
    assert roles == {"a1::c1": "superseded", "a1::c2": "current", "a1::c3": "unsupported"}
    assert [c.status for c in result.answer.claims] == [
        ClaimStatus.CONTRADICTED, ClaimStatus.SUPPORTED, ClaimStatus.UNSUPPORTED]


def test_without_the_resolver_a_contradiction_is_an_unresolved_conflict_and_nothing_is_filtered(store):
    """The benchmark's "RAG + critic" setup: the critic's finding is shown, but nothing decides between sources."""
    llm = FakeLLM([
        synth([("Five days.", [V1]), ("Three days.", [V2])]),
        contradictions(("remote days", [V1, V2])),
        verdicts(True, True),
    ])
    result = answer_question(Q_REMOTE, store, llm, AS_OF, answer_id="a1", use_resolver=False)
    answer = result.answer
    assert answer.status == AnswerStatus.CONFLICT_UNRESOLVED
    assert "five days" in answer.answer.lower() and "three days" in answer.answer.lower()
    assert result.verification.winning_source_ids == [] and result.verification.stale_source_ids == []
    assert answer.conflicts_detected == 1


def test_without_the_resolver_and_without_a_contradiction_the_answer_is_resolved(store):
    llm = FakeLLM([synth([("Three days.", [V2])]), contradictions(), verdicts(True)])
    result = answer_question(Q_REMOTE, store, llm, AS_OF, use_resolver=False)
    assert result.answer.status == AnswerStatus.RESOLVED and result.answer.answer == "Three days."


def test_a_failed_critic_is_never_recorded_as_a_finished_check(store):
    result, _ = run(store, Q_REMOTE, [synth([("Three days.", [V2])]), LLMError("timeout")])
    assert result.verification.critic_ok is False and result.verification.stage == "critic"


def test_a_finished_critic_is_recorded_even_when_it_finds_nothing(store):
    result, _ = run(store, Q_REMOTE, [synth([("Three days.", [V2])]), contradictions(), verdicts(True)])
    assert result.verification.critic_ok is True


def test_nothing_is_in_scope_when_the_critic_never_ran(store):
    result, _ = run(store, "What is Acme Corp's policy on employee stock options?", [synth([], ["Not mentioned."])])
    assert result.verification.passages and not any(p.in_scope for p in result.verification.passages)
    assert result.verification.scope_document_ids == []


from __future__ import annotations

import json
import pathlib
from datetime import date, datetime
from typing import List, Optional, Tuple

import pytest

from truthguard_agent.ingestion import ingest_document
from truthguard_agent.resolver import ResolutionOutcome, resolve
from truthguard_agent.retriever import InMemoryPassageStore, retrieve
from truthguard_agent.schemas import (
    AnswerStatus,
    AuthorityLevel,
    Chunk,
    Contradiction,
    CriticResult,
    Document,
    DocumentIn,
    RetrievedPassage,
    make_chunk_id,
)

FIXTURES = pathlib.Path(__file__).parent.parent / "datasets" / "fixtures"
AS_OF = date(2026, 10, 20)  # after the latest effective date in the fixtures

RESOLVED = AnswerStatus.RESOLVED
UNRESOLVED = AnswerStatus.CONFLICT_UNRESOLVED
INSUFFICIENT = AnswerStatus.INSUFFICIENT_EVIDENCE


def _doc(
    document_id: str,
    authority: str = "official",
    effective: Optional[str] = None,
    supersedes: Optional[str] = None,
) -> Document:
    return Document(
        document_id=document_id,
        title=document_id,
        content="text of %s" % document_id,
        effective_date=date.fromisoformat(effective) if effective else None,
        authority_level=AuthorityLevel(authority),
        supersedes_document_id=supersedes,
    )


def _passage(doc: Document) -> RetrievedPassage:
    chunk = Chunk(
        chunk_id=make_chunk_id(doc.document_id, 0),
        document_id=doc.document_id,
        index=0,
        text=doc.content,
        start_offset=0,
        end_offset=len(doc.content),
    )
    return RetrievedPassage(chunk=chunk, document=doc)


def _critic(*conflicts: List[str], needs_resolution: Optional[bool] = None) -> CriticResult:
    return CriticResult(
        contradictions=[Contradiction(claim="claim", source_ids=ids) for ids in conflicts],
        needs_resolution=bool(conflicts) if needs_resolution is None else needs_resolution,
    )


def _run(docs: List[Document], critic: CriticResult, as_of: date = AS_OF) -> ResolutionOutcome:
    return resolve([_passage(d) for d in docs], critic, as_of)


# the 18 labeled cases (AGENT/datasets/fixtures/README.md). The critic does not exist yet, so the
# contradictions are what a correct critic reports for each case; these tests check the resolver given that.
CASES: List[Tuple[str, List[str], List[List[str]], AnswerStatus, List[str], List[str]]] = [
    # (case, documents, contradictions, status, winners, stale)
    ("C01", ["remote_policy_v1", "remote_policy_v2"], [["remote_policy_v1", "remote_policy_v2"]],
     RESOLVED, ["remote_policy_v2"], ["remote_policy_v1"]),
    ("C02", ["travel_budget_v1", "travel_budget_v2"], [["travel_budget_v1", "travel_budget_v2"]],
     RESOLVED, ["travel_budget_v2"], ["travel_budget_v1"]),
    ("C03", ["equipment_allowance_v1", "equipment_allowance_v2"],
     [["equipment_allowance_v1", "equipment_allowance_v2"]],
     RESOLVED, ["equipment_allowance_v2"], ["equipment_allowance_v1"]),
    ("C04", ["annual_leave_policy_v1", "annual_leave_policy_v2"],
     [["annual_leave_policy_v1", "annual_leave_policy_v2"]],
     RESOLVED, ["annual_leave_policy_v2"], ["annual_leave_policy_v1"]),
    ("C05", ["expense_receipt_deadline_finance", "expense_receipt_deadline_hr"],
     [["expense_receipt_deadline_finance", "expense_receipt_deadline_hr"]], UNRESOLVED, [], []),
    ("C06", ["remote_coworking_policy_a", "remote_coworking_policy_b"],
     [["remote_coworking_policy_a", "remote_coworking_policy_b"]], UNRESOLVED, [], []),
    ("C07", ["leave_carry_over_conflict_a", "leave_carry_over_conflict_b"],
     [["leave_carry_over_conflict_a", "leave_carry_over_conflict_b"]], UNRESOLVED, [], []),
    ("C08", [], [], INSUFFICIENT, [], []),
    ("C09", [], [], INSUFFICIENT, [], []),
    ("C10", [], [], INSUFFICIENT, [], []),
    ("C11", ["remote_work_managers", "remote_work_interns"], [], RESOLVED, [], []),
    ("C12", ["meal_allowance_domestic", "meal_allowance_international"], [], RESOLVED, [], []),
    ("C13", ["remote_policy_v3_draft", "remote_policy_v2"], [["remote_policy_v3_draft", "remote_policy_v2"]],
     RESOLVED, ["remote_policy_v2"], []),
    ("C14", ["expense_limit_increase_draft", "expense_policy_ops"],
     [["expense_limit_increase_draft", "expense_policy_ops"]], RESOLVED, ["expense_policy_ops"], []),
    ("C15", ["parental_leave_policy"], [], RESOLVED, [], []),
    ("C16", ["sick_leave_policy"], [], RESOLVED, [], []),
    ("C17", ["laptop_refresh_policy"], [], RESOLVED, [], []),
    ("C18", ["contractor_equipment_informal", "equipment_allowance_v1"], [], RESOLVED, [], []),
]


def _fixture_passages(document_ids: List[str]) -> List[RetrievedPassage]:
    passages = []
    for document_id in document_ids:
        raw = json.loads((FIXTURES / ("%s.json" % document_id)).read_text(encoding="utf-8"))
        doc, chunks = ingest_document(DocumentIn(**raw))
        passages.append(RetrievedPassage(chunk=chunks[0], document=doc))
    return passages


@pytest.mark.parametrize("case,documents,conflicts,status,winners,stale", CASES, ids=[c[0] for c in CASES])
def test_labeled_case(case, documents, conflicts, status, winners, stale):
    outcome = resolve(_fixture_passages(documents), _critic(*conflicts), AS_OF)
    assert outcome.status == status
    assert outcome.winning_source_ids == winners
    assert outcome.stale_source_ids == stale
    assert outcome.reason


def test_labeled_cases_cover_all_18():
    assert [c[0] for c in CASES] == ["C%02d" % n for n in range(1, 19)]


def test_as_of_is_required():
    with pytest.raises(TypeError):
        resolve([], CriticResult())  # type: ignore[call-arg]


# R1: explicit supersession

def test_r1_in_force_supersession_wins_and_names_documents_rule_and_date():
    v1 = _doc("remote_policy_v1", effective="2026-01-15")
    v2 = _doc("remote_policy_amendment_v2", effective="2026-10-01", supersedes="remote_policy_v1")
    outcome = _run([v1, v2], _critic(["remote_policy_v1", "remote_policy_amendment_v2"]))
    assert outcome.status == RESOLVED
    assert outcome.winning_source_ids == ["remote_policy_amendment_v2"]
    assert outcome.stale_source_ids == ["remote_policy_v1"]
    assert outcome.reason == (
        "remote_policy_amendment_v2 explicitly supersedes remote_policy_v1 (effective 2026-10-01); "
        "rule: explicit supersession."
    )


def test_r1_supersession_target_not_retrieved_makes_nothing_stale():
    v2 = _doc("v2", effective="2026-10-01", supersedes="v1")
    other = _doc("other", effective="2026-01-01")
    outcome = _run([v2, other], _critic(["v2", "other"]))
    assert outcome.stale_source_ids == []
    assert outcome.status == UNRESOLVED


def test_r1_supersession_target_missing_from_corpus_does_not_crash():
    outcome = _run([_doc("v2", effective="2026-10-01", supersedes="gone")], CriticResult())
    assert outcome.status == RESOLVED
    assert outcome.stale_source_ids == []


def test_r1_chain_with_b_in_force_makes_a_stale_and_c_wins():
    a = _doc("A", effective="2026-01-01")
    b = _doc("B", effective="2026-05-01", supersedes="A")
    c = _doc("C", effective="2026-09-01", supersedes="B")
    outcome = _run([a, b, c], _critic(["A", "B", "C"]))
    assert outcome.status == RESOLVED
    assert outcome.winning_source_ids == ["C"]
    assert outcome.stale_source_ids == ["A", "B"]


def test_r1_chain_with_b_undated_a_is_not_stale_even_if_c_is_in_force():
    # staleness is not inherited: C names B, never A
    a = _doc("A", effective="2026-01-01")
    b = _doc("B", effective=None, supersedes="A")
    c = _doc("C", effective="2026-09-01", supersedes="B")
    outcome = _run([a, b, c], CriticResult())
    assert outcome.stale_source_ids == ["B"]


def test_r1_chain_with_c_in_future_b_still_supersedes_a():
    a = _doc("A", effective="2026-01-01")
    b = _doc("B", effective="2026-05-01", supersedes="A")
    c = _doc("C", effective="2026-12-01", supersedes="B")
    outcome = _run([a, b, c], _critic(["A", "B"]))
    assert outcome.status == RESOLVED
    assert outcome.winning_source_ids == ["B"]
    assert outcome.stale_source_ids == ["A"]


# R1 and D2: who may supersede

@pytest.mark.parametrize("superseder_authority", ["draft", "informal"])
def test_d2_draft_and_informal_never_supersede(superseder_authority):
    old = _doc("old", authority="official", effective="2026-01-01")
    new = _doc("new", authority=superseder_authority, effective="2026-06-01", supersedes="old")
    outcome = _run([old, new], _critic(["old", "new"]))
    assert outcome.stale_source_ids == []
    # old is official and new is not, so R3 decides instead
    assert outcome.status == RESOLVED
    assert outcome.winning_source_ids == ["old"]
    assert "rule: authority" in outcome.reason


def test_d2_unknown_authority_cannot_supersede_an_official_document():
    old = _doc("old", authority="official", effective="2026-01-01")
    new = _doc("new", authority="unknown", effective="2026-06-01", supersedes="old")
    outcome = _run([old, new], _critic(["old", "new"]))
    assert outcome.status == UNRESOLVED
    assert outcome.stale_source_ids == []
    assert "cannot supersede" in outcome.reason


def test_d2_unknown_authority_can_supersede_a_non_official_document():
    old = _doc("old", authority="informal", effective="2026-01-01")
    new = _doc("new", authority="unknown", effective="2026-06-01", supersedes="old")
    outcome = _run([old, new], _critic(["old", "new"]))
    assert outcome.status == RESOLVED
    assert outcome.winning_source_ids == ["new"]


def test_d2_official_can_supersede_a_draft():
    old = _doc("old", authority="draft", effective="2026-01-01")
    new = _doc("new", authority="official", effective="2026-06-01", supersedes="old")
    assert _run([old, new], _critic(["old", "new"])).winning_source_ids == ["new"]


# R2: effective date

def test_r2_future_supersession_does_not_apply_and_reason_says_when_it_takes_effect():
    v1 = _doc("v1", effective="2026-01-15")
    v2 = _doc("v2", effective="2026-12-01", supersedes="v1")
    outcome = _run([v1, v2], _critic(["v1", "v2"]))
    assert outcome.status == UNRESOLVED
    assert outcome.winning_source_ids == []
    assert outcome.stale_source_ids == []
    assert "v2 names v1 but takes effect on 2026-12-01, after 2026-10-20" in outcome.reason


def test_r2_effective_date_equal_to_as_of_counts_as_arrived():
    v1 = _doc("v1", effective="2026-01-15")
    v2 = _doc("v2", effective="2026-10-20", supersedes="v1")
    assert _run([v1, v2], _critic(["v1", "v2"])).winning_source_ids == ["v2"]


def test_r2_one_day_before_effective_date_does_not_apply():
    v1 = _doc("v1", effective="2026-01-15")
    v2 = _doc("v2", effective="2026-10-20", supersedes="v1")
    assert _run([v1, v2], _critic(["v1", "v2"]), as_of=date(2026, 10, 19)).status == UNRESOLVED


def test_r2_same_documents_resolve_differently_for_different_as_of():
    v1 = _doc("v1", effective="2026-01-15")
    v2 = _doc("v2", effective="2026-06-01", supersedes="v1")
    critic = _critic(["v1", "v2"])
    assert _run([v1, v2], critic, as_of=date(2026, 5, 1)).status == UNRESOLVED
    assert _run([v1, v2], critic, as_of=date(2026, 7, 1)).status == RESOLVED


def test_d1_superseding_document_without_effective_date_does_not_apply():
    v1 = _doc("v1", effective="2026-01-15")
    v2 = _doc("v2", effective=None, supersedes="v1")
    outcome = _run([v1, v2], _critic(["v1", "v2"]))
    assert outcome.status == UNRESOLVED
    assert outcome.stale_source_ids == []
    assert "effective date is unknown" in outcome.reason


# R3: authority

def test_r3_official_beats_draft_even_when_the_draft_is_newer():
    official = _doc("travel_budget_policy", authority="official", effective="2026-01-01")
    draft = _doc("travel_budget_draft_2026", authority="draft", effective="2026-09-01")
    outcome = _run([official, draft], _critic(["travel_budget_policy", "travel_budget_draft_2026"]))
    assert outcome.status == RESOLVED
    assert outcome.winning_source_ids == ["travel_budget_policy"]
    assert outcome.stale_source_ids == []
    assert outcome.reason == "travel_budget_policy is official and travel_budget_draft_2026 is draft; rule: authority."


def test_r3_official_beats_informal():
    outcome = _run([_doc("a", "informal"), _doc("b", "official")], _critic(["a", "b"]))
    assert outcome.winning_source_ids == ["b"]


def test_r3_draft_and_informal_rank_equal():
    outcome = _run([_doc("a", "draft"), _doc("b", "informal")], _critic(["a", "b"]))
    assert outcome.status == UNRESOLVED


@pytest.mark.parametrize("other", ["official", "draft", "informal", "unknown"])
def test_r3_unknown_gives_no_ranking(other):
    outcome = _run([_doc("a", "unknown"), _doc("b", other)], _critic(["a", "b"]))
    assert outcome.status == UNRESOLVED
    assert outcome.winning_source_ids == []


def test_r3_three_sides_two_remain_when_one_is_unknown():
    docs = [_doc("x", "official"), _doc("y", "draft"), _doc("u", "unknown")]
    assert _run(docs, _critic(["x", "y", "u"])).status == UNRESOLVED


def test_r3_three_sides_lower_ones_lose_to_the_official_one():
    docs = [_doc("x", "official"), _doc("y", "draft"), _doc("z", "informal")]
    outcome = _run(docs, _critic(["x", "y", "z"]))
    assert outcome.status == RESOLVED
    assert outcome.winning_source_ids == ["x"]


# R4: newest does not automatically win

def test_r4_newer_official_without_supersession_does_not_win():
    old = _doc("expense_policy_a", effective="2026-02-01")
    new = _doc("expense_policy_b", effective="2026-08-01")
    outcome = _run([old, new], _critic(["expense_policy_a", "expense_policy_b"]))
    assert outcome.status == UNRESOLVED
    assert outcome.winning_source_ids == []


def test_r4_created_at_and_version_do_not_rank():
    older = _doc("a", effective="2026-01-01")
    newer = _doc("b", effective="2026-01-01")
    newer = newer.model_copy(update={"created_at": date(2026, 9, 1), "version": "9"})
    assert _run([older, newer], _critic(["a", "b"])).status == UNRESOLVED


# R5: equal authority, no supersession

def test_r5_two_official_documents_without_supersession_are_unresolved():
    outcome = _run([_doc("hr", effective="2026-03-01"), _doc("finance", effective="2026-03-01")],
                   _critic(["hr", "finance"]))
    assert outcome.status == UNRESOLVED
    assert outcome.winning_source_ids == []
    assert "hr and finance" in outcome.reason
    assert "rule: equal authority, no supersession" in outcome.reason


# R6: no relevant evidence

def test_r6_no_passages_is_insufficient_evidence_even_if_the_critic_flags_a_conflict():
    outcome = resolve([], _critic(["a", "b"]), AS_OF)
    assert outcome.status == INSUFFICIENT
    assert outcome.winning_source_ids == []
    assert "no relevant evidence" in outcome.reason


# R7: missing metadata

def test_r7_documents_without_dates_stay_unresolved_and_the_reason_says_so():
    outcome = _run([_doc("lease_note_a"), _doc("lease_note_b")], _critic(["lease_note_a", "lease_note_b"]))
    assert outcome.status == UNRESOLVED
    assert "Effective date unknown for lease_note_a, lease_note_b" in outcome.reason


def test_r7_draft_newer_than_official_policy_is_not_preferred():
    official = _doc("policy", "official", effective="2026-01-01")
    draft = _doc("policy_next", "draft", effective=None)
    outcome = _run([official, draft], _critic(["policy", "policy_next"]))
    assert outcome.winning_source_ids == ["policy"]


# Step 0 and Step 2

def test_step0_no_contradictions_is_resolved_and_still_lists_stale_documents():
    v1 = _doc("v1", effective="2026-01-01")
    v2 = _doc("v2", effective="2026-06-01", supersedes="v1")
    outcome = _run([v1, v2], CriticResult())
    assert outcome.status == RESOLVED
    assert outcome.stale_source_ids == ["v1"]
    assert outcome.winning_source_ids == []
    assert outcome.reason == "No contradiction was detected among the retrieved sources."


def test_d9_needs_resolution_without_contradictions_is_unresolved_not_resolved():
    outcome = _run([_doc("a")], CriticResult(needs_resolution=True))
    assert outcome.status == UNRESOLVED
    assert outcome.winning_source_ids == []
    assert "gave no contradiction" in outcome.reason


def test_contradictions_are_judged_even_when_needs_resolution_is_false():
    outcome = _run([_doc("a"), _doc("b")], _critic(["a", "b"], needs_resolution=False))
    assert outcome.status == UNRESOLVED


def test_step2_one_unresolved_conflict_makes_the_whole_answer_unresolved():
    docs = [
        _doc("v1", effective="2026-01-01"),
        _doc("v2", effective="2026-06-01", supersedes="v1"),
        _doc("hr", effective="2026-03-01"),
        _doc("finance", effective="2026-03-01"),
    ]
    outcome = _run(docs, _critic(["v1", "v2"], ["hr", "finance"]))
    assert outcome.status == UNRESOLVED
    assert outcome.winning_source_ids == ["v2"]
    assert outcome.stale_source_ids == ["v1"]
    assert "explicitly supersedes v1" in outcome.reason
    assert "hr and finance" in outcome.reason


def test_step2_all_conflicts_resolved_lists_every_winner():
    docs = [
        _doc("v1", effective="2026-01-01"),
        _doc("v2", effective="2026-06-01", supersedes="v1"),
        _doc("official_doc", "official"),
        _doc("draft_doc", "draft"),
    ]
    outcome = _run(docs, _critic(["v1", "v2"], ["official_doc", "draft_doc"]))
    assert outcome.status == RESOLVED
    assert outcome.winning_source_ids == ["v2", "official_doc"]


# Step 1: close each conflict under supersession (D11)

def test_closure_unlisted_superseder_joins_and_beats_the_informal_note():
    # the labeled C18 has no conflict; here the critic lists v1 and the informal note but not v2
    passages = _fixture_passages(["equipment_allowance_v1", "equipment_allowance_v2", "contractor_equipment_informal"])
    critic = _critic(["equipment_allowance_v1", "contractor_equipment_informal"])
    outcome = resolve(passages, critic, AS_OF)
    assert outcome.status == RESOLVED
    assert outcome.winning_source_ids == ["equipment_allowance_v2"]
    assert outcome.stale_source_ids == ["equipment_allowance_v1"]
    assert "equipment_allowance_v2 joins the conflict because it supersedes equipment_allowance_v1" in outcome.reason
    assert "rule: authority" in outcome.reason


def test_closure_without_it_the_informal_note_would_have_won():
    # same documents, but v2 is not retrieved: v1 and the informal note are then judged by R3 alone
    passages = _fixture_passages(["equipment_allowance_v1", "contractor_equipment_informal"])
    outcome = resolve(passages, _critic(["equipment_allowance_v1", "contractor_equipment_informal"]), AS_OF)
    assert outcome.winning_source_ids == ["equipment_allowance_v1"]


def test_closure_works_in_the_other_direction_the_superseded_document_joins():
    v1 = _doc("v1", effective="2026-01-01")
    v2 = _doc("v2", effective="2026-06-01", supersedes="v1")
    other = _doc("other", "informal")
    outcome = _run([v1, v2, other], _critic(["v2", "other"]))
    assert outcome.status == RESOLVED
    assert outcome.winning_source_ids == ["v2"]
    assert "v1 joins the conflict because v2 supersedes it" in outcome.reason


def test_closure_unlisted_superseder_of_one_side_is_compared_with_the_other_side():
    # n supersedes s1 but the critic did not list it: n now stands against s2, both official
    docs = [_doc("s1", effective="2026-01-01"), _doc("s2", effective="2026-01-01"),
            _doc("n", effective="2026-05-01", supersedes="s1")]
    outcome = _run(docs, _critic(["s1", "s2"]))
    assert outcome.status == UNRESOLVED
    assert outcome.winning_source_ids == []
    assert "n joins the conflict because it supersedes s1" in outcome.reason
    assert outcome.stale_source_ids == ["s1"]


def test_closure_follows_chains_and_resolves_in_favor_of_the_last_superseder():
    a = _doc("A", effective="2026-01-01")
    b = _doc("B", effective="2026-03-01", supersedes="A")
    c = _doc("C", effective="2026-05-01", supersedes="B")
    outcome = _run([a, b, c], _critic(["A", "B"]))
    assert outcome.status == RESOLVED
    assert outcome.winning_source_ids == ["C"]
    assert outcome.stale_source_ids == ["A", "B"]
    assert "C joins the conflict because it supersedes B" in outcome.reason
    assert "the conflict is moot and C holds the position" in outcome.reason


def test_closure_every_listed_side_superseded_by_different_documents_is_unresolved():
    docs = [_doc("s1", effective="2026-01-01"), _doc("s2", effective="2026-01-01"),
            _doc("n1", effective="2026-05-01", supersedes="s1"),
            _doc("n2", effective="2026-05-01", supersedes="s2")]
    outcome = _run(docs, _critic(["s1", "s2"]))
    assert outcome.status == UNRESOLVED
    assert outcome.winning_source_ids == []
    assert "n1 and n2 have no established precedence" in outcome.reason


def test_closure_ignores_supersessions_that_do_not_apply():
    # f takes effect in the future, so it does not join and v1 still outranks the informal note
    v1 = _doc("v1", effective="2026-01-01")
    future = _doc("f", effective="2026-12-01", supersedes="v1")
    informal = _doc("informal_note", "informal")
    outcome = _run([v1, future, informal], _critic(["v1", "informal_note"]))
    assert outcome.status == RESOLVED
    assert outcome.winning_source_ids == ["v1"]
    assert "joins" not in outcome.reason


def test_closure_does_not_pull_in_a_superseder_that_d2_forbids():
    old = _doc("old", authority="official", effective="2026-01-01")
    draft = _doc("draft_new", authority="draft", effective="2026-06-01", supersedes="old")
    other = _doc("other", authority="official", effective="2026-02-01")
    outcome = _run([old, draft, other], _critic(["old", "other"]))
    assert outcome.status == UNRESOLVED
    assert "draft_new" not in outcome.winning_source_ids
    assert "joins" not in outcome.reason


def test_closure_two_supersession_cycle_is_unresolved_not_a_crash():
    a = _doc("a", effective="2026-01-01", supersedes="b")
    b = _doc("b", effective="2026-01-01", supersedes="a")
    outcome = _run([a, b], _critic(["a", "b"]))
    assert outcome.status == UNRESOLVED
    assert outcome.winning_source_ids == []
    assert "supersession loop among a, b" in outcome.reason


def test_contradiction_citing_a_source_that_was_not_retrieved_is_unresolved():
    outcome = _run([_doc("a")], _critic(["a", "ghost"]))
    assert outcome.status == UNRESOLVED
    assert "ghost" in outcome.reason


def test_contradiction_with_one_source_is_unresolved():
    assert _run([_doc("a")], _critic(["a"])).status == UNRESOLVED


def test_duplicate_source_ids_and_repeated_passages_are_handled():
    doc = _doc("a")
    outcome = resolve([_passage(doc), _passage(doc)], _critic(["a", "a"]), AS_OF)
    assert outcome.status == UNRESOLVED


def test_resolved_always_has_a_reason():
    for _case, documents, conflicts, _status, _winners, _stale in CASES:
        outcome = resolve(_fixture_passages(documents), _critic(*conflicts), AS_OF)
        assert outcome.reason.strip()


def test_outcome_requires_a_reason():
    with pytest.raises(ValueError):
        ResolutionOutcome(status=RESOLVED, reason="")


def test_resolve_does_not_modify_its_inputs():
    docs = [_doc("v1", effective="2026-01-01"), _doc("v2", effective="2026-06-01", supersedes="v1")]
    passages = [_passage(d) for d in docs]
    critic = _critic(["v1", "v2"])
    before = (critic.model_dump(), [p.model_dump() for p in passages])
    resolve(passages, critic, AS_OF)
    assert (critic.model_dump(), [p.model_dump() for p in passages]) == before


def test_as_of_must_be_a_date_not_a_datetime():
    with pytest.raises(TypeError, match="date, not a datetime"):
        resolve([_passage(_doc("a"))], CriticResult(), datetime(2026, 10, 20, 12, 0))  # type: ignore[arg-type]


def test_one_pair_reported_for_several_claims_gives_one_sentence_not_repeats():
    v1 = _doc("v1", effective="2026-01-01")
    v2 = _doc("v2", effective="2026-06-01", supersedes="v1")
    outcome = _run([v1, v2], _critic(["v1", "v2"], ["v2", "v1"], ["v1", "v2"]))
    assert outcome.status == RESOLVED
    assert outcome.winning_source_ids == ["v2"]
    assert outcome.reason.count("explicitly supersedes v1") == 1


def test_resolution_works_on_real_retriever_output_with_the_critic_listing_only_one_side():
    # retrieve() adds the superseding document (D7); the resolver's closure then lets it join (D11)
    docs = [ingest_document(DocumentIn(**json.loads((FIXTURES / ("%s.json" % name)).read_text(encoding="utf-8"))))[0]
            for name in ("remote_policy_v1", "remote_policy_v2", "remote_policy_v3_draft")]
    passages = retrieve("How many days per week can employees work remotely?", InMemoryPassageStore(docs))
    outcome = resolve(passages, _critic(["remote_policy_v1", "remote_policy_v3_draft"]), AS_OF)
    assert outcome.status == RESOLVED
    assert outcome.winning_source_ids == ["remote_policy_v2"]

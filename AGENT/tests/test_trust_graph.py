"""Trust report and evidence graph, built from real pipeline runs on the T01 fixtures (scripted model replies)."""
import json
import pathlib
from datetime import date

import pytest

from truthguard_agent.evidence_graph import build_evidence_graph
from truthguard_agent.llm import FakeLLM, LLMError
from truthguard_agent.orchestrator import answer_question
from truthguard_agent.retriever import InMemoryPassageStore
from truthguard_agent.schemas import Document
from truthguard_agent.trust_report import ATTENTION, OK, PROBLEM, UNKNOWN, build_trust_report

FIXTURES = pathlib.Path(__file__).resolve().parents[1] / "datasets" / "fixtures"
V1, V2 = "remote_policy_v1::chunk_000", "remote_policy_v2::chunk_000"
FIN, HR = "expense_receipt_deadline_finance::chunk_000", "expense_receipt_deadline_hr::chunk_000"


@pytest.fixture(scope="module")
def store():
    return InMemoryPassageStore([Document(**json.loads(p.read_text(encoding="utf-8"))) for p in sorted(FIXTURES.glob("*.json"))])


def synth(claims, caveats=None):
    return json.dumps({"claims": [{"text": t, "citation_chunk_ids": c} for t, c in claims], "caveats": caveats or []})


def contradictions(*items):
    return json.dumps({"contradictions": [{"claim": c, "chunk_ids": ids, "severity": "high", "bears_on_question": True} for c, ids in items]})


def verdicts(*supported):
    return json.dumps({"verdicts": [{"claim_index": i, "supported": s, "reason": "r"} for i, s in enumerate(supported)]})


def run(store, question, replies):
    return answer_question(question, store, FakeLLM(replies), date(2026, 10, 20), answer_id="a1")


@pytest.fixture()
def superseded(store):
    return run(store, "How many days per week can employees work remotely?", [
        synth([("Five days.", [V1]), ("Three days.", [V2])]), contradictions(("remote days", [V1, V2])), verdicts(True, True)])


@pytest.fixture()
def unresolved(store):
    return run(store, "How long do employees have to submit expense receipts?", [
        synth([("14 days.", [FIN]), ("30 days.", [HR])]), contradictions(("receipt deadline", [FIN, HR])), verdicts(True, True)])


@pytest.fixture()
def insufficient(store):
    return run(store, "What is Acme Corp's policy on employee stock options?", [synth([], ["Not mentioned."])])


def dims(report):
    return {d.key: d for d in report.dimensions}


# ---- trust report ----------------------------------------------------------------------------------------

def test_a_resolved_superseded_answer_is_clean_on_every_dimension(superseded):
    report = build_trust_report(superseded)
    d = dims(report)
    assert [x.key for x in report.dimensions] == ["evidence_coverage", "citation_support", "conflicts", "freshness", "provenance", "verification"]
    assert (d["evidence_coverage"].numerator, d["evidence_coverage"].denominator) == (2, 2)
    assert (d["citation_support"].numerator, d["citation_support"].denominator) == (2, 2)
    assert (d["conflicts"].numerator, d["conflicts"].denominator) == (1, 1) and d["conflicts"].level == OK
    assert (d["freshness"].numerator, d["freshness"].denominator) == (1, 1) and d["freshness"].level == OK
    assert d["provenance"].level == OK and d["verification"].level == OK
    assert report.warnings == []


def test_there_is_no_single_score(superseded):
    report = build_trust_report(superseded)
    assert not hasattr(report, "score") and not hasattr(report, "overall")
    assert all(d.value is None or 0 <= d.value <= 1 for d in report.dimensions)


def test_high_coverage_cannot_hide_an_unresolved_conflict(unresolved):
    report = build_trust_report(unresolved)
    d = dims(report)
    assert d["evidence_coverage"].value == 1.0 and d["citation_support"].value == 1.0  # looks perfect...
    assert d["conflicts"].level == PROBLEM and (d["conflicts"].numerator, d["conflicts"].denominator) == (0, 1)
    assert d["verification"].level == ATTENTION
    assert any("disagree" in w and "do not change that" in w for w in report.warnings)  # ...and says so anyway


def test_an_answer_with_no_claims_reports_unknown_not_fine(insufficient):
    report = build_trust_report(insufficient)
    d = dims(report)
    for key in ("evidence_coverage", "citation_support", "conflicts", "freshness", "provenance"):
        assert d[key].level == UNKNOWN and d[key].value is None, key
    assert d["verification"].level == ATTENTION
    assert any("do not answer" in w for w in report.warnings)


def test_a_failed_check_reports_unknown_and_a_problem(store):
    result = run(store, "How many days per week can employees work remotely?", [synth([("Three days.", [V2])]), LLMError("timeout")])
    report = build_trust_report(result)
    d = dims(report)
    assert d["citation_support"].level == UNKNOWN and d["conflicts"].level == UNKNOWN
    assert d["verification"].level == PROBLEM and "timeout" in d["verification"].detail
    assert any("did not finish" in w for w in report.warnings)


def test_a_claim_that_its_passage_does_not_back_is_counted_and_warned_about(store):
    result = run(store, "How many days per week can employees work remotely?", [
        synth([("Three days.", [V2]), ("Free lunch.", [V2])]), contradictions(), verdicts(True, False)])
    report = build_trust_report(result)
    d = dims(report)
    assert (d["citation_support"].numerator, d["citation_support"].denominator) == (1, 2) and d["citation_support"].level == ATTENTION
    assert any("1 drafted claim(s) were not backed" in w for w in report.warnings)


def test_an_unknown_effective_date_is_reported_as_unknown(superseded):
    for p in superseded.verification.passages:
        if p.document_id == "remote_policy_v2":
            p.effective_date = None
    d = dims(build_trust_report(superseded))
    assert d["freshness"].level == ATTENTION and (d["freshness"].numerator, d["freshness"].denominator) == (0, 1)
    assert "unknown" in d["freshness"].detail


def test_citing_a_superseded_document_is_a_problem(superseded):
    superseded.verification.stale_source_ids.append("remote_policy_v2")
    d = dims(build_trust_report(superseded))
    assert d["freshness"].level == PROBLEM and "remote_policy_v2" in d["freshness"].detail


def test_a_citation_that_cannot_be_traced_is_a_provenance_problem(superseded):
    superseded.verification.passages = [p for p in superseded.verification.passages if p.chunk_id != V2]
    d = dims(build_trust_report(superseded))
    assert d["provenance"].level == PROBLEM and d["provenance"].numerator < d["provenance"].denominator


def test_the_report_round_trips_through_json(superseded):
    report = build_trust_report(superseded)
    assert type(report).model_validate_json(report.model_dump_json()) == report


# ---- evidence graph --------------------------------------------------------------------------------------

def edges(graph, relation):
    return {(e.source, e.target) for e in graph.edges if e.relation == relation}


def test_the_graph_of_a_superseded_answer(superseded):
    graph = build_evidence_graph(superseded)
    nodes = {n.id: n for n in graph.nodes}
    assert set(nodes) == {"a1::c1", "a1::c2", "remote_policy_v1", "remote_policy_v2"}
    assert nodes["remote_policy_v2"].role == "winner" and nodes["remote_policy_v1"].role == "superseded"
    assert nodes["a1::c1"].role == "superseded" and nodes["a1::c2"].role == "current"
    assert nodes["remote_policy_v2"].chunk_ids == [V2] and nodes["remote_policy_v2"].effective_date == "2026-04-15"
    assert edges(graph, "supports") == {("a1::c1", "remote_policy_v1"), ("a1::c2", "remote_policy_v2")} or \
        ("a1::c2", "remote_policy_v2") in edges(graph, "supports")
    assert ("a1::c2", "remote_policy_v1") in edges(graph, "contradicts")
    (supersession,) = [e for e in graph.edges if e.relation == "supersedes"]
    assert (supersession.source, supersession.target, supersession.in_force) == ("remote_policy_v2", "remote_policy_v1", True)
    (conflict,) = [e for e in graph.edges if e.relation == "conflicts"]
    assert conflict.settled is True and conflict.label == "remote days"


def test_the_graph_of_an_unresolved_conflict_has_no_supersession_and_an_open_conflict(unresolved):
    graph = build_evidence_graph(unresolved)
    assert {n.id for n in graph.nodes if n.kind == "document"} == {"expense_receipt_deadline_finance", "expense_receipt_deadline_hr"}
    assert not [e for e in graph.edges if e.relation == "supersedes"]
    (conflict,) = [e for e in graph.edges if e.relation == "conflicts"]
    assert conflict.settled is False
    assert all(n.role == "" for n in graph.nodes if n.kind == "document")  # nobody won


def test_an_answer_without_claims_has_an_empty_graph(insufficient):
    graph = build_evidence_graph(insufficient)
    assert graph.nodes == [] and graph.edges == []


def test_unrelated_retrieved_documents_are_not_in_the_graph(superseded):
    retrieved = {p.document_id for p in superseded.verification.passages}
    assert "annual_leave_policy_v1" in retrieved
    assert "annual_leave_policy_v1" not in {n.id for n in build_evidence_graph(superseded).nodes}


def test_a_supersession_that_is_not_yet_in_force_is_drawn_but_marked(store):
    result = answer_question("How many days per week can employees work remotely?", store, FakeLLM([
        synth([("Five days.", [V1]), ("Three days.", [V2])]), contradictions(("remote days", [V1, V2])), verdicts(True, True)]),
        date(2026, 1, 20), answer_id="a1")
    (supersession,) = [e for e in build_evidence_graph(result).edges if e.relation == "supersedes"]
    assert supersession.in_force is False


def test_the_graph_round_trips_through_json(superseded):
    graph = build_evidence_graph(superseded)
    assert type(graph).model_validate_json(graph.model_dump_json()) == graph

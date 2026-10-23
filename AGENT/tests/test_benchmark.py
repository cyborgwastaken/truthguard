"""The benchmark: dataset integrity, metrics on hand-built results, and the runner on the real fixtures."""
import json
import pathlib
import re
from datetime import date

import pytest

from truthguard_agent.evaluation.cases import BenchmarkCase, load_cases
from truthguard_agent.evaluation.metrics import (
    CaseResult,
    answer_contains_all,
    answer_contains_any,
    compute_metrics,
    consistency,
)
from truthguard_agent.evaluation.runner import load_run, run_benchmark, run_case, save_run
from truthguard_agent.llm import FakeLLM, LLMError
from truthguard_agent.retriever import InMemoryPassageStore, retrieve
from truthguard_agent.schemas import AnswerStatus, Document

FIXTURES = pathlib.Path(__file__).resolve().parents[1] / "datasets" / "fixtures"
R, C, I, F = (AnswerStatus.RESOLVED, AnswerStatus.CONFLICT_UNRESOLVED,
              AnswerStatus.INSUFFICIENT_EVIDENCE, AnswerStatus.VERIFICATION_FAILED)


# ---- dataset ---------------------------------------------------------------------------------------------

def test_the_dataset_has_the_18_labeled_cases():
    cases = load_cases()
    assert [c.case_id for c in cases] == ["C%02d" % n for n in range(1, 19)]
    counts = {s: sum(c.expected_status == s for c in cases) for s in (R, C, I)}
    assert counts == {R: 12, C: 3, I: 3}


def test_the_dataset_agrees_with_the_fixtures_label_table():
    """Question and expected status of every case must match fixtures/README.md, so the two cannot drift."""
    table = {}
    for line in (FIXTURES / "README.md").read_text(encoding="utf-8").splitlines():
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) >= 5 and re.fullmatch(r"C\d\d", cells[0]):
            table[cells[0]] = (cells[1], re.findall(r"`([^`]+)`", cells[3])[0], re.findall(r"`([^`]+)`", cells[2]))
    assert len(table) == 18
    for case in load_cases():
        question, status, docs = table[case.case_id]
        assert case.question == question, case.case_id
        assert case.expected_status.value == status, case.case_id
        assert set(docs) <= set(case.relevant_document_ids), case.case_id


def test_every_document_the_dataset_names_exists_and_winners_and_stale_are_relevant():
    existing = {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in FIXTURES.glob("*.json")}
    for case in load_cases():
        assert set(case.relevant_document_ids) <= set(existing), case.case_id
        assert set(case.expected_winner_document_ids) <= set(case.relevant_document_ids), case.case_id
        assert set(case.expected_stale_document_ids) <= set(case.relevant_document_ids), case.case_id
        for group in case.expected_answer_contains:
            assert group and all(option.strip() for option in group), case.case_id
        for stale in case.expected_stale_document_ids:
            superseder = [d for d in existing.values() if d["supersedes_document_id"] == stale]
            assert superseder, "%s: nothing supersedes %s" % (case.case_id, stale)


def test_as_of_is_after_every_effective_date_so_the_amendments_are_in_force():
    latest = max(date.fromisoformat(json.loads(p.read_text())["effective_date"])
                 for p in FIXTURES.glob("*.json") if json.loads(p.read_text())["effective_date"])
    assert all(c.as_of >= latest for c in load_cases())


# ---- answer checks ---------------------------------------------------------------------------------------

def test_answer_checks_are_case_insensitive_substrings_and_every_group_must_match():
    assert answer_contains_all("Receipts: 14 days (Finance) or 30 days (HR).", [["14"], ["30"]])
    assert not answer_contains_all("14 days.", [["14"], ["30"]])
    assert answer_contains_all("THREE days", [["three", "3"]])
    assert answer_contains_all("anything", [])
    assert answer_contains_any("Five Days per week", ["five days"])
    assert not answer_contains_any("three days", ["five days"])


# ---- metrics on hand-built results -----------------------------------------------------------------------

def case(cid, status, **kw):
    return BenchmarkCase(case_id=cid, case_type="t", question="q?", as_of=date(2026, 10, 20), expected_status=status, **kw)


def result(cid, status, config="full", **kw):
    return CaseResult(case_id=cid, config=config, status=status, **kw)


CASES = [
    case("A", R, relevant_document_ids=["new", "old"], expected_winner_document_ids=["new"],
         expected_stale_document_ids=["old"], expected_answer_contains=[["three"]], forbidden_answer_contains=["five"]),
    case("B", C, relevant_document_ids=["x", "y"], expected_answer_contains=[["14"], ["30"]]),
    case("C", I),
    case("D", R, relevant_document_ids=["solo"]),
]


def test_metrics_for_a_good_full_run_with_their_numerators_and_denominators():
    results = [
        result("A", R, answer="Three days.", winner_document_ids=["new"], stale_document_ids=["old"],
               retrieved_document_ids=["new", "old"], citation_document_ids=["new"], claims_total=2, claims_supported=2, latency_ms=100),
        result("B", C, answer="14 days or 30 days.", retrieved_document_ids=["x"], citation_document_ids=["x", "y"], latency_ms=200),
        result("C", I, latency_ms=300),
        result("D", R, retrieved_document_ids=["solo"], citation_document_ids=["solo"], latency_ms=400),
    ]
    m = compute_metrics("full", CASES, results)
    assert (m["status_accuracy"].numerator, m["status_accuracy"].denominator) == (4, 4)
    assert (m["abstention_recall"].numerator, m["abstention_recall"].denominator) == (1, 1)
    assert (m["abstention_precision"].numerator, m["abstention_precision"].denominator) == (1, 1)
    assert (m["conflict_recall"].numerator, m["conflict_recall"].denominator) == (1, 1)
    assert (m["false_conflict_rate"].numerator, m["false_conflict_rate"].denominator) == (0, 2)
    assert (m["key_fact_accuracy"].numerator, m["key_fact_accuracy"].denominator) == (2, 2)
    assert (m["outdated_value_rate"].numerator, m["outdated_value_rate"].denominator) == (0, 1)
    assert (m["winner_accuracy"].numerator, m["winner_accuracy"].denominator) == (1, 1)
    assert (m["stale_detection"].numerator, m["stale_detection"].denominator) == (1, 1)
    assert (m["retrieval_recall"].numerator, m["retrieval_recall"].denominator) == (4, 5)  # found new, old, x, solo of the 5 relevant documents
    assert (m["citation_precision"].numerator, m["citation_precision"].denominator) == (4, 4)
    assert (m["claim_support_rate"].numerator, m["claim_support_rate"].denominator) == (2, 2)
    assert m["latency_mean_ms"].value == 250 and m["latency_p95_ms"].value == 400


def test_a_failed_check_is_never_a_correct_answer_or_a_correct_abstention():
    results = [result("A", R, answer="Three days."), result("B", C), result("C", F, failure_reason="503"), result("D", R)]
    m = compute_metrics("full", CASES, results)
    assert (m["status_accuracy"].numerator, m["status_accuracy"].denominator) == (3, 4)
    assert (m["verification_failed_rate"].numerator, m["verification_failed_rate"].denominator) == (1, 4)
    assert m["abstention_recall"].value == 0  # the failure on the no-evidence case is not an abstention
    assert m["abstention_precision"].denominator == 0 and m["abstention_precision"].value is None


def test_the_baseline_reports_what_it_cannot_do_as_not_applicable_never_as_zero():
    results = [result("A", R, config="baseline", answer="Five days.", claims_total=1)]
    m = compute_metrics("baseline", CASES, results)
    for key in ("winner_accuracy", "stale_detection", "claim_support_rate"):
        assert m[key].applies is False and m[key].value is None and m[key].note
    assert m["outdated_value_rate"].value == 1  # it states the superseded value
    assert compute_metrics("rag_critic", CASES, results)["stale_detection"].applies is True
    assert compute_metrics("rag_critic", CASES, results)["winner_accuracy"].applies is False


def test_ratios_with_nothing_to_measure_are_none_not_zero_or_an_error():
    m = compute_metrics("full", CASES, [])
    assert m["status_accuracy"].value is None and m["latency_mean_ms"].value is None and m["latency_p95_ms"].value is None


def test_p95_latency_uses_the_nearest_rank():
    results = [result("A", R, latency_ms=ms) for ms in range(100, 2100, 100)]  # 20 results: 100..2000
    assert compute_metrics("full", CASES, results)["latency_p95_ms"].value == 1900


def test_consistency_is_the_share_of_repeats_that_agree_with_the_most_common_status():
    results = [result("A", R), result("A", R), result("A", C), result("B", C), result("B", C)]
    assert consistency(results) == {"A": pytest.approx(2 / 3), "B": 1.0}


# ---- the runner on the real fixtures ---------------------------------------------------------------------

@pytest.fixture(scope="module")
def store():
    return InMemoryPassageStore([Document(**json.loads(p.read_text(encoding="utf-8"))) for p in sorted(FIXTURES.glob("*.json"))])


@pytest.fixture(scope="module")
def cases():
    return {c.case_id: c for c in load_cases()}


V1, V2 = "remote_policy_v1::chunk_000", "remote_policy_v2::chunk_000"


def synth(claims, caveats=None):
    return json.dumps({"claims": [{"text": t, "citation_chunk_ids": c} for t, c in claims], "caveats": caveats or []})


def contradictions(*items):
    return json.dumps({"contradictions": [{"claim": c, "chunk_ids": ids, "severity": "high", "bears_on_question": True} for c, ids in items]})


def verdicts(*supported):
    return json.dumps({"verdicts": [{"claim_index": i, "supported": s, "reason": "r"} for i, s in enumerate(supported)]})


def pipeline_replies():
    return [synth([("Five days.", [V1]), ("Three days.", [V2])]), contradictions(("remote days", [V1, V2])), verdicts(True, True)]


SCRIPT = {
    ("baseline", "C01"): [synth([("Five days per week.", [V1])])],
    ("rag_critic", "C01"): pipeline_replies(),
    ("full", "C01"): pipeline_replies(),
    ("baseline", "C08"): [synth([], ["Nothing about stock options."])],
    ("rag_critic", "C08"): [synth([], ["Nothing about stock options."])],
    ("full", "C08"): [synth([], ["Nothing about stock options."])],
}


def factory(config, case_id, repeat):
    return FakeLLM(list(SCRIPT[(config, case_id)]))


def test_the_baseline_search_finds_the_old_policy_without_the_expansion(store, cases):
    """So the scripted baseline reply that cites it is valid, and the baseline never sees the amendment."""
    found = {p.chunk.chunk_id for p in retrieve(cases["C01"].question, store, expand_related=False)}
    assert V1 in found


def test_three_setups_on_two_cases_give_the_expected_results_and_metrics(store, cases):
    run = run_benchmark([cases["C01"], cases["C08"]], store, factory, retries=0)
    by = {(r.config, r.case_id): r for r in run.results}
    assert len(run.results) == 6

    assert by[("baseline", "C01")].status == R and "five days" in by[("baseline", "C01")].answer.lower()
    assert by[("rag_critic", "C01")].status == C and by[("rag_critic", "C01")].winner_document_ids == []
    full = by[("full", "C01")]
    assert full.status == R and "three days" in full.answer.lower()
    assert full.winner_document_ids == ["remote_policy_v2"] and "remote_policy_v1" in full.stale_document_ids
    assert full.citation_document_ids == ["remote_policy_v2"]
    assert full.claims_total == 2 and full.claims_supported == 2 and full.latency_ms >= 0
    for config in ("baseline", "rag_critic", "full"):
        assert by[(config, "C08")].status == I

    assert run.metrics["baseline"]["outdated_value_rate"].value == 1.0   # the plain baseline states the old value
    assert run.metrics["full"]["outdated_value_rate"].value == 0.0
    assert run.metrics["full"]["winner_accuracy"].value == 1.0
    assert run.metrics["baseline"]["winner_accuracy"].applies is False
    # The baseline's status is "resolved" for C01, which is what is expected: status alone cannot show its flaw.
    # The wrong fact can: it answered with the superseded value and left out the current one.
    assert run.metrics["baseline"]["status_accuracy"].value == 1.0
    assert run.metrics["baseline"]["key_fact_accuracy"].value == 0.0
    assert run.metrics["full"]["key_fact_accuracy"].value == 1.0
    assert run.metrics["full"]["status_accuracy"].value == 1.0
    assert run.metrics["rag_critic"]["status_accuracy"].value == 0.5  # C01: it shows a conflict but decides nothing
    assert run.dataset_version == "v1" and run.settings["repeats"] == 1


def test_a_rate_limit_failure_is_retried_and_other_failures_are_not(store, cases):
    llm = FakeLLM([LLMError("Groq API error 429: rate limit"), synth([], ["Nothing."])])
    assert run_case("full", cases["C08"], store, llm).status == F  # one case alone is not retried; the run loop does it

    def retrying(config, case_id, repeat):
        return FakeLLM([LLMError("Groq API error 429: rate limit"), synth([], ["Nothing."])])

    run = run_benchmark([cases["C08"]], store, retrying, configs=["full"], retries=2, backoff_s=0)
    assert run.results[0].status == I

    flaky = FakeLLM([LLMError("Groq API error 503")])
    run = run_benchmark([cases["C08"]], store, lambda *a: flaky, configs=["full"], retries=2, backoff_s=0)
    assert run.results[0].status == F and len(flaky.calls) == 1


def test_a_crash_is_recorded_as_a_failed_check_and_the_run_goes_on(cases):
    class Broken:
        def search(self, query, limit):
            raise RuntimeError("database is down")

        def related_passages(self, ids):
            return []

    run = run_benchmark([cases["C01"], cases["C08"]], Broken(), lambda *a: FakeLLM([]), configs=["full"], retries=0)
    assert [r.status for r in run.results] == [F, F]
    assert all(r.failure_reason.startswith("exception: RuntimeError") for r in run.results)


def test_repeats_and_progress(store, cases):
    seen = []
    run = run_benchmark([cases["C08"]], store, lambda *a: FakeLLM([synth([], ["n"])]), configs=["full"], repeats=3, progress=seen.append)
    assert [r.repeat for r in run.results] == [1, 2, 3] and len(seen) == 3
    assert run.consistency["full"] == {"C08": 1.0}


def test_a_run_round_trips_through_its_json_file_and_latest_is_updated(store, cases, tmp_path):
    run = run_benchmark([cases["C08"]], store, lambda *a: FakeLLM([synth([], ["n"])]), configs=["full"])
    path = save_run(run, tmp_path)
    assert path.name == "run-%s.json" % run.run_id
    assert load_run(path) == run
    assert load_run(tmp_path / "latest.json") == run

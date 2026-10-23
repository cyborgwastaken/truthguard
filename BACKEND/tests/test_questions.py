"""POST /questions and GET /answers on the real database with the real T01 fixtures and scripted model replies."""
import json
import pathlib

import pytest
from sqlalchemy import func, select
from truthguard_agent.llm import FakeLLM, LLMError

from app.api.questions import get_llm
from app.config import settings
from app.db.models import AnswerCitationRow, AnswerRow, ClaimRow, EvidenceLinkRow
from app.main import app

FIXTURES = pathlib.Path(__file__).resolve().parents[2] / "AGENT" / "datasets" / "fixtures"
V1, V2 = "remote_policy_v1::chunk_000", "remote_policy_v2::chunk_000"
Q_REMOTE = "How many days per week can employees work remotely?"


def synth(claims, caveats=None):
    return json.dumps({"claims": [{"text": t, "citation_chunk_ids": c} for t, c in claims], "caveats": caveats or []})


def contradictions(*items):
    return json.dumps(
        {"contradictions": [{"claim": c, "chunk_ids": ids, "severity": "high", "bears_on_question": True} for c, ids in items]}
    )


def verdicts(*supported):
    return json.dumps({"verdicts": [{"claim_index": i, "supported": s, "reason": "r"} for i, s in enumerate(supported)]})


@pytest.fixture()
def loaded(client):
    for path in sorted(FIXTURES.glob("*.json")):
        assert client.post("/documents", json=json.loads(path.read_text(encoding="utf-8"))).status_code == 201
    return client


def ask(client, replies, question=Q_REMOTE, **extra):
    llm = FakeLLM(replies)
    app.dependency_overrides[get_llm] = lambda: llm
    response = client.post("/questions", json={"question": question, **extra})
    return response, llm


def superseded_replies():
    return [
        synth([("Employees may work remotely five days per week.", [V1]), ("Employees may work remotely three days per week.", [V2])]),
        contradictions(("remote days per week", [V1, V2])),
        verdicts(True, True),
    ]


def test_superseded_policy_is_resolved_and_the_whole_record_is_returned(loaded):
    response, _ = ask(loaded, superseded_replies())
    assert response.status_code == 201
    body = response.json()
    answer, check = body["answer"], body["verification"]
    assert answer["status"] == "resolved" and "three days" in answer["answer"] and "five days" not in answer["answer"]
    assert [c["chunk_id"] for c in answer["citations"]] == [V2]
    assert check["winning_source_ids"] == ["remote_policy_v2"] and check["stale_source_ids"] == ["remote_policy_v1"]
    assert check["conflicts"][0]["winner_source_ids"] == ["remote_policy_v2"]
    assert {p["chunk_id"] for p in check["passages"] if p["in_scope"]} >= {V1, V2}
    assert {r for r in check["claim_roles"].values()} == {"current", "superseded"}
    assert body["llm_mode"] == "live" and check["as_of"]


def test_answer_is_stored_and_read_back_exactly(loaded, db):
    posted = ask(loaded, superseded_replies())[0].json()
    answer_id = posted["answer"]["answer_id"]
    assert loaded.get("/answers/%s" % answer_id).json() == posted

    row = db.get(AnswerRow, answer_id)
    assert row.status == "resolved" and row.as_of is not None and row.details["answer"]["answer_id"] == answer_id
    assert db.scalar(select(func.count()).select_from(ClaimRow).where(ClaimRow.answer_id == answer_id)) == 2
    assert db.scalar(select(func.count()).select_from(AnswerCitationRow).where(AnswerCitationRow.answer_id == answer_id)) == 1
    relations = {l.relation for l in db.scalars(select(EvidenceLinkRow))}
    assert {"supports", "contradicts", "context"} <= relations


def test_unresolved_conflict_returns_both_positions(loaded):
    fin, hr = "expense_receipt_deadline_finance::chunk_000", "expense_receipt_deadline_hr::chunk_000"
    body = ask(loaded, [
        synth([("Finance requires receipts within 14 days.", [fin]), ("HR allows 30 days.", [hr])]),
        contradictions(("receipt deadline", [fin, hr])),
        verdicts(True, True),
    ], question="How long do employees have to submit expense receipts?")[0].json()
    assert body["answer"]["status"] == "conflict_unresolved"
    assert "14 days" in body["answer"]["answer"] and "30 days" in body["answer"]["answer"]
    assert body["verification"]["conflicts"][0]["status"] == "conflict_unresolved"
    assert body["verification"]["winning_source_ids"] == []


def test_insufficient_evidence_is_a_normal_answer(loaded):
    body = ask(loaded, [synth([], ["The passages do not mention stock options."])],
               question="What is Acme Corp's policy on employee stock options?")[0].json()
    assert body["answer"]["status"] == "insufficient_evidence" and body["answer"]["answer"] == ""
    assert "stock options" in body["answer"]["resolution_reason"]


def test_a_failed_check_is_a_stored_201_answer_not_a_server_error(loaded):
    response, _ = ask(loaded, [LLMError("Groq API error 503")])
    assert response.status_code == 201
    body = response.json()
    assert body["answer"]["status"] == "verification_failed" and "503" in body["answer"]["resolution_reason"]
    assert loaded.get("/answers/%s" % body["answer"]["answer_id"]).json() == body


def test_as_of_is_passed_to_the_pipeline_and_stored(loaded):
    body = ask(loaded, superseded_replies(), as_of="2026-01-20")[0].json()
    assert body["verification"]["as_of"] == "2026-01-20"
    assert body["answer"]["status"] == "conflict_unresolved"  # the amendment is not in force yet


def test_recent_answers_are_listed_newest_first(loaded):
    first = ask(loaded, [synth([], ["Nothing."])], question="first question here")[0].json()["answer"]["answer_id"]
    second = ask(loaded, [synth([], ["Nothing."])], question="second question here")[0].json()["answer"]["answer_id"]
    listed = loaded.get("/answers?limit=5").json()
    assert [a["answer_id"] for a in listed][:2] == [second, first]
    assert listed[0]["status"] == "insufficient_evidence" and listed[0]["question"] == "second question here"


@pytest.mark.parametrize("payload", [{"question": "hi"}, {"question": "   "}, {"question": Q_REMOTE, "as_of": "not-a-date"}, {}])
def test_invalid_questions_are_422(loaded, payload):
    app.dependency_overrides[get_llm] = lambda: FakeLLM([])
    assert loaded.post("/questions", json=payload).status_code == 422


def test_unknown_answer_is_404(client):
    assert client.get("/answers/nope").status_code == 404


def test_without_a_key_the_error_says_how_to_fix_it(loaded, monkeypatch):
    monkeypatch.setattr(settings, "llm_mode", "live")
    monkeypatch.setattr(settings, "groq_api_key", None)
    response = loaded.post("/questions", json={"question": Q_REMOTE})
    assert response.status_code == 503
    assert "GROQ_API_KEY" in response.json()["detail"] and "replay" in response.json()["detail"]


def test_replay_mode_needs_no_key_and_a_missing_reply_is_a_visible_failure(loaded, monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "llm_mode", "replay")
    monkeypatch.setattr(settings, "groq_api_key", None)
    monkeypatch.setattr(settings, "llm_cache_path", str(tmp_path / "empty.jsonl"))
    body = loaded.post("/questions", json={"question": Q_REMOTE}).json()
    assert body["llm_mode"] == "replay"
    assert body["answer"]["status"] == "verification_failed" and "No recorded reply" in body["answer"]["resolution_reason"]


def test_health_reports_the_model_setup_without_calling_the_model(client, monkeypatch):
    monkeypatch.setattr(settings, "groq_api_key", None)
    llm = client.get("/health").json()["llm"]
    assert llm["key_present"] is False and llm["model"] and llm["mode"]

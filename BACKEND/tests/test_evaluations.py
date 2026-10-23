"""GET /evaluations/* with a run saved into a temporary results folder."""
import json
import pathlib

import pytest
from fastapi.testclient import TestClient
from truthguard_agent.evaluation import runner
from truthguard_agent.evaluation.cases import load_cases
from truthguard_agent.evaluation.runner import run_benchmark, save_run
from truthguard_agent.llm import FakeLLM
from truthguard_agent.retriever import InMemoryPassageStore
from truthguard_agent.schemas import Document

from app.main import app

FIXTURES = pathlib.Path(__file__).resolve().parents[2] / "AGENT" / "datasets" / "fixtures"


@pytest.fixture()
def results_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "RESULTS_DIR", tmp_path)
    return tmp_path


@pytest.fixture()
def saved_run(results_dir):
    store = InMemoryPassageStore([Document(**json.loads(p.read_text(encoding="utf-8"))) for p in sorted(FIXTURES.glob("*.json"))])
    case = [c for c in load_cases() if c.case_id == "C08"]
    reply = json.dumps({"claims": [], "caveats": ["Nothing."]})
    run = run_benchmark(case, store, lambda *a: FakeLLM([reply]), configs=["baseline", "full"])
    save_run(run, results_dir)
    return run


def test_latest_returns_the_whole_run_with_per_case_results(saved_run):
    body = TestClient(app).get("/evaluations/latest").json()
    assert body["run_id"] == saved_run.run_id and body["dataset_version"] == "v1"
    assert {r["config"] for r in body["results"]} == {"baseline", "full"}
    assert body["metrics"]["full"]["status_accuracy"]["denominator"] == 1
    assert body["metrics"]["baseline"]["winner_accuracy"]["applies"] is False


def test_before_any_run_the_message_says_how_to_run_it(results_dir):
    response = TestClient(app).get("/evaluations/latest")
    assert response.status_code == 404 and "python -m app.benchmark" in response.json()["detail"]


def test_runs_are_listed_and_fetched_by_id(saved_run):
    client = TestClient(app)
    listed = client.get("/evaluations/runs").json()
    assert [r["run_id"] for r in listed] == [saved_run.run_id]
    assert client.get("/evaluations/runs/%s" % saved_run.run_id).json()["run_id"] == saved_run.run_id


@pytest.mark.parametrize("bad", ["nope", "..%2Fsecret", "20260101T000000Z", "latest"])
def test_unknown_or_malformed_run_ids_are_404(saved_run, bad):
    assert TestClient(app).get("/evaluations/runs/%s" % bad).status_code == 404

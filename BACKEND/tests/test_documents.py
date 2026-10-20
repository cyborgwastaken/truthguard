import json
import pathlib

import pytest
from truthguard_agent.ingestion import normalize_text
from truthguard_agent.schemas import make_chunk_id

from app.api import documents as documents_api

FIXTURES = pathlib.Path(__file__).resolve().parents[2] / "AGENT" / "datasets" / "fixtures"

BODY = {
    "document_id": "remote_policy_v1",
    "title": "Remote Work Policy",
    "content": "Employees may work remotely up to five days per week.",
}


def post(client, **overrides):
    return client.post("/documents", json={**BODY, **overrides})


def test_create_returns_201_with_unknown_metadata_as_null(client):
    r = post(client)
    assert r.status_code == 201
    body = r.json()
    assert body["document_id"] == "remote_policy_v1"
    assert body["chunk_count"] == 1
    assert body["authority_level"] == "unknown"
    for field in ("version", "created_at", "effective_date", "supersedes_document_id", "source"):
        assert body[field] is None
    assert len(body["content_hash"]) == 64
    assert "content" not in body


def test_same_upload_again_changes_nothing(client):
    first = post(client).json()
    r = post(client)
    assert r.status_code == 200
    assert r.json() == first
    assert len(client.get("/documents").json()) == 1


def test_same_id_with_different_content_is_409_and_stored_text_is_kept(client):
    post(client)
    r = post(client, content="Employees may work remotely three days per week.")
    assert r.status_code == 409
    assert "different content or metadata" in r.json()["detail"]
    stored = client.get("/documents/remote_policy_v1").json()
    assert stored["content"] == BODY["content"]


def test_same_id_and_content_with_different_metadata_is_409(client):
    post(client)
    assert post(client, effective_date="2026-01-15").status_code == 409
    assert post(client, title="Another title").status_code == 409


def test_lost_race_on_the_primary_key_is_handled(client, monkeypatch):
    """Two uploads of one id at the same time: the second finds the first only after its insert fails."""
    post(client)
    real = documents_api._lookup
    calls = []

    def blind_first_time(session, document_id):
        calls.append(document_id)
        return None if len(calls) == 1 else real(session, document_id)

    monkeypatch.setattr(documents_api, "_lookup", blind_first_time)
    assert post(client).status_code == 200  # identical: treated as a duplicate
    calls.clear()
    assert post(client, title="different").status_code == 409
    assert len(client.get("/documents").json()) == 1


def test_list_is_sorted_has_chunk_counts_and_no_text(client):
    post(client, document_id="b_doc")
    post(client, document_id="a_doc", content=("A paragraph of policy text. " * 40 + "\n\n") * 3)
    docs = client.get("/documents").json()
    assert [d["document_id"] for d in docs] == ["a_doc", "b_doc"]
    assert docs[0]["chunk_count"] > 1 and docs[1]["chunk_count"] == 1
    assert all("content" not in d and "chunks" not in d for d in docs)


def test_list_pagination(client):
    for name in ("d1", "d2", "d3"):
        post(client, document_id=name)
    assert [d["document_id"] for d in client.get("/documents?limit=2").json()] == ["d1", "d2"]
    assert [d["document_id"] for d in client.get("/documents?limit=2&offset=2").json()] == ["d3"]
    assert client.get("/documents?limit=0").status_code == 422
    assert client.get("/documents?limit=501").status_code == 422
    assert client.get("/documents?offset=-1").status_code == 422


def test_empty_list(client):
    assert client.get("/documents").json() == []


def test_get_returns_text_and_chunks_that_match_their_offsets(client):
    content = "First paragraph about remote work.\n\n\n\nSecond paragraph about travel.   \r\nStill second."
    post(client, content=content)
    doc = client.get("/documents/remote_policy_v1").json()
    assert doc["content"] == content
    normalized = normalize_text(content)
    assert doc["chunk_count"] == len(doc["chunks"]) >= 1
    for index, chunk in enumerate(doc["chunks"]):
        assert chunk["chunk_id"] == make_chunk_id("remote_policy_v1", index)
        assert chunk["index"] == index
        assert normalized[chunk["start_offset"]:chunk["end_offset"]] == chunk["text"]


def test_get_unknown_document_is_404(client):
    r = client.get("/documents/nope")
    assert r.status_code == 404
    assert "nope" in r.json()["detail"]


@pytest.mark.parametrize(
    "overrides",
    [
        {"content": ""},
        {"content": "   \n\n  "},
        {"title": ""},
        {"document_id": ""},
        {"document_id": "has space"},
        {"document_id": "a/b"},
        {"document_id": "x" * 201},
        {"authority_level": "very-official"},
        {"effective_date": "not-a-date"},
        {"created_at": "2026-13-45"},
        {"supersedes_document_id": "remote_policy_v1"},
        {"supersedes_document_id": "bad id"},
        {"content": "has a \x00 nul"},
        {"title": "has a \x00 nul"},
        {"version": "v" * 65},
        {"content": "x" * 1_000_001},
    ],
)
def test_invalid_input_is_422(client, overrides):
    r = post(client, **overrides)
    assert r.status_code == 422, overrides
    assert client.get("/documents").json() == []


def test_missing_required_fields_is_422(client):
    assert client.post("/documents", json={"title": "x"}).status_code == 422
    assert client.post("/documents", content="not json", headers={"content-type": "application/json"}).status_code == 422


def test_supersession_is_stored_even_if_the_target_is_not_uploaded_yet(client):
    r = post(client, document_id="remote_policy_v2", supersedes_document_id="remote_policy_v1",
             authority_level="official", effective_date="2026-04-15")
    assert r.status_code == 201
    assert r.json()["supersedes_document_id"] == "remote_policy_v1"


def test_all_t01_fixture_documents_upload_and_keep_their_metadata(client):
    files = sorted(FIXTURES.glob("*.json"))
    assert len(files) >= 20
    expected = {}
    for path in files:
        data = json.loads(path.read_text())
        expected[data["document_id"]] = data
        assert client.post("/documents", json=data).status_code == 201, path.name
    listed = {d["document_id"]: d for d in client.get("/documents?limit=500").json()}
    assert set(listed) == set(expected)
    for document_id, data in expected.items():
        for field in ("title", "version", "created_at", "effective_date", "authority_level", "supersedes_document_id"):
            assert listed[document_id][field] == data.get(field), (document_id, field)
    assert listed["remote_policy_v2"]["supersedes_document_id"] == "remote_policy_v1"
    assert listed["remote_policy_v3_draft"]["effective_date"] is None
    assert listed["remote_policy_v3_draft"]["authority_level"] == "draft"

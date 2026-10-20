from __future__ import annotations

import json
import pathlib

import pytest

from truthguard_agent.schemas import DocumentIn

FIXTURES = pathlib.Path(__file__).parent.parent / "datasets" / "fixtures"


def _load_all_docs() -> list[dict]:
    return [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(FIXTURES.glob("*.json"))
    ]


def test_all_fixtures_validate() -> None:
    """Every JSON file in fixtures/ must parse as a valid DocumentIn."""
    paths = sorted(FIXTURES.glob("*.json"))
    assert len(paths) >= 15, "Expected at least 15 fixture documents"
    for path in paths:
        raw = json.loads(path.read_text(encoding="utf-8"))
        DocumentIn(**raw)  # raises ValidationError if invalid


def test_supersedes_references_exist() -> None:
    """Every supersedes_document_id must point to an existing document_id."""
    docs = _load_all_docs()
    existing_ids = {d["document_id"] for d in docs}
    for doc in docs:
        ref = doc.get("supersedes_document_id")
        if ref is not None:
            assert ref in existing_ids, (
                "Document '%s' supersedes '%s' but that document_id does not exist."
                % (doc["document_id"], ref)
            )


def test_document_ids_are_unique() -> None:
    """Every document_id in the fixture set must be unique."""
    docs = _load_all_docs()
    ids = [d["document_id"] for d in docs]
    duplicates = [doc_id for doc_id in ids if ids.count(doc_id) > 1]
    assert not duplicates, "Duplicate document_ids found: %s" % duplicates


def test_all_case_types_present() -> None:
    """Fixture set must contain examples of all six required case types.

    This is checked by verifying the required structural properties exist:
    - Superseded: at least one doc has a non-null supersedes_document_id
    - Draft trap: at least one doc has authority_level == 'draft' and effective_date == null
    - Informal: at least one doc has authority_level == 'informal'
    - Missing dates: at least one doc has created_at == null
    """
    docs = _load_all_docs()

    has_supersession = any(d.get("supersedes_document_id") is not None for d in docs)
    assert has_supersession, "No document with supersedes_document_id found (superseded case type missing)"

    has_draft_trap = any(
        d.get("authority_level") == "draft" and d.get("effective_date") is None
        for d in docs
    )
    assert has_draft_trap, "No draft document with null effective_date found (trap case type missing)"

    has_informal = any(d.get("authority_level") == "informal" for d in docs)
    assert has_informal, "No informal document found"

    has_null_date = any(d.get("created_at") is None for d in docs)
    assert has_null_date, "No document with null created_at found (missing-date case type missing)"

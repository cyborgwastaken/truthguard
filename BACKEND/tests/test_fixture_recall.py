"""Retrieval recall on the T01 fixtures: for each labeled question, are the documents it needs retrieved?"""
import json
import pathlib
import re

from app.db.search import PostgresPassageStore
from tests.helpers import store_document
from truthguard_agent.retriever import retrieve
from truthguard_agent.schemas import DocumentIn

FIXTURES = pathlib.Path(__file__).resolve().parents[2] / "AGENT" / "datasets" / "fixtures"


def labeled_cases():
    """(case_id, question, [document_id, ...]) for every row of the case table in the fixtures README."""
    cases = []
    for line in (FIXTURES / "README.md").read_text(encoding="utf-8").splitlines():
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) >= 5 and re.fullmatch(r"C\d\d", cells[0]):
            cases.append((cells[0], cells[1], re.findall(r"`([^`]+)`", cells[2])))
    return cases


def load_fixtures(db):
    for path in sorted(FIXTURES.glob("*.json")):
        store_document(db, DocumentIn(**json.loads(path.read_text(encoding="utf-8"))))


def missing_documents(db, k, expand_related):
    store = PostgresPassageStore(db)
    missing = {}
    for case_id, question, needed in labeled_cases():
        found = {p.document.document_id for p in retrieve(question, store, k=k, expand_related=expand_related)}
        if set(needed) - found:
            missing[case_id] = sorted(set(needed) - found)
    return missing


def test_the_case_table_is_read_from_the_readme():
    cases = labeled_cases()
    assert [c[0] for c in cases] == ["C%02d" % n for n in range(1, 19)]
    assert sum(1 for c in cases if c[2]) == 15
    fixture_ids = {path.stem for path in FIXTURES.glob("*.json")}
    assert {doc for c in cases for doc in c[2]} <= fixture_ids


def test_every_labeled_question_retrieves_its_relevant_documents(db):
    load_fixtures(db)
    assert missing_documents(db, k=8, expand_related=True) == {}


def test_search_alone_finds_every_relevant_document_in_the_top_five(db):
    load_fixtures(db)
    assert missing_documents(db, k=5, expand_related=False) == {}

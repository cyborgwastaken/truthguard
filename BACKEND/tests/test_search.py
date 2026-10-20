from datetime import date

import pytest

from app.db.search import PostgresPassageStore
from tests.helpers import add_document
from truthguard_agent.retriever import retrieve
from truthguard_agent.schemas import AuthorityLevel


def ids(passages):
    return [p.chunk.chunk_id for p in passages]


def test_search_matches_when_only_some_of_the_question_words_are_in_the_passage(db):
    add_document(db, "d1", "Employees may work remotely.")
    assert ids(PostgresPassageStore(db).search("remotely quokka", limit=5)) == ["d1::chunk_000"]


def test_search_ranks_the_passage_matching_more_words_first_with_scores(db):
    add_document(db, "one", "Annual leave is 25 days.")
    add_document(db, "two", "Sick leave is 10 days.")
    add_document(db, "none", "Travel must be booked through the portal.")
    passages = PostgresPassageStore(db).search("annual leave", limit=5)
    assert ids(passages) == ["one::chunk_000", "two::chunk_000"]
    assert isinstance(passages[0].score, float) and passages[0].score > passages[1].score > 0


def test_search_matches_word_forms(db):
    add_document(db, "d1", "Employees may work remotely.")
    assert ids(PostgresPassageStore(db).search("remote", limit=5)) == ["d1::chunk_000"]


def test_search_respects_the_limit_and_rejects_a_limit_below_one(db):
    for name in ("a", "b", "c"):
        add_document(db, name, "leave policy")
    store = PostgresPassageStore(db)
    assert len(store.search("leave", limit=2)) == 2
    with pytest.raises(ValueError):
        store.search("leave", limit=0)


def test_search_returns_nothing_for_no_match_or_a_question_of_only_stop_words(db):
    add_document(db, "d1", "Sick leave is 10 days.")
    store = PostgresPassageStore(db)
    assert store.search("stock options", limit=5) == []
    assert store.search("the and of", limit=5) == []


def test_search_breaks_score_ties_by_chunk_id_in_code_point_order(db):
    add_document(db, "alpha", "same words")
    add_document(db, "Zeta", "same words")
    assert ids(PostgresPassageStore(db).search("same words", limit=5)) == ["Zeta::chunk_000", "alpha::chunk_000"]


def test_search_results_carry_the_document_metadata_and_chunk_details(db):
    add_document(
        db,
        "v2",
        "Effective April 15 employees may work remotely three days per week.",
        supersedes="v1",
        version="2",
        created_at=date(2026, 4, 1),
        effective_date=date(2026, 4, 15),
        authority_level=AuthorityLevel.OFFICIAL,
        source="HR Department",
    )
    passage = PostgresPassageStore(db).search("remotely", limit=5)[0]
    assert (passage.chunk.chunk_id, passage.chunk.document_id, passage.chunk.index) == ("v2::chunk_000", "v2", 0)
    assert passage.chunk.text == passage.document.content
    assert (passage.chunk.start_offset, passage.chunk.end_offset) == (0, len(passage.chunk.text))
    doc = passage.document
    assert (doc.document_id, doc.title, doc.version, doc.source) == ("v2", "v2", "2", "HR Department")
    assert (doc.created_at, doc.effective_date) == (date(2026, 4, 1), date(2026, 4, 15))
    assert doc.authority_level == AuthorityLevel.OFFICIAL and doc.supersedes_document_id == "v1"
    assert len(doc.content_hash) == 64


def test_search_keeps_missing_metadata_unknown(db):
    add_document(db, "d1", "Employees may work remotely.")
    doc = PostgresPassageStore(db).search("remotely", limit=5)[0].document
    assert doc.version is None and doc.created_at is None and doc.effective_date is None
    assert doc.supersedes_document_id is None and doc.source is None
    assert doc.authority_level == AuthorityLevel.UNKNOWN


def test_related_passages_finds_the_document_that_supersedes(db):
    add_document(db, "v1", "old")
    add_document(db, "v2", "new", supersedes="v1")
    add_document(db, "other", "unrelated")
    passages = PostgresPassageStore(db).related_passages(["v1"])
    assert ids(passages) == ["v2::chunk_000"]
    assert passages[0].score is None and passages[0].document.supersedes_document_id == "v1"


def test_related_passages_finds_the_document_that_is_superseded(db):
    add_document(db, "v1", "old")
    add_document(db, "v2", "new", supersedes="v1")
    assert ids(PostgresPassageStore(db).related_passages(["v2"])) == ["v1::chunk_000"]


def test_related_passages_does_not_return_the_given_documents_and_goes_one_hop_only(db):
    add_document(db, "v1", "one")
    add_document(db, "v2", "two", supersedes="v1")
    add_document(db, "v3", "three", supersedes="v2")
    store = PostgresPassageStore(db)
    assert ids(store.related_passages(["v1", "v2"])) == ["v3::chunk_000"]
    assert ids(store.related_passages(["v1"])) == ["v2::chunk_000"]
    assert ids(store.related_passages(["v3"])) == ["v2::chunk_000"]


def test_related_passages_ignores_unknown_ids_dangling_references_none_and_repeats(db):
    add_document(db, "x", "text", supersedes="never_ingested")
    add_document(db, "v1", "old")
    add_document(db, "v2", "new", supersedes="v1")
    store = PostgresPassageStore(db)
    assert store.related_passages([]) == []
    assert store.related_passages(["unknown"]) == []
    assert store.related_passages(["x"]) == []
    assert store.related_passages([None]) == []
    assert ids(store.related_passages(["v1", "v1", None])) == ["v2::chunk_000"]


def test_related_passages_returns_every_chunk_in_document_id_then_chunk_order(db):
    add_document(db, "v1", "old")
    add_document(db, "v2", "x" * 500 + "\n\n" + "y" * 500, supersedes="v1")
    add_document(db, "Zeta", "newer", supersedes="v1")
    add_document(db, "alpha", "newest", supersedes="v1")
    assert ids(PostgresPassageStore(db).related_passages(["v1"])) == [
        "Zeta::chunk_000",
        "alpha::chunk_000",
        "v2::chunk_000",
        "v2::chunk_001",
    ]


def test_retrieve_over_postgres_follows_a_chain_and_keeps_scores_apart(db):
    add_document(db, "v1", "Employees may work remotely five days per week.")
    add_document(db, "v2", "Amended once.", supersedes="v1")
    add_document(db, "v3", "Amended twice.", supersedes="v2")
    add_document(db, "travel", "Travel must be booked through the portal.")
    passages = retrieve("How many days per week can employees work remotely?", PostgresPassageStore(db))
    assert ids(passages) == ["v1::chunk_000", "v2::chunk_000", "v3::chunk_000"]
    assert [p.score is None for p in passages] == [False, True, True]

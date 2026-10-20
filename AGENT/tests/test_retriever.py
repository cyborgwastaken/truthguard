from __future__ import annotations

import pytest

from truthguard_agent.retriever import InMemoryPassageStore
from truthguard_agent.schemas import Document


def make_doc(document_id, content="Placeholder text.", supersedes=None, **fields):
    return Document(
        document_id=document_id, title=document_id, content=content, supersedes_document_id=supersedes, **fields
    )


def ids(passages):
    return [p.chunk.chunk_id for p in passages]


def test_search_returns_matching_passages_ranked_with_ids_metadata_and_scores():
    store = InMemoryPassageStore(
        [
            make_doc("sick", "Sick leave is 10 days.", version="3"),
            make_doc("annual", "Annual leave is 25 days.", version="2"),
            make_doc("travel", "Travel must be booked through the portal."),
        ]
    )
    passages = store.search("annual leave", limit=5)
    assert ids(passages) == ["annual::chunk_000", "sick::chunk_000"]
    assert passages[0].score > passages[1].score > 0
    assert passages[0].document.document_id == "annual" and passages[0].document.version == "2"
    assert passages[0].chunk.text == "Annual leave is 25 days."


def test_search_ranks_a_passage_with_a_rare_word_above_ones_with_a_common_word():
    store = InMemoryPassageStore(
        [
            make_doc("d1", "leave one"),
            make_doc("d2", "leave two"),
            make_doc("d3", "leave three"),
            make_doc("z", "stock options"),
        ]
    )
    assert ids(store.search("stock leave", limit=4)) == ["z::chunk_000", "d1::chunk_000", "d2::chunk_000", "d3::chunk_000"]


def test_search_respects_the_limit():
    store = InMemoryPassageStore([make_doc("a", "leave one"), make_doc("b", "leave two"), make_doc("c", "leave three")])
    assert len(store.search("leave", limit=2)) == 2


def test_search_returns_nothing_when_no_term_matches():
    store = InMemoryPassageStore([make_doc("a", "Sick leave is 10 days.")])
    assert store.search("stock options", limit=5) == []


def test_search_breaks_score_ties_by_chunk_id():
    store = InMemoryPassageStore([make_doc("b", "same words"), make_doc("a", "same words")])
    assert ids(store.search("same words", limit=5)) == ["a::chunk_000", "b::chunk_000"]


@pytest.mark.parametrize("bad", [0, -1])
def test_search_limit_must_be_positive(bad):
    with pytest.raises(ValueError):
        InMemoryPassageStore([make_doc("a")]).search("text", limit=bad)


def test_related_passages_finds_the_document_that_supersedes():
    store = InMemoryPassageStore([make_doc("v1", "old"), make_doc("v2", "new", supersedes="v1"), make_doc("other")])
    passages = store.related_passages(["v1"])
    assert ids(passages) == ["v2::chunk_000"]
    assert passages[0].score is None
    assert passages[0].document.supersedes_document_id == "v1"


def test_related_passages_finds_the_document_that_is_superseded():
    store = InMemoryPassageStore([make_doc("v1", "old"), make_doc("v2", "new", supersedes="v1"), make_doc("other")])
    assert ids(store.related_passages(["v2"])) == ["v1::chunk_000"]


def test_related_passages_does_not_return_the_given_documents():
    store = InMemoryPassageStore([make_doc("v1"), make_doc("v2", supersedes="v1")])
    assert store.related_passages(["v1", "v2"]) == []


def test_related_passages_is_one_hop_only():
    store = InMemoryPassageStore([make_doc("v1"), make_doc("v2", supersedes="v1"), make_doc("v3", supersedes="v2")])
    assert ids(store.related_passages(["v1"])) == ["v2::chunk_000"]


def test_related_passages_ignores_unknown_ids_and_dangling_references():
    store = InMemoryPassageStore([make_doc("x", supersedes="never_ingested"), make_doc("y")])
    assert store.related_passages(["unknown"]) == []
    assert store.related_passages(["x"]) == []


def test_related_passages_returns_every_chunk_in_document_then_chunk_order():
    long_content = "x" * 500 + "\n\n" + "y" * 500
    store = InMemoryPassageStore(
        [make_doc("v1"), make_doc("v2", long_content, supersedes="v1"), make_doc("v0"), make_doc("v1b", supersedes="v1")]
    )
    assert ids(store.related_passages(["v1"])) == [
        "v1b::chunk_000",
        "v2::chunk_000",
        "v2::chunk_001",
    ]


def test_related_passages_with_no_ids_returns_nothing():
    assert InMemoryPassageStore([make_doc("v1"), make_doc("v2", supersedes="v1")]).related_passages([]) == []

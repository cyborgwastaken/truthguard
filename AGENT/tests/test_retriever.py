from __future__ import annotations

import pytest

from truthguard_agent.retriever import InMemoryPassageStore, retrieve
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


class SpyStore(InMemoryPassageStore):
    def __init__(self, documents):
        super().__init__(documents)
        self.related_calls = []

    def related_passages(self, document_ids):
        self.related_calls.append(list(document_ids))
        return super().related_passages(document_ids)


def test_retrieve_returns_ranked_hits_with_scores_then_related_passages_without_scores():
    store = InMemoryPassageStore(
        [
            make_doc("v1", "Employees may work remotely five days per week."),
            make_doc("v2", "Effective April the limit is lower.", supersedes="v1"),
            make_doc("travel", "Travel must be booked through the portal."),
        ]
    )
    passages = retrieve("remotely days week", store)
    assert ids(passages) == ["v1::chunk_000", "v2::chunk_000"]
    assert passages[0].score is not None and passages[0].score > 0
    assert passages[1].score is None
    assert passages[1].document.supersedes_document_id == "v1"


def test_retrieve_does_not_repeat_a_passage_that_was_already_a_hit():
    store = InMemoryPassageStore(
        [
            make_doc("v1", "Employees may work remotely five days per week."),
            make_doc("v2", "The remote limit is three days.", supersedes="v1"),
        ]
    )
    passages = retrieve("remotely days", store)
    assert sorted(ids(passages)) == ["v1::chunk_000", "v2::chunk_000"]
    assert all(p.score is not None for p in passages)


def test_retrieve_follows_a_chain_of_supersessions():
    store = InMemoryPassageStore(
        [
            make_doc("v1", "Employees may work remotely five days per week."),
            make_doc("v2", "Amended once.", supersedes="v1"),
            make_doc("v3", "Amended twice.", supersedes="v2"),
        ]
    )
    assert ids(retrieve("remotely days week", store)) == ["v1::chunk_000", "v2::chunk_000", "v3::chunk_000"]


def test_retrieve_follows_a_chain_in_both_directions_from_the_middle():
    store = InMemoryPassageStore(
        [
            make_doc("v1", "Original."),
            make_doc("v2", "Employees may work remotely five days per week.", supersedes="v1"),
            make_doc("v3", "Amended twice.", supersedes="v2"),
            make_doc("v4", "Amended three times.", supersedes="v3"),
        ]
    )
    assert ids(retrieve("remotely days week", store)) == [
        "v2::chunk_000",
        "v1::chunk_000",
        "v3::chunk_000",
        "v4::chunk_000",
    ]


def test_retrieve_stops_on_a_cycle_and_on_self_supersession():
    cycle = InMemoryPassageStore(
        [make_doc("a", "Remote days apply.", supersedes="b"), make_doc("b", "Other text.", supersedes="a")]
    )
    assert ids(retrieve("remote days", cycle)) == ["a::chunk_000", "b::chunk_000"]
    itself = InMemoryPassageStore([make_doc("s", "Remote days apply.", supersedes="s")])
    assert ids(retrieve("remote days", itself)) == ["s::chunk_000"]


def test_retrieve_stops_after_a_fixed_number_of_rounds_on_a_long_chain():
    docs = [make_doc("d01", "Employees may work remotely five days per week.")]
    docs += [make_doc("d%02d" % n, "Amended.", supersedes="d%02d" % (n - 1)) for n in range(2, 13)]
    store = SpyStore(docs)
    passages = retrieve("remotely days week", store)
    assert store.related_calls == [["d01"], ["d02"], ["d03"], ["d04"], ["d05"]]
    assert ids(passages) == ["d%02d::chunk_000" % n for n in range(1, 7)]


def test_retrieve_does_not_add_the_rest_of_a_document_that_was_already_a_hit():
    store = InMemoryPassageStore(
        [
            make_doc("v1", "Remote days apply.\n\n" + "z" * 500 + "\n\n" + "y" * 500),
            make_doc("v2", "Amended.", supersedes="v1"),
        ]
    )
    assert ids(retrieve("remote days", store)) == ["v1::chunk_000", "v2::chunk_000"]


def test_retrieve_without_expansion_returns_only_the_ranked_hits():
    store = SpyStore(
        [make_doc("v1", "Employees may work remotely five days per week."), make_doc("v2", "Amended.", supersedes="v1")]
    )
    passages = retrieve("remotely days week", store, expand_related=False)
    assert ids(passages) == ["v1::chunk_000"]
    assert store.related_calls == []


def test_retrieve_k_limits_the_ranked_hits_and_related_passages_come_on_top():
    store = InMemoryPassageStore(
        [
            make_doc("a", "leave one"),
            make_doc("b", "leave two"),
            make_doc("c", "leave three"),
            make_doc("amend", "Nothing in common.", supersedes="a"),
        ]
    )
    passages = retrieve("leave", store, k=2)
    assert ids(passages) == ["a::chunk_000", "b::chunk_000", "amend::chunk_000"]


def test_retrieve_with_no_hits_returns_nothing_and_does_not_look_for_related_documents():
    store = SpyStore([make_doc("a", "Sick leave is 10 days."), make_doc("b", "Amended.", supersedes="a")])
    assert retrieve("stock options", store) == []
    assert store.related_calls == []


@pytest.mark.parametrize("bad", [0, -1])
def test_retrieve_k_must_be_positive(bad):
    with pytest.raises(ValueError):
        retrieve("leave", InMemoryPassageStore([make_doc("a")]), k=bad)


def test_results_are_copies_so_editing_one_does_not_change_the_store():
    store = InMemoryPassageStore([make_doc("v1", "Remote days apply."), make_doc("v2", "Amended.", supersedes="v1")])
    hit = store.search("remote days", limit=5)[0]
    hit.chunk.text = "tampered"
    hit.document.title = "tampered"
    related = store.related_passages(["v1"])[0]
    related.score = 9.0
    related.chunk.text = "tampered"
    assert store.search("remote days", limit=5)[0].chunk.text == "Remote days apply."
    assert store.search("remote days", limit=5)[0].document.title == "v1"
    assert store.related_passages(["v1"])[0].score is None
    assert store.related_passages(["v1"])[0].chunk.text == "Amended."


def test_search_matches_non_ascii_words_as_whole_words():
    store = InMemoryPassageStore([make_doc("de", "Der über Vertrag gilt."), make_doc("x", "Nur ber ist hier.")])
    assert ids(store.search("über", limit=5)) == ["de::chunk_000"]
    cyrillic = InMemoryPassageStore([make_doc("ru", "Отпуск составляет 25 дней.")])
    assert ids(cyrillic.search("отпуск", limit=5)) == ["ru::chunk_000"]


def test_related_passages_is_one_hop_only_on_the_older_side_too():
    store = InMemoryPassageStore([make_doc("v1"), make_doc("v2", supersedes="v1"), make_doc("v3", supersedes="v2")])
    passages = store.related_passages(["v3"])
    assert ids(passages) == ["v2::chunk_000"]
    assert passages[0].score is None


def test_related_passages_treats_repeated_and_missing_ids_like_a_set():
    store = InMemoryPassageStore([make_doc("v1"), make_doc("v2", supersedes="v1"), make_doc("plain")])
    assert ids(store.related_passages(["v1", "v1"])) == ["v2::chunk_000"]
    assert store.related_passages([None]) == []


def test_related_passages_of_a_document_that_supersedes_itself_is_empty():
    assert InMemoryPassageStore([make_doc("s", supersedes="s")]).related_passages(["s"]) == []


class CannedStore:
    """A store that returns what it was given, with no checks of its own."""

    def __init__(self, hits, related):
        self.hits = hits
        self.related = related

    def search(self, query, limit):
        return self.hits

    def related_passages(self, document_ids):
        return self.related


def test_retrieve_checks_k_itself_and_does_not_change_the_list_the_store_returned():
    docs = InMemoryPassageStore([make_doc("v1", "Remote days apply."), make_doc("v2", "Amended.", supersedes="v1")])
    hits = docs.search("remote days", limit=5)
    related = docs.related_passages(["v1"])
    store = CannedStore(hits, related)
    with pytest.raises(ValueError):
        retrieve("remote days", store, k=0)
    assert ids(retrieve("remote days", store)) == ["v1::chunk_000", "v2::chunk_000"]
    assert ids(store.hits) == ["v1::chunk_000"]

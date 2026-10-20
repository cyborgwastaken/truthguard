"""Find the passages that may answer a question. The AGENT package never touches the database: a
PassageStore hides where the passages live (the Postgres one is in BACKEND, the in-memory one is here)."""
from __future__ import annotations

import math
import re
from typing import Dict, Iterable, List, Protocol

from .ingestion import chunk_document
from .schemas import Document, RetrievedPassage

_WORD = re.compile(r"[a-z0-9]+")


class PassageStore(Protocol):
    def search(self, query: str, limit: int) -> List[RetrievedPassage]:
        """Passages that match the query, best first, each with a score."""
        ...

    def related_passages(self, document_ids: List[str]) -> List[RetrievedPassage]:
        """Every passage of the documents one supersession step away from the given ones.

        That means documents that supersede a given document and documents a given document supersedes,
        but not the given documents themselves. Passages come in document then chunk order with
        score=None, because no text match was scored for them. Unknown IDs, and a supersedes_document_id
        that points at a document which was never ingested, are ignored.
        """
        ...


MAX_EXPANSION_ROUNDS = 5


def retrieve(question: str, store: PassageStore, k: int = 8, expand_related: bool = True) -> List[RetrievedPassage]:
    """The passages that may answer the question: ranked hits first, then supersession-related ones.

    k is the number of ranked hits; related passages are added on top, so the list can be longer than k.
    Ranked hits carry a score, related passages have score=None. Callers must keep that distinction and
    never sort None as a score. With expand_related the documents that supersede, or are superseded by,
    a hit are added, and so are theirs in turn (a chain v1 -> v2 -> v3), for at most MAX_EXPANSION_ROUNDS
    rounds. A document is added once, so cycles end; a hit document is not topped up with its other chunks.
    """
    if k < 1:
        raise ValueError("k must be at least 1")
    passages = list(store.search(question, k))
    if not expand_related:
        return passages
    visited = {p.document.document_id for p in passages}
    frontier = sorted(visited)
    for _ in range(MAX_EXPANSION_ROUNDS):
        if not frontier:
            break
        found = [p for p in store.related_passages(frontier) if p.document.document_id not in visited]
        passages.extend(found)
        frontier = sorted({p.document.document_id for p in found})
        visited.update(frontier)
    return passages


class InMemoryPassageStore:
    """A PassageStore over a list of documents, for tests. Scoring is a plain word-overlap sum weighted
    by rarity: good enough to exercise callers, not a stand-in for Postgres ranking."""

    def __init__(self, documents: Iterable[Document]) -> None:
        self._documents: Dict[str, Document] = {doc.document_id: doc for doc in documents}
        self._passages: Dict[str, List[RetrievedPassage]] = {
            doc_id: [RetrievedPassage(chunk=chunk, document=doc) for chunk in chunk_document(doc)]
            for doc_id, doc in self._documents.items()
        }

    def search(self, query: str, limit: int) -> List[RetrievedPassage]:
        if limit < 1:
            raise ValueError("limit must be at least 1")
        passages = [p for chunks in self._passages.values() for p in chunks]
        words = [set(_WORD.findall(p.chunk.text.lower())) for p in passages]
        weight = {}
        for term in set(_WORD.findall(query.lower())):
            matches = sum(term in found for found in words)
            if matches:
                weight[term] = math.log(1 + len(passages) / matches)
        scored = []
        for passage, found in zip(passages, words):
            score = sum(w for term, w in weight.items() if term in found)
            if score > 0:
                scored.append(passage.model_copy(update={"score": score}))
        scored.sort(key=lambda p: (-p.score, p.chunk.chunk_id))
        return scored[:limit]

    def related_passages(self, document_ids: List[str]) -> List[RetrievedPassage]:
        given = set(document_ids)
        related = set()
        for doc_id in given & self._documents.keys():
            older = self._documents[doc_id].supersedes_document_id
            if older in self._documents:
                related.add(older)
        for doc in self._documents.values():
            if doc.supersedes_document_id in given:
                related.add(doc.document_id)
        return [p for doc_id in sorted(related - given) for p in self._passages[doc_id]]

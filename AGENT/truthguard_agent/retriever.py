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

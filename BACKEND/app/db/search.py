"""Postgres implementation of the AGENT's PassageStore (see truthguard_agent.retriever)."""
from __future__ import annotations

from typing import List, Optional

from sqlalchemy import Text, cast, collate, func, select, union
from sqlalchemy.dialects.postgresql import TSQUERY
from sqlalchemy.orm import Session, aliased

from truthguard_agent.schemas import Chunk, Document, RetrievedPassage

from .models import ChunkRow, DocumentRow


def _passage(chunk: ChunkRow, document: DocumentRow, score: Optional[float]) -> RetrievedPassage:
    return RetrievedPassage(
        chunk=Chunk(
            chunk_id=chunk.chunk_id,
            document_id=chunk.document_id,
            index=chunk.chunk_index,
            text=chunk.text,
            start_offset=chunk.start_offset,
            end_offset=chunk.end_offset,
        ),
        document=Document(
            document_id=document.document_id,
            title=document.title,
            content=document.content,
            content_hash=document.content_hash,
            version=document.version,
            created_at=document.created_at,
            effective_date=document.effective_date,
            authority_level=document.authority_level,
            supersedes_document_id=document.supersedes_document_id,
            source=document.source,
        ),
        score=score,
    )


class PostgresPassageStore:
    def __init__(self, session: Session) -> None:
        self._session = session

    def search(self, query: str, limit: int) -> List[RetrievedPassage]:
        """Full-text search over chunks, best first. A chunk matches when it has ANY word of the question.

        plainto_tsquery joins the words with AND, so a natural question ("How many days per week can
        employees work remotely?") matched almost nothing on the T01 fixtures. The words are joined with OR
        instead and ts_rank orders the hits.
        """
        if limit < 1:
            raise ValueError("limit must be at least 1")
        # Postgres text cannot hold a NUL character, and one would abort the whole transaction.
        query = query.replace("\x00", " ")
        tsquery = cast(
            func.replace(cast(func.plainto_tsquery("english", query), Text), " & ", " | "), TSQUERY
        )
        score = func.ts_rank(ChunkRow.tsv, tsquery)
        rows = self._session.execute(
            select(ChunkRow, DocumentRow, score)
            .join(DocumentRow, DocumentRow.document_id == ChunkRow.document_id)
            .where(ChunkRow.tsv.op("@@")(tsquery))
            .order_by(score.desc(), collate(ChunkRow.chunk_id, "C"))
            .limit(limit)
        ).all()
        return [_passage(chunk, document, float(rank)) for chunk, document, rank in rows]

    def related_passages(self, document_ids: List[str]) -> List[RetrievedPassage]:
        """Every chunk of the documents one supersession step from the given ones (not the given ones)."""
        given = {doc_id for doc_id in document_ids if doc_id is not None}
        if not given:
            return []
        given_row, newer_row = aliased(DocumentRow), aliased(DocumentRow)
        older = select(given_row.supersedes_document_id).where(
            given_row.document_id.in_(given), given_row.supersedes_document_id.is_not(None)
        )
        newer = select(newer_row.document_id).where(newer_row.supersedes_document_id.in_(given))
        # A UNION of the two lookups, not an OR inside one WHERE: the OR stops Postgres from using the
        # indexes on documents.supersedes_document_id and chunks.document_id.
        related = union(older, newer).subquery()
        rows = self._session.execute(
            select(ChunkRow, DocumentRow)
            .join(DocumentRow, DocumentRow.document_id == ChunkRow.document_id)
            .where(
                DocumentRow.document_id.in_(select(related)),
                DocumentRow.document_id.not_in(given),
            )
            .order_by(collate(DocumentRow.document_id, "C"), ChunkRow.chunk_index)
        ).all()
        return [_passage(chunk, document, None) for chunk, document in rows]

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, defer
from truthguard_agent.ingestion import ingest_document
from truthguard_agent.schemas import Chunk, Document

from ..db.models import ChunkRow, DocumentRow
from ..db.session import get_session
from ..schemas.documents import DocumentCreate, DocumentDetail, DocumentSummary

router = APIRouter(prefix="/documents", tags=["documents"])

# Every stored column except content_hash and ingested_at, which are computed.
_METADATA_FIELDS = (
    "title",
    "version",
    "created_at",
    "effective_date",
    "authority_level",
    "supersedes_document_id",
    "source",
)

CONFLICT_MESSAGE = (
    "A document with this document_id already exists with different content or metadata. "
    "Versioning is not supported yet: use a new document_id for a new version."
)


def _lookup(session: Session, document_id: str) -> Optional[DocumentRow]:
    return session.get(DocumentRow, document_id)


def _to_row(doc: Document) -> DocumentRow:
    values = doc.model_dump()
    values["authority_level"] = doc.authority_level.value
    return DocumentRow(**values)


def _is_identical(row: DocumentRow, doc: Document) -> bool:
    new = _to_row(doc)
    return row.content_hash == new.content_hash and all(
        getattr(row, field) == getattr(new, field) for field in _METADATA_FIELDS
    )


def _summary(row: DocumentRow, chunk_count: int) -> DocumentSummary:
    return DocumentSummary(
        document_id=row.document_id,
        title=row.title,
        version=row.version,
        created_at=row.created_at,
        effective_date=row.effective_date,
        authority_level=row.authority_level,
        supersedes_document_id=row.supersedes_document_id,
        source=row.source,
        content_hash=row.content_hash,
        ingested_at=row.ingested_at,
        chunk_count=chunk_count,
    )


def _chunk_count(session: Session, document_id: str) -> int:
    return session.scalar(select(func.count()).select_from(ChunkRow).where(ChunkRow.document_id == document_id)) or 0


@router.post("", response_model=DocumentSummary, status_code=201)
def create_document(payload: DocumentCreate, response: Response, session: Session = Depends(get_session)):
    """Store a document and its chunks.

    Uploading the same document again (same content and metadata) changes nothing and returns the
    stored record with status 200. The same document_id with anything different is a 409.
    """
    doc, chunks = ingest_document(payload)
    if not chunks:
        raise HTTPException(status_code=422, detail="The document content has no text to index.")

    existing = _lookup(session, doc.document_id)
    if existing is not None:
        if _is_identical(existing, doc):
            response.status_code = 200
            return _summary(existing, _chunk_count(session, existing.document_id))
        raise HTTPException(status_code=409, detail=CONFLICT_MESSAGE)

    row = _to_row(doc)
    row.chunks = [
        ChunkRow(
            chunk_id=c.chunk_id,
            document_id=c.document_id,
            chunk_index=c.index,
            text=c.text,
            start_offset=c.start_offset,
            end_offset=c.end_offset,
        )
        for c in chunks
    ]
    try:
        # SAVEPOINT: a lost race on the primary key undoes only this insert.
        with session.begin_nested():
            session.add(row)
            session.flush()
    except IntegrityError:
        existing = _lookup(session, doc.document_id)
        if existing is None:
            raise  # a different integrity problem: let it surface as a server error
        if _is_identical(existing, doc):
            response.status_code = 200
            return _summary(existing, _chunk_count(session, existing.document_id))
        raise HTTPException(status_code=409, detail=CONFLICT_MESSAGE)
    session.commit()
    session.refresh(row)
    return _summary(row, len(chunks))


@router.get("", response_model=List[DocumentSummary])
def list_documents(
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
):
    """List documents (metadata only, ordered by document_id)."""
    counts = (
        select(ChunkRow.document_id, func.count().label("n")).group_by(ChunkRow.document_id).subquery()
    )
    rows = session.execute(
        select(DocumentRow, func.coalesce(counts.c.n, 0))
        .options(defer(DocumentRow.content))  # the text can be large; lists do not need it
        .outerjoin(counts, counts.c.document_id == DocumentRow.document_id)
        .order_by(DocumentRow.document_id)
        .limit(limit)
        .offset(offset)
    ).all()
    return [_summary(row, count) for row, count in rows]


@router.get("/{document_id}", response_model=DocumentDetail)
def get_document(document_id: str, session: Session = Depends(get_session)):
    """One document with its full text and its chunks."""
    row = _lookup(session, document_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Document not found: %s" % document_id)
    chunks = [
        Chunk(
            chunk_id=c.chunk_id,
            document_id=c.document_id,
            index=c.chunk_index,
            text=c.text,
            start_offset=c.start_offset,
            end_offset=c.end_offset,
        )
        for c in row.chunks
    ]
    return DocumentDetail(**_summary(row, len(chunks)).model_dump(), content=row.content, chunks=chunks)

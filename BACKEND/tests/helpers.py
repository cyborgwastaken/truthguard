from app.db.models import ChunkRow, DocumentRow
from truthguard_agent.ingestion import ingest_document
from truthguard_agent.schemas import DocumentIn


def store_document(db, doc_in):
    """Store a document and its chunks the way ingestion produces them (the API does this in T06)."""
    doc, chunks = ingest_document(doc_in)
    fields = doc.model_dump(exclude={"authority_level"})
    db.add(DocumentRow(**fields, authority_level=doc.authority_level.value))
    db.flush()
    # Inserted last chunk first, so any ordering in the results has to come from the query.
    db.add_all(
        ChunkRow(
            chunk_id=c.chunk_id,
            document_id=c.document_id,
            chunk_index=c.index,
            text=c.text,
            start_offset=c.start_offset,
            end_offset=c.end_offset,
        )
        for c in reversed(chunks)
    )
    db.flush()


def add_document(db, document_id, content, supersedes=None, **fields):
    """store_document for a made-up document whose title is its id."""
    doc_in = DocumentIn(
        document_id=document_id, title=document_id, content=content, supersedes_document_id=supersedes, **fields
    )
    store_document(db, doc_in)

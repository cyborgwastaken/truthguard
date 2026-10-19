import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.db.models import (
    AnswerCitationRow,
    AnswerRow,
    ChunkRow,
    ClaimRow,
    DocumentRow,
    EvidenceLinkRow,
)


def make_doc(db, document_id="d1", content="Employees may work remotely three days a week."):
    doc = DocumentRow(document_id=document_id, title="Remote Work Policy", content=content, content_hash="h")
    db.add(doc)
    db.flush()
    return doc


def make_chunk(db, document_id="d1", index=0, text="Employees may work remotely three days a week."):
    chunk = ChunkRow(
        chunk_id="%s::chunk_%03d" % (document_id, index),
        document_id=document_id,
        chunk_index=index,
        text=text,
        start_offset=0,
        end_offset=len(text),
    )
    db.add(chunk)
    db.flush()
    return chunk


def test_missing_metadata_is_stored_as_null(db):
    make_doc(db)
    db.expire_all()
    doc = db.get(DocumentRow, "d1")
    assert doc.version is None
    assert doc.created_at is None
    assert doc.effective_date is None
    assert doc.supersedes_document_id is None
    assert doc.source is None
    assert doc.authority_level == "unknown"


def test_chunk_full_text_search_column_is_generated(db):
    make_doc(db)
    make_chunk(db, text="Employees may work remotely three days a week.")
    make_chunk(db, index=1, text="Travel must be booked through the portal.")
    db.flush()
    hits = db.scalars(
        select(ChunkRow.chunk_id).where(ChunkRow.tsv.op("@@")(func.plainto_tsquery("english", "remote work")))
    ).all()
    assert hits == ["d1::chunk_000"]


def test_deleting_a_document_deletes_its_chunks(db):
    doc = make_doc(db)
    make_chunk(db)
    db.delete(doc)
    db.flush()
    assert db.scalar(select(func.count()).select_from(ChunkRow)) == 0


def test_chunk_requires_an_existing_document(db):
    with pytest.raises(IntegrityError):
        make_chunk(db, document_id="missing")


def test_answer_claim_and_evidence_round_trip(db):
    make_doc(db)
    chunk = make_chunk(db)
    answer = AnswerRow(answer_id="a1", question="How many remote days?", answer="Three.", status="resolved")
    answer.claims.append(ClaimRow(claim_id="a1::c1", answer_id="a1", text="Three days are allowed."))
    answer.citations.append(AnswerCitationRow(chunk_id=chunk.chunk_id, source_id="d1"))
    db.add(answer)
    db.flush()
    db.add(
        EvidenceLinkRow(
            claim_id="a1::c1", chunk_id=chunk.chunk_id, source_id="d1", relation="supports", rationale="states 3 days"
        )
    )
    db.flush()
    db.expire_all()
    saved = db.get(AnswerRow, "a1")
    assert saved.status == "resolved"
    assert saved.claims[0].status == "unverified"
    assert saved.claims[0].evidence_links[0].relation == "supports"
    assert saved.citations[0].chunk_id == "d1::chunk_000"


def test_deleting_an_answer_deletes_claims_and_links(db):
    make_doc(db)
    chunk = make_chunk(db)
    answer = AnswerRow(answer_id="a1", question="q?", answer="x", status="insufficient_evidence")
    answer.claims.append(ClaimRow(claim_id="a1::c1", answer_id="a1", text="t"))
    db.add(answer)
    db.flush()
    db.add(EvidenceLinkRow(claim_id="a1::c1", chunk_id=chunk.chunk_id, source_id="d1", relation="context"))
    db.flush()
    db.delete(answer)
    db.flush()
    assert db.scalar(select(func.count()).select_from(EvidenceLinkRow)) == 0
    assert db.scalar(select(func.count()).select_from(ClaimRow)) == 0

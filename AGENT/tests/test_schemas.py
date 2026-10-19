import pytest
from pydantic import ValidationError

from truthguard_agent.schemas import (
    AnswerStatus,
    AuthorityLevel,
    Document,
    DocumentIn,
    FinalAnswer,
    make_chunk_id,
)


def test_missing_metadata_stays_unknown():
    doc = Document(document_id="d1", title="T", content="hello")
    assert doc.version is None
    assert doc.effective_date is None
    assert doc.supersedes_document_id is None
    assert doc.authority_level == AuthorityLevel.UNKNOWN


def test_content_hash_is_deterministic_and_content_sensitive():
    a = Document(document_id="d1", title="T", content="hello")
    b = Document(document_id="d2", title="U", content="hello")
    c = Document(document_id="d1", title="T", content="hello!")
    assert a.content_hash == b.content_hash
    assert a.content_hash != c.content_hash


def test_empty_content_rejected():
    with pytest.raises(ValidationError):
        DocumentIn(document_id="d1", title="T", content="")


def test_chunk_id_is_stable():
    assert make_chunk_id("policy_v1", 3) == "policy_v1::chunk_003"


def test_answer_status_values_match_roadmap():
    assert {s.value for s in AnswerStatus} == {
        "resolved",
        "conflict_unresolved",
        "insufficient_evidence",
        "verification_failed",
    }


def test_final_answer_defaults():
    ans = FinalAnswer(
        answer_id="a1", question="q?", answer="", status=AnswerStatus.INSUFFICIENT_EVIDENCE
    )
    assert ans.citations == [] and ans.conflicts_detected == 0

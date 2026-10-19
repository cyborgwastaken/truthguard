from __future__ import annotations

import hashlib
from datetime import date, datetime, timezone
from typing import List, Optional

from pydantic import BaseModel, Field, model_validator

from .enums import (
    AnswerStatus,
    AuthorityLevel,
    ClaimStatus,
    ConflictStatus,
    EvidenceRelation,
    Severity,
)


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def make_chunk_id(document_id: str, index: int) -> str:
    return "%s::chunk_%03d" % (document_id, index)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class DocumentIn(BaseModel):
    """Ingestion payload. Optional fields stay None when unknown; never invent them."""

    document_id: str = Field(min_length=1)
    title: str
    content: str = Field(min_length=1)
    version: Optional[str] = None
    created_at: Optional[date] = None
    effective_date: Optional[date] = None
    authority_level: AuthorityLevel = AuthorityLevel.UNKNOWN
    supersedes_document_id: Optional[str] = None
    source: Optional[str] = None


class Document(DocumentIn):
    content_hash: str = ""

    @model_validator(mode="after")
    def _fill_hash(self) -> "Document":
        if not self.content_hash:
            self.content_hash = content_hash(self.content)
        return self


class Chunk(BaseModel):
    chunk_id: str
    document_id: str
    index: int
    text: str
    start_offset: int
    end_offset: int


class EvidenceRef(BaseModel):
    source_id: str
    chunk_id: str


class RetrievedPassage(BaseModel):
    chunk: Chunk
    document: Document
    score: Optional[float] = None


class Claim(BaseModel):
    claim_id: str
    answer_id: str
    text: str
    claim_type: str = "factual"
    status: ClaimStatus = ClaimStatus.UNVERIFIED


class EvidenceLink(BaseModel):
    claim_id: str
    chunk_id: str
    source_id: str
    relation: EvidenceRelation
    rationale: str = ""
    verifier_version: str = ""


class Contradiction(BaseModel):
    claim: str
    source_ids: List[str]
    severity: Severity = Severity.MEDIUM
    evidence: List[EvidenceRef] = Field(default_factory=list)


class StalenessFinding(BaseModel):
    source_id: str
    reason: str
    evidence: List[EvidenceRef] = Field(default_factory=list)


class CriticResult(BaseModel):
    contradictions: List[Contradiction] = Field(default_factory=list)
    staleness: List[StalenessFinding] = Field(default_factory=list)
    unsupported_claims: List[str] = Field(default_factory=list)
    needs_resolution: bool = False


class Conflict(BaseModel):
    conflict_id: str
    answer_id: str
    source_ids: List[str]
    status: ConflictStatus = ConflictStatus.UNRESOLVED
    resolution_rationale: Optional[str] = None


class FinalAnswer(BaseModel):
    answer_id: str
    question: str
    answer: str
    status: AnswerStatus
    citations: List[EvidenceRef] = Field(default_factory=list)
    conflicts_detected: int = 0
    resolution_reason: Optional[str] = None
    claims: List[Claim] = Field(default_factory=list)
    evidence_links: List[EvidenceLink] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utcnow)
    model_version: Optional[str] = None
    prompt_version: Optional[str] = None


class QuestionIn(BaseModel):
    question: str = Field(min_length=3, max_length=2000)

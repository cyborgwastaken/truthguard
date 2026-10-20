"""Request and response shapes for the /documents endpoints.

The frontend (T11) mirrors these in TypeScript. Missing metadata is always null, never a made-up value.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator, model_validator
from truthguard_agent.schemas import AuthorityLevel, Chunk, DocumentIn

ID_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9_.-]*$"


def _reject_nul(value: Optional[str]) -> Optional[str]:
    # Postgres text columns cannot hold a NUL character; without this check it would be a 500.
    if value is not None and "\x00" in value:
        raise ValueError("must not contain NUL characters")
    return value


class DocumentCreate(DocumentIn):
    """Upload payload: DocumentIn plus the limits the database and URLs need."""

    document_id: str = Field(min_length=1, max_length=200, pattern=ID_PATTERN)
    title: str = Field(min_length=1, max_length=500)
    content: str = Field(min_length=1, max_length=1_000_000)
    version: Optional[str] = Field(default=None, max_length=64)
    supersedes_document_id: Optional[str] = Field(default=None, max_length=200, pattern=ID_PATTERN)

    @field_validator("title", "content", "version", "source")
    @classmethod
    def _no_nul(cls, value: Optional[str]) -> Optional[str]:
        return _reject_nul(value)

    @model_validator(mode="after")
    def _not_self_superseding(self) -> "DocumentCreate":
        if self.supersedes_document_id == self.document_id:
            raise ValueError("a document cannot supersede itself")
        return self


class DocumentSummary(BaseModel):
    """A document without its text, for lists."""

    document_id: str
    title: str
    version: Optional[str] = None
    created_at: Optional[date] = None
    effective_date: Optional[date] = None
    authority_level: AuthorityLevel
    supersedes_document_id: Optional[str] = None
    source: Optional[str] = None
    content_hash: str
    ingested_at: datetime
    chunk_count: int


class DocumentDetail(DocumentSummary):
    """One document with its full text and its chunks."""

    content: str
    chunks: List[Chunk]

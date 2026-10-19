from __future__ import annotations

from enum import Enum


class AuthorityLevel(str, Enum):
    OFFICIAL = "official"
    DRAFT = "draft"
    INFORMAL = "informal"
    UNKNOWN = "unknown"


class AnswerStatus(str, Enum):
    RESOLVED = "resolved"
    CONFLICT_UNRESOLVED = "conflict_unresolved"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    VERIFICATION_FAILED = "verification_failed"


class ClaimStatus(str, Enum):
    SUPPORTED = "supported"
    CONTRADICTED = "contradicted"
    PARTIALLY_SUPPORTED = "partially_supported"
    UNSUPPORTED = "unsupported"
    UNVERIFIED = "unverified"


class EvidenceRelation(str, Enum):
    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    CONTEXT = "context"


class Severity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ConflictStatus(str, Enum):
    RESOLVED = "resolved"
    UNRESOLVED = "unresolved"

"""The evidence graph of an answer: its claims, the documents they rest on, and how those documents relate.

Nodes are claims and documents. Edges are evidence links (a claim supports, contradicts, or is only given context
by a document), supersession (a newer document replaces an older one, and whether that is in force as of the
question date), and conflicts (two documents the critic found to disagree, settled or not). Everything is derived
from the stored answer record, so a past answer can be drawn again. See DOCS/truthguard_expansion_roadmap.md,
Feature A."""
from __future__ import annotations

from typing import Dict, List, Optional

from pydantic import BaseModel, Field

from .orchestrator import PipelineResult
from .resolver import applicable_supersessions
from .schemas import AnswerStatus, Chunk, Document, RetrievedPassage


class GraphNode(BaseModel):
    id: str
    kind: str  # claim or document
    label: str
    role: str = ""  # claims: current, superseded, conflict_side, unsupported. documents: winner, superseded or empty
    claim_status: Optional[str] = None
    chunk_ids: List[str] = Field(default_factory=list)  # documents: their passages in this answer
    version: Optional[str] = None
    effective_date: Optional[str] = None
    authority_level: Optional[str] = None


class GraphEdge(BaseModel):
    source: str
    target: str
    relation: str  # supports, contradicts, context, supersedes, conflicts
    label: str = ""
    chunk_ids: List[str] = Field(default_factory=list)
    in_force: Optional[bool] = None  # supersedes: does it apply as of the question date?
    settled: Optional[bool] = None  # conflicts: did the rules settle it?


class EvidenceGraph(BaseModel):
    answer_id: str
    as_of: str
    nodes: List[GraphNode]
    edges: List[GraphEdge]


def _passages(result: PipelineResult) -> List[RetrievedPassage]:
    """Rebuild passages from the stored views so the resolver's own supersession rules can be reused."""
    out = []
    for v in result.verification.passages:
        document = Document(document_id=v.document_id, title=v.title, content=v.text or "-", version=v.version,
                            effective_date=v.effective_date, authority_level=v.authority_level,
                            supersedes_document_id=v.supersedes_document_id)
        chunk = Chunk(chunk_id=v.chunk_id, document_id=v.document_id, index=0, text=v.text or "-", start_offset=0,
                      end_offset=len(v.text or "-"))
        out.append(RetrievedPassage(chunk=chunk, document=document, score=v.score))
    return out


def build_evidence_graph(result: PipelineResult) -> EvidenceGraph:
    answer, check = result.answer, result.verification
    scope = {p.document_id: p for p in check.passages if p.in_scope}
    chunks_of: Dict[str, List[str]] = {}
    for p in check.passages:
        if p.in_scope:
            chunks_of.setdefault(p.document_id, []).append(p.chunk_id)
    document_of = {p.chunk_id: p.document_id for p in check.passages}

    nodes: List[GraphNode] = []
    for claim in answer.claims:
        nodes.append(GraphNode(id=claim.claim_id, kind="claim", label=claim.text,
                               role=check.claim_roles.get(claim.claim_id, ""), claim_status=claim.status.value))
    cited_docs = {document_of[link.chunk_id] for link in answer.evidence_links if link.chunk_id in document_of}
    in_graph = set(cited_docs)
    for conflict in check.conflicts:
        in_graph |= set(conflict.source_ids) | set(conflict.winner_source_ids)
    edges: List[GraphEdge] = []

    applicable = applicable_supersessions(_passages(result), check.as_of)
    for target, superseders in applicable.items():
        if target in scope and any(s in scope for s in superseders):
            in_graph |= {target} | {s for s in superseders if s in scope}
    for doc_id in sorted(in_graph):
        p = scope.get(doc_id)
        if p is None:
            continue
        role = "winner" if doc_id in check.winning_source_ids else "superseded" if doc_id in check.stale_source_ids else ""
        nodes.append(GraphNode(id=doc_id, kind="document", label=p.title, role=role, chunk_ids=chunks_of.get(doc_id, []),
                               version=p.version, effective_date=p.effective_date.isoformat() if p.effective_date else None,
                               authority_level=p.authority_level.value))

    merged: Dict[tuple, GraphEdge] = {}
    for link in answer.evidence_links:
        doc = document_of.get(link.chunk_id)
        if doc is None:
            continue
        key = (link.claim_id, doc, link.relation.value)
        edge = merged.setdefault(key, GraphEdge(source=link.claim_id, target=doc, relation=link.relation.value,
                                                label=link.rationale if link.relation.value == "contradicts" else ""))
        if link.chunk_id not in edge.chunk_ids:
            edge.chunk_ids.append(link.chunk_id)
    edges.extend(merged.values())

    for doc_id in sorted(in_graph & set(scope)):
        target = scope[doc_id].supersedes_document_id
        if target in scope and target in in_graph:
            edges.append(GraphEdge(source=doc_id, target=target, relation="supersedes",
                                   label="supersedes", in_force=target in applicable and doc_id in applicable[target]))

    seen = set()
    for conflict in check.conflicts:
        ids = [s for s in dict.fromkeys(list(conflict.source_ids) + list(conflict.winner_source_ids)) if s in scope]
        for i, a in enumerate(ids):
            for b in ids[i + 1:]:
                if (a, b, conflict.claim) in seen:
                    continue
                seen.add((a, b, conflict.claim))
                edges.append(GraphEdge(source=a, target=b, relation="conflicts", label=conflict.claim,
                                       settled=conflict.status == AnswerStatus.RESOLVED))
    return EvidenceGraph(answer_id=answer.answer_id, as_of=check.as_of.isoformat(), nodes=nodes, edges=edges)

"""Run the benchmark: the same cases through three setups, every result recorded.

  baseline    plain RAG: search and answer, no checking (answer_baseline)
  rag_critic  the full pipeline with the critic but without the resolver (answer_question, use_resolver=False)
  full        the full pipeline (answer_question)

"rag_critic" and "full" send identical prompts to the model, so with a CachingLLM in cache mode the second one
costs no extra model calls. A rate-limit failure is retried; any other exception is recorded as a failed check
and the run goes on."""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional, Sequence

from pydantic import BaseModel, Field

from ..baseline import answer_baseline
from ..llm import LLMClient
from ..orchestrator import answer_question
from ..retriever import PassageStore, retrieve
from ..schemas import AnswerStatus
from .cases import BenchmarkCase, dataset_version
from .metrics import CONFIG_LABELS, CONFIGS, CaseResult, Metric, compute_metrics, consistency

RESULTS_DIR = Path(__file__).resolve().parents[2] / "datasets" / "benchmark" / "results"

# (config, case_id, repeat) -> the model client to use for that run
LLMFactory = Callable[[str, str, int], LLMClient]


class BenchmarkRun(BaseModel):
    run_id: str
    created_at: datetime
    dataset_version: str
    settings: Dict[str, object] = Field(default_factory=dict)
    config_labels: Dict[str, str] = Field(default_factory=lambda: dict(CONFIG_LABELS))
    cases: List[BenchmarkCase]
    results: List[CaseResult]
    metrics: Dict[str, Dict[str, Metric]]
    consistency: Dict[str, Dict[str, float]] = Field(default_factory=dict)


def _unique(items: Iterable[str]) -> List[str]:
    return list(dict.fromkeys(items))


def _is_rate_limit(reason: Optional[str]) -> bool:
    return bool(reason) and ("429" in reason or "rate limit" in reason.lower())


def run_case(
    config: str,
    case: BenchmarkCase,
    store: PassageStore,
    llm: LLMClient,
    k: int = 8,
    repeat: int = 1,
) -> CaseResult:
    started = time.monotonic()
    answer_id = "bench-%s-%s-r%d" % (case.case_id, config, repeat)
    try:
        if config == "baseline":
            retrieved = _unique(p.document.document_id for p in retrieve(case.question, store, k=k, expand_related=False))
            final = answer_baseline(case.question, store, llm, k=k, answer_id=answer_id)
            result = CaseResult(
                case_id=case.case_id, config=config, repeat=repeat, status=final.status, answer=final.answer,
                answer_id=answer_id, citation_document_ids=_unique(c.source_id for c in final.citations),
                retrieved_document_ids=retrieved, conflicts_detected=final.conflicts_detected,
                claims_total=len(final.claims), claims_supported=0,
                failure_reason=final.resolution_reason if final.status == AnswerStatus.VERIFICATION_FAILED else None,
            )
        else:
            run = answer_question(case.question, store, llm, case.as_of, k=k, answer_id=answer_id,
                                  use_resolver=(config == "full"))
            final, check = run.answer, run.verification
            result = CaseResult(
                case_id=case.case_id, config=config, repeat=repeat, status=final.status, answer=final.answer,
                answer_id=answer_id, citation_document_ids=_unique(c.source_id for c in final.citations),
                retrieved_document_ids=_unique(p.document_id for p in check.passages),
                winner_document_ids=list(check.winning_source_ids),
                stale_document_ids=_unique(s.source_id for s in check.stale),
                conflicts_detected=final.conflicts_detected, claims_total=len(final.claims),
                claims_supported=len(final.claims) - len(check.unsupported),
                failure_reason=check.failure_reason,
            )
    except Exception as error:  # a crash is a failed check, never a stopped run
        result = CaseResult(case_id=case.case_id, config=config, repeat=repeat, status=AnswerStatus.VERIFICATION_FAILED,
                            failure_reason="exception: %s: %s" % (type(error).__name__, error))
    result.latency_ms = int((time.monotonic() - started) * 1000)
    return result


def run_benchmark(
    cases: Sequence[BenchmarkCase],
    store: PassageStore,
    llm_factory: LLMFactory,
    configs: Sequence[str] = CONFIGS,
    repeats: int = 1,
    k: int = 8,
    retries: int = 2,
    backoff_s: float = 20.0,
    settings: Optional[Dict[str, object]] = None,
    progress: Optional[Callable[[CaseResult], None]] = None,
) -> BenchmarkRun:
    results: List[CaseResult] = []
    for repeat in range(1, repeats + 1):
        for case in cases:
            for config in configs:
                llm = llm_factory(config, case.case_id, repeat)
                result = run_case(config, case, store, llm, k=k, repeat=repeat)
                attempt = 0
                while result.status == AnswerStatus.VERIFICATION_FAILED and _is_rate_limit(result.failure_reason) and attempt < retries:
                    attempt += 1
                    time.sleep(backoff_s * attempt)
                    result = run_case(config, case, store, llm, k=k, repeat=repeat)
                results.append(result)
                if progress:
                    progress(result)
    now = datetime.now(timezone.utc)
    return BenchmarkRun(
        run_id=now.strftime("%Y%m%dT%H%M%SZ"),
        created_at=now,
        dataset_version=dataset_version(),
        settings={"k": k, "repeats": repeats, "configs": list(configs), **(settings or {})},
        cases=list(cases),
        results=results,
        metrics={c: compute_metrics(c, list(cases), [r for r in results if r.config == c]) for c in configs},
        consistency={c: consistency([r for r in results if r.config == c]) for c in configs},
    )


def save_run(run: BenchmarkRun, directory: Path = RESULTS_DIR) -> Path:
    """Write run-<id>.json and also latest.json, which the dashboard shows."""
    directory.mkdir(parents=True, exist_ok=True)
    text = run.model_dump_json(indent=1)
    path = directory / ("run-%s.json" % run.run_id)
    path.write_text(text, encoding="utf-8")
    (directory / "latest.json").write_text(text, encoding="utf-8")
    return path


def load_run(path: Path) -> BenchmarkRun:
    return BenchmarkRun.model_validate(json.loads(Path(path).read_text(encoding="utf-8")))

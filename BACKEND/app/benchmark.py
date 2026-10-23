"""Run the benchmark against the real database and the real model.

  cd BACKEND
  python -m app.benchmark                      # all 18 cases, three setups, one repeat
  python -m app.benchmark --repeats 3          # repeat each case to see how stable the answers are
  python -m app.benchmark --cases C01,C05,C08  # only some cases
  python -m app.benchmark --mode record        # always call the model and record every reply

Needs the database with the sample documents (python3 OPS/load_fixtures.py) and GROQ_API_KEY. Model replies
are cached next to the results, so an interrupted run resumes without repeating calls, and "rag_critic" and
"full" share the same replies. Each extra repeat uses its own cache file, so repeats really are independent.
Results go to AGENT/datasets/benchmark/results/ (run-<id>.json and latest.json)."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from truthguard_agent.evaluation.cases import load_cases
from truthguard_agent.evaluation.metrics import CONFIGS, CaseResult
from truthguard_agent.evaluation.runner import RESULTS_DIR, run_benchmark, save_run
from truthguard_agent.llm import CachingLLM, GroqLLM

from .config import settings
from .db.search import PostgresPassageStore
from .db.session import SessionLocal

BENCH_CACHE = RESULTS_DIR / "model-replies.jsonl"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Run the TruthGuard benchmark.")
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--configs", default=",".join(CONFIGS))
    parser.add_argument("--cases", default="", help="comma-separated case ids; default all")
    parser.add_argument("--mode", choices=["cache", "record", "live", "replay"], default="cache")
    parser.add_argument("--k", type=int, default=8)
    args = parser.parse_args(argv)

    if args.mode != "replay" and not settings.groq_api_key:
        print("No language-model key. Set GROQ_API_KEY (environment or BACKEND/.env), or use --mode replay "
              "with recorded replies.", file=sys.stderr)
        return 2
    cases = load_cases()
    if args.cases:
        wanted = {c.strip() for c in args.cases.split(",")}
        cases = [c for c in cases if c.case_id in wanted]
        if len(cases) != len(wanted):
            print("Unknown case id in --cases.", file=sys.stderr)
            return 2
    configs = [c.strip() for c in args.configs.split(",")]

    clients = {}

    def factory(config: str, case_id: str, repeat: int):
        if repeat not in clients:
            inner = None if args.mode == "replay" else GroqLLM(
                settings.llm_model, api_key=settings.groq_api_key, temperature=settings.llm_temperature)
            cache = BENCH_CACHE if repeat == 1 else BENCH_CACHE.with_name("model-replies-r%d.jsonl" % repeat)
            clients[repeat] = CachingLLM(inner, cache, args.mode, model_name=settings.llm_model)
        return clients[repeat]

    def progress(r: CaseResult) -> None:
        print("%-4s %-10s r%d  %-22s %5.1fs  %s" % (
            r.case_id, r.config, r.repeat, r.status.value, r.latency_ms / 1000, r.failure_reason or ""), flush=True)

    with SessionLocal() as session:
        run = run_benchmark(
            cases, PostgresPassageStore(session), factory, configs=configs, repeats=args.repeats, k=args.k,
            settings={"model": settings.llm_model, "temperature": settings.llm_temperature, "mode": args.mode},
            progress=progress,
        )
    path = save_run(run)
    print("\nSaved %s\n" % path)
    for config in configs:
        m = run.metrics[config]
        print("%-11s status accuracy %s | failed checks %s | key facts %s | outdated value %s | false conflicts %s" % (
            config, *("n/a" if m[k].value is None else "%d/%d" % (m[k].numerator, m[k].denominator) for k in (
                "status_accuracy", "verification_failed_rate", "key_fact_accuracy", "outdated_value_rate", "false_conflict_rate"))))
    return 0


if __name__ == "__main__":
    sys.exit(main())

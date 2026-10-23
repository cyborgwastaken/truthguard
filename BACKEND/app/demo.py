"""Rehearse the demo against the real model, and record its replies for the offline fallback.

  cd BACKEND
  python -m app.demo                 # run the demo questions once, record every reply, compare with the labels
  python -m app.demo --repeats 3     # run each question 3 times to see which ones are stable
  python -m app.demo --cases C01,C05 # only some questions

Needs the database with the sample documents (python3 OPS/load_fixtures.py) and GROQ_API_KEY. The replies are
stored in AGENT/datasets/recorded/replies.jsonl (fictional documents only), so the demo can run without the
network: start the backend with TRUTHGUARD_LLM_MODE=replay. A replayed answer is labelled "Replayed recording"
on screen. Choose the most stable question of each kind for the live demo, and say in the demo when a
recording is used."""
from __future__ import annotations

import argparse
import sys
import time
from datetime import date

from truthguard_agent.evaluation.cases import load_cases
from truthguard_agent.llm import CachingLLM, GroqLLM
from truthguard_agent.orchestrator import answer_question

from .config import settings
from .db.search import PostgresPassageStore
from .db.session import SessionLocal

# The situations the demo shows, with alternatives so the most stable one can be picked.
DEMO_CASES = ["C01", "C02", "C05", "C06", "C07", "C08", "C09", "C10", "C11", "C13"]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Rehearse the demo questions with the real model.")
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--cases", default=",".join(DEMO_CASES))
    parser.add_argument("--mode", choices=["record", "cache", "live"], default="record")
    args = parser.parse_args(argv)

    if not settings.groq_api_key:
        print("No language-model key. Set GROQ_API_KEY (environment or BACKEND/.env).", file=sys.stderr)
        return 2
    wanted = [c.strip() for c in args.cases.split(",") if c.strip()]
    by_id = {c.case_id: c for c in load_cases()}
    if any(w not in by_id for w in wanted):
        print("Unknown case id in --cases.", file=sys.stderr)
        return 2

    inner = GroqLLM(settings.llm_model, api_key=settings.groq_api_key, temperature=settings.llm_temperature)
    recorder = CachingLLM(inner, settings.llm_cache_path, args.mode)
    print("model %s, temperature %s, mode %s\n" % (settings.llm_model, settings.llm_temperature, args.mode))
    problems = 0
    for case_id in wanted:
        case = by_id[case_id]
        got = []
        seconds = []
        for repeat in range(args.repeats):
            # the first run is recorded; extra runs call the model again so that stability is really measured
            llm = recorder if repeat == 0 else inner
            started = time.monotonic()
            with SessionLocal() as session:
                result = answer_question(case.question, PostgresPassageStore(session), llm, date.today())
            seconds.append(time.monotonic() - started)
            got.append(result.answer.status.value)
            if result.answer.status != case.expected_status:
                problems += 1
        verdict = "OK " if all(g == case.expected_status.value for g in got) else "BAD"
        print("%s %-4s expected %-21s got %-45s %5.1fs  %s" % (
            verdict, case_id, case.expected_status.value, ", ".join(got), sum(seconds) / len(seconds), case.question))
    print("\n%s" % ("All answers have the expected status." if not problems else
                    "%d answer(s) differ from the expected status: prefer other questions for the demo." % problems))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())

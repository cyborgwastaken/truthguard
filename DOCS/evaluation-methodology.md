# Evaluation Methodology

How TruthGuard is measured, what the numbers mean, and what they cannot show. The results themselves are on the
**Benchmark** page of the app and in `AGENT/datasets/benchmark/results/latest.json`; this page does not repeat
numbers, so it cannot go out of date.

## The question being tested

Does checking an answer against its sources (finding conflicts, spotting outdated documents, applying explicit
rules, abstaining) give better answers than a plain search-and-answer system, and where does it not?

## The three setups

All three use the same documents, the same retrieval settings (top 8 passages) and the same language model with the
same temperature (0).

| Setup | What it does | Code |
|---|---|---|
| **Plain RAG** (baseline) | Search, then ask the model to answer from the passages. No checking. Plain search only: it is not shown the documents that supersede or are superseded by what it found, because that expansion is part of what TruthGuard adds. | `answer_baseline` |
| **RAG + critic** | The full pipeline with the critic, but no resolver: the critic's findings are shown, nothing decides between sources, so any contradiction that bears on the question is an unresolved conflict. | `answer_question(use_resolver=False)` |
| **Full TruthGuard** | Critic plus the deterministic resolver (explicit supersession, effective dates, authority). | `answer_question` |

The baseline uses the **same answer-drafting prompt** as the full system, which already tells the model to report
disagreement between passages. So the comparison isolates what the critic and the resolver add, not what prompt
wording adds.

"RAG + critic" and "full" send identical prompts to the model, so they share the same recorded replies; they differ
only in the deterministic resolver step.

## The dataset (v1)

18 labeled questions over 26 fictional documents (`AGENT/datasets/benchmark/cases_v1.json`, derived from the label
table in `AGENT/datasets/fixtures/README.md`; a test keeps the two in step).

| Kind | Cases | The right answer |
|---|---|---|
| Superseded policy | C01 to C04 | `resolved`, with the current value, and the old document reported stale |
| Equally official sources disagree | C05 to C07 | `conflict_unresolved`, both positions shown |
| Not in the documents | C08 to C10 | `insufficient_evidence` |
| Similar but not a conflict (hard negatives) | C11, C12 | `resolved`; no conflict |
| Unapproved draft (trap) | C13, C14 | `resolved`, from the official document |
| One clear source | C15 to C17 | `resolved` |
| Informal note that does not contradict | C18 | `resolved` |

Every question is judged as of 2026-10-20, a date after every document's effective date, so all amendments are in force.

## The metrics

Each is a ratio. The page shows the numerator and denominator next to the percentage, so a number can always be traced
to cases. "n/a" means the setup cannot produce that data (for example the baseline never names a winning source);
it is never shown as 0.

| Metric | Definition | Better |
|---|---|---|
| Status accuracy | answers whose status equals the expected status / all answers | higher |
| Key facts present | answers containing every expected fact / answers to cases that have expected facts | higher |
| States the outdated value | answers containing a superseded value / answers to superseded cases | lower |
| False conflicts | cases that should be resolved but were answered `conflict_unresolved` / cases that should be resolved | lower |
| Flags real conflicts | real-conflict cases answered `conflict_unresolved` / real-conflict cases | higher |
| Abstains when it should | no-evidence cases answered `insufficient_evidence` / no-evidence cases | higher |
| Abstentions that were right | `insufficient_evidence` answers on no-evidence cases / all `insufficient_evidence` answers | higher |
| Picks the right source | cases whose winning documents equal the expected winners / cases with an expected winner | higher |
| Spots outdated sources | cases where every expected superseded document is reported stale / cases with a superseded document | higher |
| Retrieval recall | relevant documents retrieved / relevant documents | higher |
| Citations on relevant documents | citations pointing at a relevant document / all citations | higher |
| Claims backed by their passages | claims the critic judged supported / all drafted claims (critic setups only) | higher |
| Failed checks | answers with status `verification_failed` / all answers | lower |
| Mean time, p95 | wall-clock time per answer | lower |

"Key facts" and "outdated value" are case-insensitive substring checks written down in the dataset. A status can be right
while the fact is wrong (the baseline answers "resolved" with the old figure), which is why both are reported.

**A failed check is never counted as a correct answer or a correct abstention.** A rate-limit error is retried
(up to twice, with a pause); any other failure is recorded as `verification_failed` and the run goes on.

## How to run it

```bash
cd BACKEND
python -m app.benchmark                 # 18 cases x 3 setups, one run each
python -m app.benchmark --repeats 3     # repeat to see how stable each answer is
python -m app.benchmark --cases C01,C05 # a subset
```

Model replies are cached in `AGENT/datasets/benchmark/results/model-replies*.jsonl`, so an interrupted run resumes and the
results can be reproduced from the cache (`--mode replay`). With `--repeats N`, each extra repeat uses its own cache file,
so the repeats are independent calls. Every run writes `run-<id>.json` (settings, every per-case result, every metric with
its numerator and denominator) and updates `latest.json`.

## What the numbers do not show

- **It is small and invented.** 18 questions over fictional documents that the system's author also wrote. The
  documents are cleaner than real ones. The numbers show how the setups differ here, not how any would score elsewhere.
- **One model, one temperature.** Answers can vary from run to run; repeat runs and the stability figure show how much.
- **The critic is only as good as the model's judgement.** Whether two passages truly contradict is a model decision.
  The rules after it are deterministic and tested; the judgement before them is measured here, not guaranteed.
- **Retrieval never abstains.** Search returns the best passages even when none answer the question, so "insufficient
  evidence" depends on the model finding nothing to cite and on the support check. The abstention metrics measure that.
- **Key-fact checks are substring matches.** An answer can contain the right number in a wrong sentence, or phrase it in a
  way the check does not know. Read the failed cases on the page, not just the percentages.
- **No claim of statistical significance.** With 18 cases, a difference of one case is 5.6 percentage points.

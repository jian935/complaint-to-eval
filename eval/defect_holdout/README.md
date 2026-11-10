# Defect hold-out evaluation

**Labels are MODEL-generated (`annotator: model`), never human.**
Every number here means "how well the deterministic rules agree with one careful
reader", not human accuracy. `accepted_cases` is still 0.

Six **pairwise disjoint** splits exist. Each round is an error-analysis loop: read
the misses/false positives of set *N*, change something on principle, then measure
on a **fresh** set *N+1* that no change has ever seen. Numbers are never
overwritten, so anyone can check whether a result came from tuning.

## The headline, in two lines

- **Mode-level** (right issue *and* right bucket): precision ≈ 0.71–0.77,
  recall ≈ 0.56–0.80 across clean splits.
- **In practice this is a crash detector.** On the newest clean split it found
  13 of 15 crashes and **2 of 12 non-crash defects**. Everything except
  `crash_or_error` is unproven.

## Round table (mode-level)

| Round | Change | Measured on | micro P | micro R |
| --- | --- | --- | ---: | ---: |
| 1 | first measurement, untuned | A (40) | 0.815 | 0.667 |
| 2 | natural-phrase signals from A; start-of-word boundary | B (40, fresh) | 0.917 | 0.846 |
| 3 | — (clean confirmation of round 2) | **C (39, clean)** | **0.711** | **0.771** |
| 4 | blank quoted code before matching | **D (40, fresh)** | **0.774** | **0.649** |
| 5 | remove bare topic nouns | **E (40, fresh)** | **0.710** | **0.629** |
| 6 | add `logic_or_validation`, move boundary cases out of data/config | **F (32, fresh)** | **0.714** | **0.556** |

Round 2's 0.917/0.846 was the optimistic outlier; Round 3 exists to prove that.
Rounds 3–6 sit in a narrow band: **phrase-level changes no longer move precision.**

After round 6 the labels of C/D/E were rewritten (the boundary cases moved to the
new mode), so re-scoring them gives 0.824 / 0.829 / 0.743 — but those labels were
edited with those sets in view. **F is the only clean post-change number.**

## Baselines (the check that makes the numbers mean something)

These corpora are defect-heavy, so a trivial rule scores well. On set F:

| Rule | Level | Precision | Recall |
| --- | --- | ---: | ---: |
| Always flag every record | record | 0.844 | **1.000** |
| Always predict `crash_or_error` | mode | 0.469 | 0.556 |
| **This engine** | record | **0.944** | 0.630 |
| **This engine** | mode | **0.714** | 0.556 |

Read that carefully: at record level the engine buys precision (0.944 vs 0.844) by
giving up recall — **"flag everything" is not beaten on recall.** At mode level the
engine does beat the trivial baseline on precision at equal recall, which is the
one place it clearly adds value.

## Record level, which is the fairer view for a triage tool

Mode-level scoring punishes "right issue, wrong bucket" twice (a false positive
*and* a miss). A triage tool is first judged on whether it flags the right report.

| Set | Records | Detection P | Detection R | Clean records wrongly flagged |
| --- | ---: | ---: | ---: | --- |
| C | 39 | 0.903 | 0.800 | 3 of 4 |
| D | 40 | 1.000 | 0.919 | 0 of 3 |
| E | 40 | 0.906 | 0.829 | 3 of 5 |
| **F** | 32 | **0.944** | **0.630** | 1 of 5 |

The last column matters: across the sets, **7 of 17 clean records were flagged**.
Feature proposals and vendor pitches that mention technical words get labelled as
defects. That is the tool's most visible failure mode.

## Round 6 — adding `logic_or_validation`

Exit-code bugs, type coercion, accepted-invalid-input, duplicate execution and
malformed constructed output were being forced into `config_or_env` or
`data_integrity`, polluting both. A tenth mode was added and 18 boundary cases
across A–E were moved into it. Every move is listed with its old and new mode in
[`migrations.md`](migrations.md) — a label edit that cannot be audited is worse than
no label edit.

**Result on the fresh set F: 0 of 5 logic cases caught.** The real phrasings were
"divergent control flow", "stale computed range", "stringified to Python repr",
"overwrites action_name", "accepts a trailing newline" — none of which the general
signals anticipated. The mode is conceptually right and measurably useless so far.

This is the sixth time a phrase-level change produced no generalisation gain. The
conclusion is not "try harder with phrases"; it is that **a topic-word + fault-word
co-occurrence model is the only design that can express what the reader is doing.**

## Method

- **Split** (`scripts/split_holdout.py` for A, `split_holdout_b/c/d.py`, and
  `scripts/draw_holdout.py` for later sets): exclude every id used earlier, sort
  the rest by `md5("<salt>:<record_id>")`, take up to N per corpus. Pools that are
  too small are **capped and reported, never padded** — set C's dify arm is 15,
  and set F is 32 records because aider's derive pool ran out.
- **Labels** (`labels_holdout*.jsonl`): multi-label per record (`modes: []` =
  feature request / promo / off-topic). Written by reading the issue text only;
  **engine predictions were not consulted** (easy to guarantee — v0.1 produced
  ~0 candidates on this corpus).
- **Score** (`scripts/eval_defects_holdout.py`): per-mode precision/recall, micro
  average, record-level detection, Wilson intervals, the full miss and
  false-positive lists, and the two trivial baselines.
- **Corpus** (`.local/corpus/`, gitignored, never published): aider 136 issues
  (Apache-2.0), dify 136 issues (Apache-2.0 with additional conditions). dify was
  expanded from 47 before set D, otherwise every later split would have been
  aider-only and inflated by crash reports.

Reproduce (needs the local corpus snapshot; labels and splits are committed):

```bash
python scripts/eval_defects_holdout.py --holdout .local/corpus/holdoutF.jsonl \
    --labels eval/defect_holdout/labels_holdout_f.jsonl --out out/eval_defects_f.json
```

## Per-mode detail on set F (clean)

| Mode | Precision | Recall | TP | pred | label |
| --- | ---: | ---: | ---: | ---: | ---: |
| `crash_or_error` | 1.00 | 0.87 | 13 | 13 | 15 |
| `data_integrity` | 0.33 | 1.00 | 1 | 3 | 1 |
| `logic_or_validation` | – | **0.00** | 0 | 0 | 5 |
| `security` | 0.50 | 1.00 | 1 | 2 | 1 |
| `ui_or_ux` | 0.00 | **0.00** | 0 | 2 | 4 |
| `config_or_env` | 0.00 | **0.00** | 0 | 1 | 1 |

Nine of the ten modes have ten or fewer labelled instances in any single split.
That is the other honest limit: **most modes are simply too rare here to measure.**

## Limits (read before quoting)

1. **Model labels, one reader, one pass.** No inter-annotator agreement exists, so
   "precision" means agreement with this reader. A second reader would move these
   numbers by an unknown amount.
2. **n = 32–40 per set, two repos.** Wilson intervals span ±0.12–0.18.
3. **Domain.** aider and dify issue trackers — software defect reports, not user
   complaints in general. That is exactly why the project pivoted from the
   LLM-behaviour taxonomy.
4. **Rare modes unmeasurable.** Nine modes have ≤10 labels per split.
5. **`accepted_cases` is 0.** Nothing here is a human-accepted eval set, and no fix
   rate, resolution time or business impact is claimed anywhere.

## Backlog (design-level, not more phrases)

- **Co-occurrence model**: require a topic token *and* a fault token in the same
  clause. Every false positive since round 3 has been a topic word in neutral
  prose; every miss has been a fault expressed in vocabulary the list lacks.
- **Sentence-level, not clause-level**: markdown issue templates split clauses at
  every newline, which cuts a claim in half before it can be matched.
- **A human label pass** on one split, so at least one number is not
  model-vs-model.

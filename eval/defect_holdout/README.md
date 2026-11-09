# Defect hold-out evaluation

**Labels are MODEL-generated (`annotator: model`), never human.**
Read every number here as "how well do the deterministic rules agree with one
careful reader", not as a human-accuracy result.

## Method

- **Split** (`scripts/split_holdout.py`): sort each corpus by `md5(record_id)`,
  take the first N as hold-out — aider 24 + dify 16 = **40 records**; the rest is
  dev. Deterministic, reproducible from `eval/defect_holdout/partitions.json`.
- **Labels** (`labels_holdout.jsonl`): one row per record, multi-label
  (`modes: [...]`, empty = not a defect report / feature / promo). Written by
  reading the issue text only — **engine predictions were not consulted**.
- **Score** (`scripts/eval_defects_holdout.py`): per-mode precision/recall and a
  micro average, with 95% Wilson intervals; misses and false positives listed.

Reproduce:

```bash
python scripts/split_holdout.py
python scripts/eval_defects_holdout.py
```

## Results (40 hold-out records, MODEL labels)

| Metric | Value | 95% Wilson |
| --- | ---: | --- |
| **micro precision** | **0.815** | [0.633, 0.918] |
| **micro recall** | **0.667** | [0.496, 0.802] |

27 engine candidates · 33 label-positive instances · 22 true positives.

| Mode | Precision | Recall | TP | pred | label |
| --- | ---: | ---: | ---: | ---: | ---: |
| `crash_or_error` | 0.95 | 1.00 | 21 | 22 | 21 |
| `docs` | 1.00 | 0.50 | 1 | 1 | 2 |
| `data_integrity` | – | **0.00** | 0 | 0 | 5 |
| `ui_or_ux` | 0.00 | **0.00** | 0 | 1 | 3 |
| `regression` | 0.00 | **0.00** | 0 | 1 | 1 |
| `config_or_env` | 0.00 | 0.00 | 0 | 1 | 1 |
| `i18n_or_locale` | 0.00 | – | 0 | 1 | 0 |

## What this actually says (honest)

- **Precision 0.815 is carried by `crash_or_error`** — which is near-trivial on
  aider (79% of that corpus is the auto-crash template). 21 of 22 crash
  predictions are right, and it found all 21 real crashes. That proves template
  detection, not skill.
- **Recall collapses on the modes that matter.** `data_integrity` 0/5,
  `ui_or_ux` 0/3, `regression` 0/1: the natural phrasing of real issues
  ("rejects a valid archive", "pickers hide integer variables", "fails to render",
  "regression in 1.19.0", "deletes files still referenced") does not contain the
  hand-picked signals.
- **Precision is not clean either.** 5 false positives, e.g. `ui_or_ux` fired on
  a feature request, `i18n` fired on a README-gap issue, `regression` fired on a
  functional type bug.

## Limits (read before quoting)

1. **Signals were authored with visibility into both corpora** (I read aider and
   dify while writing them). So this is optimistic, not a clean generalisation.
2. **Hold-out misses have now been seen.** Any signal change motivated by these
   11 misses would be tuning on the test set; those changes must be validated on
   a *fresh* split, not this one.
3. **n = 40, model labels, two repos.** Wilson intervals are wide; this is a
   directional first estimate.
4. **`accepted_cases` is still 0.** Candidate output is unchanged; nothing here
   is a human-accepted eval set.

## Improvement backlog (next polish pass)

Derive new signals from the **dev** split (not hold-out), for the natural
phrasings that were missed:
- `data_integrity`: "rejects a valid", "deletes ... referenced", "excludes the
  selected", "trailing quote", "cannot be bound to"
- `ui_or_ux`: "pickers hide", "fails to render", "does not render", "clipped",
  "hidden from"
- `regression`: "regression in", "regressed in", "as of <version>"
- `docs`: "document X as", "omits the ... step"

Then re-split with a **new hash seed** so the fresh hold-out was never read, and
re-run this scorer. Publish the new numbers alongside the old ones — do not
overwrite them.

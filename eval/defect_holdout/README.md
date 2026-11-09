# Defect hold-out evaluation

**Labels are MODEL-generated (`annotator: model`), never human.**
Read every number here as "how well the deterministic rules agree with one
careful reader", not as a human-accuracy result. `accepted_cases` is still 0.

Five **pairwise disjoint** splits exist. Each round is a real error-analysis loop:
look at the misses/false positives of set *N*, change the signals on principle,
then measure on a **fresh** set *N+1* that no change has ever seen. Numbers are
never overwritten — the whole lineage stays visible so anyone can check whether a
result came from tuning.

| Round | Change | Measured on | micro P | micro R |
| --- | --- | --- | ---: | ---: |
| 1 | first measurement, untuned | A (40) | 0.815 [0.633, 0.918] | 0.667 [0.496, 0.802] |
| 2 | natural-phrase signals from A's misses; start-of-word boundary | B (40, fresh) | 0.917 [0.782, 0.971] | 0.846 [0.703, 0.928] |
| 3 | — (clean confirmation of round 2) | **C (39, clean)** | **0.711 [0.552, 0.830]** | **0.771 [0.610, 0.879]** |
| 4 | blank quoted code before matching (C's false positives) | **D (40, fresh)** | **0.774 [0.602, 0.886]** | **0.649 [0.488, 0.782]** |
| 5 | remove bare topic nouns, keep fault-shaped phrases (D's false positives) | **E (40, fresh)** | **0.710 [0.534, 0.839]** | **0.629 [0.463, 0.768]** |

**The number to quote is the range over the three uncontaminated sets (C, D, E):
precision ≈ 0.71–0.77, recall ≈ 0.63–0.77.** Round 2's 0.917/0.846 was the
optimistic outlier and must not be quoted alone — that is exactly what Round 3
was for.

## Method

- **Split** (`scripts/split_holdout.py` for A; `split_holdout_b/c/d.py` for the
  rest; `scripts/draw_holdout.py` for any new set): exclude every id used by an
  earlier set, sort the remainder by `md5("<salt>:<record_id>")`, take up to
  N per corpus (aider 24 + dify 16). Pools that are too small are **capped and
  reported, never padded** — set C's dify arm is 15, not 16.
- **Labels** (`labels_holdout*.jsonl`): one row per record, multi-label
  (`modes: [...]`, empty = feature request / promo / off-topic). Written by
  reading the issue text only — **engine predictions were not consulted**, which
  is easy to guarantee here because v0.1 produced ~0 candidates on this corpus.
- **Score** (`scripts/eval_defects_holdout.py`): per-mode precision/recall, a
  micro average, 95% Wilson intervals, and the full miss / false-positive lists.
- **Corpus** (`.local/corpus/`, gitignored, never published): aider 136 issues
  (Apache-2.0), dify 136 issues (MIT). dify was expanded from 47 to 136 before
  set D because A+B+C had exhausted the original pool; without that, D and E
  would have been aider-only and precision would have been dominated by crash
  reports.

Reproduce (needs the local corpus snapshot; the labels and splits are committed):

```bash
python scripts/eval_defects_holdout.py --holdout .local/corpus/holdoutC.jsonl \
    --labels eval/defect_holdout/labels_holdout_c.jsonl --out out/eval_defects_c.json
```

## Round 1 (set A) — the first, untuned measurement

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

Precision was carried by `crash_or_error`, which is near-trivial on aider (79% of
that corpus is one auto-crash template). Recall collapsed on the modes that
matter: the natural phrasing of real issues ("rejects a valid archive", "pickers
hide integer variables", "regression in 1.19.0") was not in the signal list.

## Round 2 (set B) — signals improved, validated on a fresh split

New natural-phrase signals from A's misses (`rejects a valid`, `excludes the
selected`, `trailing quote`, `unexecuted`, `fails to render`, `pickers hide`,
`does not render`, `regression in`) plus a start-of-word boundary so prefix
signals catch inflections. Set B drawn with salt `v2`, A excluded, labelled fresh.

Result: **0.917 / 0.846**. Per-mode: `crash` 0.96/1.00 · `i18n` 1.00/1.00 ·
`ui` 1.00/0.67 · `config` 1.00/0.50 · `data_integrity` 0.67/0.33 · `security`
0/– (one false positive).

**Caveat that mattered:** one fix (the start-of-word boundary) was changed after
B's first run showed `data_integrity` missing "silently truncates". So B's
`data_integrity` recall is mildly optimistic, and 0.917/0.846 is *not* a clean
generalisation. Round 3 existed to test that.

## Round 3 (set C) — clean, and much lower

Set C: salt `v3`, A and B excluded. dify's pool was exhausted, so C is
**39 records** (aider 24 + dify 15) — capped, not padded.

| Metric | Value | 95% Wilson |
| --- | ---: | --- |
| micro precision | **0.711** | [0.552, 0.830] |
| micro recall | **0.771** | [0.610, 0.879] |

So Round 2's 0.846 recall was indeed optimistic; the clean figure is ~0.71/0.77.
This is the round that proves the loop is worth running: without C the project
would have published a number ~0.15 too high.

## Round 4 (set D) — blank quoted code before matching

C's false positives shared one cause: signals fired **inside quoted code** —
`timeout=120` in a repro snippet, `ValueError` inside `except`, `high-performance
models`, "doc translation". A defect report quotes code; a quoted exception name
is not a reported crash. Fix: `blank_code()` replaces fenced blocks and inline
code spans with **spaces of the same length**, so matching ignores code while
every offset (and therefore every evidence quote) still points at the original
text.

Principle-based, not dataset-specific — and validated on the fresh **set D**
(salt `v4`, A/B/C excluded, 40 records).

| Metric | Value | 95% Wilson |
| --- | ---: | --- |
| micro precision | **0.774** | [0.602, 0.886] |
| micro recall | **0.649** | [0.488, 0.782] |

Per-mode: `crash` **1.00**/0.90 (blanking removed every crash false positive) ·
`data_integrity` 1.00/**0.14** · `config` 1.00/0.33 · `ui` 0.67/0.67 ·
`security` 0.33/1.00 · `i18n` 0/– · `performance` 0/– · `regression` 0/–.

**The trade-off is real and worth stating:** blanking also hid two crash
signatures that appear *only* inside code (`'str' object has no attribute 'get'`,
`fail with 500`), which is why crash recall fell 1.00 → 0.90 while crash
precision rose 0.94 → 1.00. We accepted that: a wrong crash claim is worse than
a missed one for a triage tool.

On C itself (re-run after the fix, so no longer clean) precision moved
0.711 → 0.794 with recall unchanged — consistent with the D result.

## Round 5 (set E) — enforce the project's own "no bare nouns" rule

D's false positives exposed a **discipline violation** rather than a tuning
issue: `defects.py` states "No bare nouns; only specific multi-word signals", yet
the rules contained `security`, `locale`, `layout`, `sidebar`, `hover`,
`tooltip`, `chevron`, `performance`, `latency`. Those are *topics*, not defect
claims, so they fired on "security concerns", "delivery, security, and migration
requirements", "doc translation", "high-performance models", "a regression test
should be added".

Fix: bare topic nouns removed; only fault-shaped phrases remain
(`path traversal`, `outside the repository`, `does not render`,
`falls back to english`, `points in the wrong direction`, `stale`, …).

Validated on the fresh **set E** (salt `v5`, A–D excluded, 40 records).

| Metric | Value | 95% Wilson |
| --- | ---: | --- |
| micro precision | **0.710** | [0.534, 0.839] |
| micro recall | **0.629** | [0.463, 0.768] |

Per-mode: `crash` 0.95/0.90 · `i18n` 1.00/1.00 · `security` 1.00/0.50 ·
`performance` 0.25/1.00 · `data_integrity` 0/7 · `ui` 0/2 · `config` 0/1.

**Honest read: precision did not improve.** On E, the removed nouns were carrying
real recall, and the fault-shaped replacements did not pick up the slack. C, D and
E together bound the current classifier at roughly **P 0.71–0.77 / R 0.63–0.77**,
and further rounds of "fix the false positives I just saw" are no longer producing
gains — the next improvement has to come from a different design, not more phrases.

## What the five rounds actually established

1. **Only `crash_or_error` is validated.** It sits at 0.95–1.00 precision across
   C/D/E. Everything else is an aspiration: `data_integrity` recall is 0.00–0.14
   on natural dify prose, `ui` 0.00–0.67, `config` 0.00–0.33.
2. **On aider, crash detection is nearly free** and inflates every headline
   number. Any split that is mostly aider will look good for structural reasons.
3. **Signal-phrase iteration has plateaued.** Rounds 2→5 added phrases, removed
   phrases and stripped code; precision stayed 0.71–0.77. The bottleneck is the
   model itself — "topic word + fault word in the same clause" is what a reader
   does, and a flat phrase list cannot express it.
4. **The loop is honest but not free:** each round that reads a set's errors
   contaminates that set forever. That is why five disjoint splits were needed to
   produce three quotable numbers.

## Limits (read before quoting)

1. **Model labels.** One reader, one pass, multi-label. No inter-annotator
   agreement exists, so "precision" means agreement with this reader.
2. **n = 39–40 per set, two repos.** Wilson intervals are wide (±0.1–0.15); treat
   the range as the estimate and the point values as examples.
3. **Domain.** aider and dify issue trackers. Neither is "user complaints" in the
   general sense — this corpus is software defect reports, which is exactly why
   the project pivoted.
4. **`accepted_cases` is still 0.** Nothing here is a human-accepted eval set, and
   no fix rate / resolution time / business impact is claimed anywhere.

## Backlog (design-level, not more phrases)

- **Co-occurrence model**: require a topic token *and* a fault token in the same
  clause. This is what the false positives of rounds 3–5 were really about.
- **A `logic_or_validation` mode**: several misses (exit codes, type coercion,
  accepted-invalid-input, duplicate execution) are currently forced into
  `config_or_env` or `data_integrity` and are documented as boundary cases in the
  label notes. The taxonomy is missing a bucket, not a signal.
- **A human label pass** on one split, so at least one number is not
  model-vs-model. Until then every figure here is agreement between the rules and
  one model reader.

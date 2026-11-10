# Defect hold-out evaluation

**Labels are MODEL-generated (`annotator: model`), except for split G.**
Every number here means "how well the deterministic rules agree with one careful
reader", not human accuracy. `accepted_cases` is still 0.

39 of the 40 G rows were also annotated **blind by a human** — see
[`human_agreement.md`](human_agreement.md). It is the only human reference in the
project, and it moves the mode-level number a lot: the binary call replicated
exactly, the mode labels did not.

Six **pairwise disjoint** splits exist. Each round is an error-analysis loop: read
the misses/false positives of set *N*, change something on principle, then measure
on a **fresh** set *N+1* that no change has ever seen. Numbers are never
overwritten, so anyone can check whether a result came from tuning.

## The headline, in four lines

- **Mode-level** (right issue *and* right bucket): precision ≈ 0.71–0.77,
  recall ≈ 0.56–0.80 — against **model labels**. Against the 39 human labels on
  set G the same engine scores **0.31 / 0.32**. Read the 0.71–0.77 range as an
  upper bound, not a point estimate.
- **In practice this is a crash detector.** On set F it found 13 of 15 crashes and
  **2 of 12 non-crash defects**.
- **Precision depends almost entirely on how many non-defects the queue contains.**
  Both source repos are defect trackers, so their natural prior is ~88% defects —
  far more positive than a real triage feed. Measured on a deliberately balanced
  50/50 split (set G), record-level precision is **0.632**, and the trivial
  "flag everything" rule scores **0.500 / 1.000** against it.

### Human check on set G (n = 39)

A human annotated set G blind: the workbook carried issue text and empty answer
columns, no predicted mode and no existing label.

| | Human vs existing labels | Human vs engine |
| --- | --- | --- |
| Is it a defect at all | κ = **1.000** | κ = **0.231** |

The binary judgement replicated on all 39 scored rows, including every
non-defect. The **mode** labels disagreed on 8 of 19 defect rows — mostly on the
data-vs-logic boundary — and mode-level micro precision fell from 0.714 to
**0.31**. `logic_or_validation` recall is 0.09: the human found 11 instances, the
engine found 1.

All eight disagreements, one excluded "unclear" row and the limits:
[`human_agreement.md`](human_agreement.md).

### Prior sensitivity (record level, from set G, n_clean = 20)

| Share of the queue that is defective | Expected precision |
| ---: | ---: |
| 90% | 0.939 |
| 75% | 0.837 |
| 50% | 0.632 |
| 25% | 0.364 |
| 10% | 0.160 |

Read the bottom rows. A quote of "precision 0.94" is only true for a feed that is
90% broken reports. **At a 25% prior — plausible for an unfiltered issue feed —
precision is 0.36**, i.e. roughly two of every three flags would be wrong.

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

## Round 7 — set G, measuring precision under a realistic prior

Sets A–F are all randomly drawn from two defect trackers, so ~88% of their records
are defect reports. That makes precision look good for a structural reason: with
four negatives in a split, one false positive barely moves the number.

Set G fixes the composition instead of the sampling. It is **20 non-defect reports
+ 20 defect reports**, hand-picked from the unused pool (`scripts/draw_holdout_g.py`
lists every id and why it is in there). The negatives are what a triage queue
actually contains: feature requests, chores/refactors, questions, vendor pitches and
spam. Selection is deliberate, not random, and that bias is real: these are *typical*
non-defects, not a uniform sample of them.

| Metric | Set F (~88% defects) | **Set G (50/50)** |
| --- | ---: | ---: |
| record-level precision | 0.944 | **0.632** [0.410, 0.809] |
| record-level recall | 0.630 | 0.600 [0.387, 0.781] |
| mode-level precision | 0.714 | **0.308** |
| mode-level recall | 0.556 | 0.400 |
| clean records wrongly flagged | 1 of 5 | **7 of 20 (35%)** |
| trivial "flag everything" baseline | 0.844 / 1.000 | **0.500 / 1.000** |

Three things fall out of this, none of them flattering:

1. **The engine is barely better than a trivial rule at a realistic prior.** On G it
   buys precision 0.632 vs 0.500, while giving up 0.400 of recall versus 1.000. That
   is not a defensible trade for a triage tool.
2. **It over-flags non-defects: 7 of 20 (35%).** The offenders are feature requests
   that talk about performance ("make X faster") and chores that mention data
   ("dependency upgrade upsets package exports"). Topic vocabulary, again.
3. **`crash_or_error` scored precision 0.00 on G** (4 predictions, 0 correct, and it
   missed both real crashes). Its 0.95–1.00 precision on aider/dify-heavy splits
   comes from those corpora using `Uncaught`/`Traceback` wording. A report that
   describes a failure without that vocabulary ("returns 400", "is not a function")
   is not recognised at all.

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
| F | 32 | 0.944 | 0.630 | 1 of 5 |
| **G (50/50)** | 40 | **0.632** | 0.600 | **7 of 20** |

The last two columns matter. Random splits carry only 3–5 clean records, so their
clean-record column is noise; G is the first set with enough negatives to estimate
the false-positive rate properly (0.35), and that is what drags precision down.
The pattern behind those flags is always the same: a feature proposal or vendor
pitch that happens to mention a technical word gets labelled a defect. That is the
tool's most visible failure mode.

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
  and set F is 32 records because aider's derive pool ran out. **Set G is the one
  exception**: hand-built at 20/20 to measure a different class prior
  (`scripts/draw_holdout_g.py` lists every id and its reason).
- **Labels** (`labels_holdout*.jsonl`): multi-label per record (`modes: []` =
  feature request / promo / off-topic). Written by reading the issue text only;
  **engine predictions were not consulted** (easy to guarantee — v0.1 produced
  ~0 candidates on this corpus).
- **Score** (`scripts/eval_defects_holdout.py`): per-mode precision/recall, micro
  average, record-level detection, Wilson intervals, the full miss and
  false-positive lists, two trivial baselines, and the prior-sensitivity reweight.
- **Corpus** (`.local/corpus/`, gitignored, never published): aider 252 issues
  (Apache-2.0), dify 176 issues (Apache-2.0 with additional conditions). Both were
  expanded as later splits exhausted the earlier pools; without that, every split
  after D would have been aider-only and inflated by crash reports.

Reproduce (needs the local corpus snapshot; labels and splits are committed):

```bash
python scripts/eval_defects_holdout.py --holdout .local/corpus/holdoutF.jsonl \
    --labels eval/defect_holdout/labels_holdout_f.jsonl --out out/eval_defects_f.json
python scripts/eval_defects_holdout.py --holdout .local/corpus/holdoutG.jsonl \
    --labels eval/defect_holdout/labels_holdout_g.jsonl --out out/eval_defects_g.json
```

`out/` is gitignored, so the two headline runs are committed verbatim as
[`results_f.json`](results_f.json) and [`results_g.json`](results_g.json) — generated
output, never hand-edited, containing record ids and mode labels only. Earlier
rounds' raw outputs are not committed; their numbers survive in the tables above and
in the commit messages, which is the only place they can be checked against.

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
2. **Precision is a function of the prior.** Never quote one precision figure without
   saying which class mix it came from. The 0.944 on F is a 90%-defect feed; the useful
   number for deployment planning is the 25% row of the prior-sensitivity table (0.36).
3. **The negative sample is only now adequate.** Four random splits contributed 3–5
   clean records each; G contributes 20. Every earlier precision figure rested on
   almost no negatives and should be read as "on this particular draw", not as an
   estimate.
4. **Crash detection is vocabulary-bound.** It works on reports that say `Uncaught` or
   `Traceback` and fails on ones that describe the same failure in prose ("returns
   400", "is not a function"). On G it scored 0.00 precision.
5. **n = 32–40 per set, two repos.** Wilson intervals span ±0.12–0.18.
6. **Domain.** aider and dify issue trackers — software defect reports, not user
   complaints in general. That is exactly why the project pivoted from the
   LLM-behaviour taxonomy.
7. **Rare modes unmeasurable.** Nine modes have ≤10 labels per split.
8. **G's negatives are hand-picked.** They are typical non-defects, not a uniform
   sample, so 0.35 is an estimate of the false-positive rate on *plausible* noise,
   which may be harsher than a real queue.
9. **`accepted_cases` is 0.** Nothing here is a human-accepted eval set, and no fix
   rate, resolution time or business impact is claimed anywhere.

## Backlog (design-level, not more phrases)

- **Co-occurrence model**: require a topic token *and* a fault token in the same
  clause. Every false positive since round 3 has been a topic word in neutral
  prose; every miss has been a fault expressed in vocabulary the list lacks.
- **Sentence-level, not clause-level**: markdown issue templates split clauses at
  every newline, which cuts a claim in half before it can be matched.
- ~~**A human label pass** on one split~~ — done, set G, n = 39. Result: the binary
  call replicated (κ = 1.000) but mode-level precision fell to 0.31. See
  [`human_agreement.md`](human_agreement.md).
- **A second human on the same rows**, to get reader-to-reader κ rather than
  human-vs-model.

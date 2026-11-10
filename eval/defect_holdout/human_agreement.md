# Human agreement on the G split

**This is the first number in this project that does not compare a model to
itself.** One human annotated the G split blind — the workbook contained issue
text and empty answer columns, with no predicted mode and no existing label.

- Split: G (20 non-defect / 20 defect, hand-built)
- Annotator: one person, tagged `annotator: human`, independent
- 40 rows returned, 39 scored, 1 marked "unclear" (excluded from kappa)
- Raw output: [`human_agreement.json`](human_agreement.json)
- **Scope note:** three further readers later labelled the same split — see
  [`multi_annotator.md`](multi_annotator.md). The binary result here replicated
  (four-reader Fleiss κ = 0.922); some single-reader *mode* attributions below did
  not, and are marked as corrected.

## Headline

| Comparison | Agreement | Cohen's κ | What it means |
| --- | ---: | ---: | --- |
| Human vs existing reader (this project's labels) — *is it a defect at all* | 1.000 | **1.000** | The binary call holds up |
| Human vs engine — *is it a defect at all* | 0.615 | **0.231** | Barely better than chance |
| Human vs existing reader — *which mode* | — | — | **8 of 19 defect rows disagree** |

The binary judgement replicates. The category judgement does not.

## Record level (is this a defect report at all)

The human and the existing labels agree on **39 of 39** scored rows, including
all 20 non-defect rows. That is the reassuring half: the 50/50 split was not
built by mislabelling feature requests as bugs.

Against the human labels, the engine on this split:

| | Value | 95% Wilson |
| --- | ---: | --- |
| Precision | 0.632 | [0.410, 0.809] |
| Recall | 0.600 | — |
| TP / FP / FN | 12 / 7 / 8 | — |
| κ vs human | 0.231 | — |

These are the same precision/recall figures previously reported for G. They did
not change, because the binary labels did not change. **Everything below did.**

## Mode level (human = reference)

Mode-level scoring asks a harder question: right record *and* right bucket.
Predictions and gold instances of 25–26 each, so every count moves the number.

| Mode | TP | FP | FN | Precision | Recall |
| --- | ---: | ---: | ---: | ---: | ---: |
| `crash_or_error` | 0 | 4 | 1 | **0.00** | **0.00** |
| `data_integrity` | 2 | 5 | 1 | 0.29 | 0.67 |
| `logic_or_validation` | 1 | 0 | 10 | 1.00 | **0.09** |
| `config_or_env` | 1 | 2 | 1 | 0.33 | 0.50 |
| `ui_or_ux` | 1 | 1 | 3 | 0.50 | 0.25 |
| `security` | 2 | 1 | 0 | 0.67 | 1.00 |
| `performance` | 1 | 5 | 0 | 0.17 | 1.00 |
| `regression` | 0 | 0 | 1 | — | 0.00 |
| **micro** | **8** | **18** | **17** | **0.31** | **0.32** |

### The number that has to be corrected

Against the project's own labels, mode-level micro precision on G was **0.714 /
0.556**. Against the human it is **0.31 / 0.32**.

The gap is not the engine getting worse overnight. It is the reference changing:

1. **The human labelled more thoroughly.** On multi-symptom reports they tagged
   2 modes where the existing labels carried 1 (`data_integrity` +
   `logic_or_validation` on four rows). Richer gold labels mechanically raise FN.
2. **Eight of 19 defect rows disagree on the bucket**, mostly at the
   data-vs-logic boundary. Two readers with the same taxonomy still split.
3. **The engine's multi-label output is thin.** It emits one mode per record in
   most rows; the human emits 1.3 on average.

So the honest reading of mode-level precision is **0.31–0.71 depending on whose
labels you trust, and nobody should quote a point estimate until a second human
labels the same rows.** The 0.71–0.77 range quoted elsewhere in this folder is
model-labelled and should be read as an upper bound.

## The 8 disagreements, in full

| Row | Issue | Human | Existing labels | Engine |
| --- | --- | --- | --- | --- |
| r23 | aider-5706 | `logic_or_validation` | `data_integrity` | `crash_or_error` |
| r28 | aider-5622 | `config_or_env`, `security` | `config_or_env` | `config_or_env`, `security` |
| r34 | dify-45580 | `logic_or_validation` | `crash_or_error` | — |
| r35 | dify-45547 | `logic_or_validation` | `data_integrity` | `crash_or_error`, `data_integrity` |
| r36 | dify-45516 | `data_integrity`, `logic_or_validation` | `logic_or_validation` | `crash_or_error` |
| r37 | dify-45508 | `data_integrity`, `logic_or_validation` | `logic_or_validation` | `crash_or_error`, `data_integrity`, `performance`, `ui_or_ux` |
| r38 | dify-45422 | `regression`, `ui_or_ux` | `data_integrity` | `data_integrity` |
| r40 | dify-45184 | `data_integrity`, `logic_or_validation` | `data_integrity` | `data_integrity` |

Patterns worth naming — **now corrected against the four-reader study in
[`multi_annotator.md`](multi_annotator.md), which supersedes the single-reader
attribution in this section:**

- **The 400/TypeError trap is real but not one-sided.** r34 and r35 were labelled
  `crash_or_error` by this project because the report quotes an HTTP 400 or a
  `TypeError`. With four readers, r34 splits **3 logic to 2 crash** (one reader
  wrote both), and r35 splits **3 logic to 3 data** — so "the human reads it as
  logic" was too strong, but the engine treating a quoted error string as a crash
  is still the wrong instinct.
- **data vs logic is partly genuine ambiguity and partly granularity.** Six of
  eight disagreements sit on this boundary. The four-reader study shows the
  readers who write two modes always write *both* `data_integrity` and
  `logic_or_validation`; the readers who write one pick whichever they consider
  primary. So the boundary is vague, but most of the "disagreement" is a reader
  choosing to record one side of a pair that both sides agree exists.
- **r38 is a real miss by the labels, not just the engine.** "Download entry
  disappears after converting to Pipeline" is a regression. All four readers say
  `regression` and/or `ui_or_ux`; **this project alone says `data_integrity`**.
  Recorded as a known label error rather than silently patched.
- **r37 shows the engine over-firing.** Four modes on one row, three of them
  wrong. `performance` and `ui_or_ux` fired on a report about embedding count
  mismatch.

## One row the human would not call

`r05` (a report about token-invalid model IDs and 404/402 errors for free/BYOK
users) was marked **unclear** — the annotator's note: the problem section
describes real failures, but the body is mostly a fallback proposal with an
offer to open a PR. The existing labels call it a non-defect. Both readings are
defensible, which is exactly why it is excluded from kappa rather than coerced.

## Limits

1. **This file is one annotator, one pass.** κ here measures agreement between two
   readers, not truth. Three further readers are analysed in
   [`multi_annotator.md`](multi_annotator.md): Fleiss κ = 0.922 across four, so the
   binary call holds — but the mode-level figures below remain single-reader, and
   the four-reader mode spread is 0.23–0.40.
2. **n = 39.** A single disagreement is 2.6 percentage points; kappa on 39 rows
   is coarse.
3. **G is a balanced set, not a sample.** It over-represents non-defects by
   construction, so its precision is not the precision of a real queue.
4. **The annotator could infer some answers from vocabulary.** Aider reports
   quoting `Uncaught` are obvious; that inflates agreement on the easy rows.
5. **The existing labels were written by the same person who wrote the signals.**
   Human-vs-reader κ = 1.000 on the binary call does not mean the *modes* are
   right; the 8 disputes show they are not.

## What changes in the repo

- Mode-level precision elsewhere in `eval/defect_holdout/` is relabelled
  **model-labelled, upper bound**.
- The record-level precision (0.632) and recall (0.600) stand; they were
  measured against labels a human now agrees with.
- `logic_or_validation` recall of 0.09 is the single clearest backlog item: the
  human found 11 instances, the engine found 1.

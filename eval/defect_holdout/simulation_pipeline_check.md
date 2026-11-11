# Simulation: the multi-reader pipeline works, and that is all it proves

**`kind: simulation` · `annotator: model` · `publishable: false` · `accepted_cases: 0`**

On 2026-11-11 the requester decided that chasing a second independent human
reader for split H was not worth it and authorised simulated data instead. This
file records what was done with that authorisation — and, more importantly, what
was deliberately *not* done.

Raw numbers: [`simulation_pipeline_check.json`](simulation_pipeline_check.json).
Generator: `scripts/make_simulated_reader.py` (seed `20261111`). Scorer:
`eval_human_agreement_v2.py --simulated`, which refuses to write into `eval/`.

## What was generated

Three synthetic "second readers", each derived from the confirmed human H_r1
workbook by a deterministic perturbation. Reasons were replaced with template
text so no real reader's prose was copied. All three live in `.local/`
(gitignored), with `SIMULATED / NOT HUMAN` on the first sheet.

| Variant | 不确定 rows | primary swaps | secondary edits |
| --- | ---: | ---: | ---: |
| identical | 0 | 0 | 0 |
| moderate | 2 | 6 | 4 |
| divergent | 8 | 16 | 12 |

Swaps follow the boundaries real readers actually disagreed on in split G
(`data_integrity` ↔ `logic_or_validation`, `crash_or_error` ↔ `performance`,
`ui_or_ux` ↔ `config_or_env`) so the disagreements are interpretable. That does
not make them real.

## Result: the statistic can be dialled to any value

| Variant | binary Fleiss κ (y/n/u) | *old* definite-only κ | primary-mode Fleiss κ | independence check |
| --- | ---: | ---: | ---: | --- |
| identical | **1.000** | 1.000 | **1.000** | SUSPECT (exit 2) |
| moderate | **0.890** | 1.000 | **0.743** | NO_RED_FLAG (exit 0) |
| divergent | **0.630** | 1.000 | **0.221** | NO_RED_FLAG (exit 0) |

**This table is the argument, not a finding.** Turning one parameter moves the
mode-level κ from 0.221 to 1.000. A number that can be set to anything proves
nothing about whether two people agree. It is recorded precisely so nobody can
later quote the flattering row as "v2 reached κ = 1.000".

## A real bug the simulation caught

The multi-reader branch silently **dropped every row where either reader
answered 不确定** before computing the binary Fleiss κ. With that denominator,
all three variants scored **1.000** on the binary layer — the two variants that
actually disagreed were invisible. That is exactly the "pick a flattering
denominator" mistake this project keeps guarding against.

Fixed in `eval_human_agreement_v2.py`:

- `不确定` is now a **third category** (`y / n / u`) in the headline κ;
- the older `*_definite_only` figure is still emitted, but explicitly labelled
  as the flattering comparison;
- both `n_items` and `n_items_definite_only` are reported, plus the list of
  unclear rows;
- pairwise Cohen's κ uses all three categories.

Also fixed a broken pairwise index that was pairing every row of reader A with
the *first* row of reader B when more than two workbooks were supplied.

## What the independence checker did — and did not — say

`check_labeling_independence.py` flagged `identical` as SUSPECT but returned
`NO_RED_FLAG` for `moderate` and `divergent`. Those two are still synthetic and
still derived from H_r1.

> **`NO_RED_FLAG` is not a certificate.** The tool detects a paraphrase
> signature (identical labels + highly similar prose). It can *falsify*
> independence; it cannot establish that a reader is human, blind, or
> independent. Only provenance can. This simulation is a worked example of why.

## What is now verified

The pipeline itself: Cohen's κ for pairs, Fleiss κ on the binary and
primary-mode layers, three-category handling of 不确定, two denominators shown
side by side, per-reader scores, and a per-row disagreement table. A genuinely
independent workbook could be scored today without writing new code.

## What is deliberately left unanswered

**Whether the v2 rule makes two independent people agree more than v1.**
No reader-to-reader κ from real people exists under v2, and none will be
manufactured here. The claim stays ❌ untested in both READMEs. Split G's four
independent human readers (Fleiss κ = 0.922 on the binary question) remain the
only multi-person data in this repository; H's 0.545 / 0.429 remains a genuine
engine-vs-one-person comparison.

Using simulation to *fill the gap* would have been self-verification: derive a
reader from your own data, then report that it agrees with your own data. The
gap is closed by deciding not to claim the result, not by filling it.

# One reader on the H split, under the v2 rule

> **2026-11-10 update — read this before quoting anything below.** The first
> workbook was **confirmed by the requester as filled by a person**, so the
> engine-vs-reader figures below are a real person-vs-machine comparison.
> A second filled workbook failed the independence check (every label matched,
> optional causes identical on 40/40 rows, reasons paraphrased at 0.843 mean
> similarity with 0 byte-identical rows) and was **rejected** — it is not a
> second reader. See [`contamination_h.md`](contamination_h.md).
> **One reader is still only one reader: the v2 hypothesis is untested, and no
> reader-to-reader κ may be published from these two workbooks.**

**Read this line first: one reader is not an agreement study.** The v2 rule was
written to fix a *between-people* problem — readers splitting into "one label"
and "symptom plus cause" camps. A second reader on the same workbook is the only
thing that can test whether it worked. One workbook cannot.

So this file reports the one comparison a single reader does support: the engine
scored against that reader, under v2 semantics (primary mode only). It also
reports what the same rows look like when the secondary column is folded into the
gold set — not because that is the v2 rule, but because the gap between the two
numbers is the whole reason the rule exists.

- Split: H, 40 rows, stratified (aider crash-template 6 / aider other 14 / dify 20)
- Reader: one person, independent, tagged `annotator: human`; workbook carried
  issue text and empty answer columns, no predicted mode, no existing label
- Overlap with splits A–G: 0
- Raw output: [`human_agreement_v2.json`](human_agreement_v2.json)
- Reproduce: `python scripts/eval_human_agreement_v2.py --workbook <filled.xlsx>`

## Headline

| Comparison | Value | What it means |
| --- | ---: | --- |
| Reader vs engine — *is it a defect at all* | κ **0.327**, agreement 0.650 | not close |
| Engine precision / recall, record level | **0.889** [0.672, 0.969] / **0.571** [0.391, 0.735] | flags 18 of 40, misses 12 of 28 defects |
| Engine precision / recall, mode level, primary only | **0.545** [0.347, 0.731] / **0.429** [0.265, 0.609] | 12 right, 10 wrong, 16 missed |
| Engine silent on a defect row | **12 of 28** | 43% of real defects get no label at all |
| Same rows, gold = primary + secondary | 0.636 / **0.264** | 25 extra gold modes, recall drops |

**The one honest comparison available is between the two mode-level rows**
(0.545 / 0.429 against 0.636 / 0.264): same split, same rows, only the definition
of a gold label changes. Everything else in this table is a level, not a trend —
H is a different split from G with a different prior, and 0.545 cannot be
subtracted from 0.31.

## What the reader actually filled

| | count |
| --- | ---: |
| 是 (defect) | 28 |
| 不是 (not a defect) | 12 |
| 不确定 (unclear) | 0 |
| rows using the secondary column | 25 |

Primary mode distribution: `crash_or_error` 11, `data_integrity` 10, `ui_or_ux` 5,
`security` 1, `performance` 1. **`logic_or_validation` 0 as primary, 15 as
secondary.** Under the v2 rule, one reader essentially stopped using the fallback
class for the primary decision while still recording it as a cause — which is
what the rule intended. It also means the v1 complaint that "everything is being
filed as logic_or_validation" was a *template* problem, not a vocabulary problem:
give people a symptom-ordered checklist and they keep the cause (15 rows) but stop
choosing it as the answer.

## Per-mode, primary only (reader = reference)

| mode | TP | FP | FN | P | R | note |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| crash_or_error | 7 | 0 | 4 | **1.00** | 0.64 | 6 of the 7 are one template |
| data_integrity | 1 | 4 | 9 | **0.20** | **0.10** | worst class by a mile |
| ui_or_ux | 2 | 1 | 3 | 0.67 | 0.40 | |
| security | 1 | 1 | 0 | 0.50 | 1.00 | |
| performance | 1 | 2 | 0 | 0.33 | 1.00 | |
| config_or_env | 0 | 2 | 0 | 0.00 | — | never right as a primary |
| micro | 12 | 10 | 16 | 0.545 | 0.429 | |

`crash_or_error` at precision 1.00 is real but cheap: six of the seven true
positives are the same generated crash template (`Uncaught X in file Y line N.
Aider version:`) with a different exception name. The bucket was sampled on
purpose, at 6/40, and it is the bucket where a keyword engine cannot lose.

`data_integrity` is the opposite and is the finding to act on. The reader used it
as the primary mode **10 times**; the engine got **1** of those, and put 4 other
rows there by mistake. Nine of the ten are "it ran, the output is wrong" reports
with no crash vocabulary in them — silent drop, wrong column, offset timestamp,
double-decoded body. No phrase-list design with a fault-word lexicon will reach
these; they need topic-word plus fault-word co-occurrence, which is the
restructure already on the list.

## Baselines, so the numbers are not read alone

| Baseline | record P / R | mode micro P / R |
| --- | --- | --- |
| always flag every record | 0.700 / 1.000 | — |
| always answer `crash_or_error` | — | 0.275 / 0.393 |
| engine | 0.889 / 0.571 | 0.545 / 0.429 |

Same shape as split G, same verdict: the engine buys precision it does not need
and pays in recall. On a queue that is 70% defective, flag-everything scores 0.700
precision with perfect recall — the engine's 0.889 does not justify dropping 43%
of the defects.

Clean records wrongly flagged: **2 of 12** (`r09`, `r10`) — both are
feature/question reports that contain fault-sounding words. Better than the 7/20
on split G, but that is the split's prior, not the engine improving.

## Why this is not "v2 made things better"

Three reasons, written down so a later reader cannot quietly drop them:

1. **Different split, different prior.** G was hand-built 20/20. H is 70%
   defective by construction (6 crash + 14 aider other which skew to feature
   requests + 20 dify which skew to bugs). Precision and recall both move with
   the prior — the sensitivity curve in [`README.md`](README.md) shows 0.939 at a
   90% defective queue and 0.364 at 25%.
2. **Different reference.** G's 0.31 was scored against a *single-label reader
   while the engine was allowed multiple modes*. H's 0.545 scores only the
   primary column. That is a change of measuring instrument.
3. **One reader.** No reader-reader κ exists for v2 yet. The v1 figure it would
   be compared against — Fleiss κ 0.922 binary, low mode-level agreement between
   granularity camps — is a between-people number. Comparing a between-people
   number to a person-versus-machine number is the exact error this project keeps
   catching itself making.

## What is still missing — and now deliberately left missing

The v2 hypothesis is untested. Testing it needs a second person to fill the same
40 rows blind, with no sight of the first workbook: reader-reader binary κ
against v1's 0.922, primary-mode κ against v1's low cross-granularity numbers,
and whether "one primary by symptom order" actually converges two people.

**On 2026-11-11 the requester decided not to collect that second reader** and
authorised simulated data instead. Two returned "second" workbooks had already
been rejected as non-independent, so a third attempt was not worth another
round. The gap is therefore closed by *not claiming the result*, not by filling
it with a generated reader.

[`simulation_pipeline_check.md`](simulation_pipeline_check.md) records what the
simulation was used for: verifying that the scorer computes both κ layers
correctly, handling 不确定 as a third category and fixing a flattering-denominator
bug. Its κ values range 0.221–1.000 depending on a generator parameter and are
**not publishable**. Nothing here may be quoted as evidence that v2 is better.

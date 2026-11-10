# Multi-annotator agreement on the G split (4 readers)

Four annotators labelled the same 40 rows, blind — the workbook carried issue
text and empty answer columns, no predicted mode, no existing label. Their
working styles differ by construction and by name:

| Label | Self-described style | 是 | 不是 | 不确定 | Mean modes per defect |
| --- | --- | ---: | ---: | ---: | ---: |
| 甲 (strict evidence) | one mode, only what the text proves | 20 | 19 | 1 | 1.00 |
| 乙 (lenient intent) | tags symptom *and* cause | 23 | 17 | 0 | 1.74 |
| 丙 (root-cause multi) | tags symptom *and* cause | 21 | 19 | 0 | 1.76 |
| 丁 (headline skim) | one mode, what the title says | 21 | 19 | 0 | 1.00 |
| *this project* | one mode | 20 | 20 | 0 | 1.00 |
| *engine* | 1–2 modes, keyword-driven | 19 | 21 | 0 | — |

Raw output: [`multi_annotator.json`](multi_annotator.json). Reproduce with
`scripts/eval_multi_annotator.py`.

## Headline

| Question | Answer |
| --- | --- |
| Can two careful readers agree on "is this a defect"? | **Yes — Fleiss κ = 0.922** across the four |
| Can the engine agree with a human? | **No — κ = 0.202–0.305** against any of them |
| Does the engine belong to the group? | **No** — adding it as a fifth rater drops Fleiss from 0.911 to **0.633** |
| Do the readers agree on *which* mode? | Partly. Same-set agreement 0.19–0.86, Jaccard 0.55–0.93 — the spread is **granularity**, not judgement |
| Best mode-level score the engine gets against any human | **0.23–0.38 precision**, 0.24–0.40 recall |

This is the answer to the question the previous round could not settle. The
disagreement is not "readers cannot agree". Readers agree strongly on the binary
call, and the engine is the outlier.

## 1. The binary call is reliable

Pairwise Cohen's κ on "is this a defect", indeterminate rows dropped:

|  | 甲 | 乙 | 丙 | 丁 | project |
| --- | ---: | ---: | ---: | ---: | ---: |
| **甲** | — | 0.845 | 0.949 | 0.949 | 1.000 |
| **乙** | 0.845 | — | 0.899 | 0.899 | 0.850 |
| **丙** | 0.949 | 0.899 | — | **1.000** | 0.950 |
| **丁** | 0.949 | 0.899 | 1.000 | — | 0.950 |
| **project** | 1.000 | 0.850 | 0.950 | 0.950 | — |
| **engine** | 0.231 | 0.305 | 0.202 | 0.202 | 0.250 |

- Lowest human-human pair: **0.845** (甲 vs 乙 — the strict reader against the
  lenient one).
- 丙 and 丁 agree on **every single row** despite opposite stated styles.
- The engine's best relationship with anyone is 0.305, with the lenient reader
  who calls the most rows defects. It is not measuring the same thing.

Only **4 of 40 rows** lack a unanimous verdict:

| Row | Issue | Verdicts | Project | Engine |
| --- | --- | --- | --- | --- |
| r05 | aider-5676 | 甲不是 · 乙是 · 丙是 · 丁是 | 不是 | 不是 |
| r11 | dify-45584 | 甲不确定 · 其余不是 | 不是 | 不是 |
| r13 | dify-45560 | 乙是 · 其余不是 | 不是 | 是 |
| r14 | dify-45559 | 乙是 · 其余不是 | 不是 | 是 |

r13 and r14 are the lenient reader alone against three. r05 is the opposite:
**three readers call it a defect and this project does not.**

## 2. The mode labels differ by granularity, not by disagreement

Same-set agreement on rows both call a defect looks alarming — 0.19 to 0.86:

| Pair | Both 是 | Same mode set | Mean Jaccard |
| --- | ---: | ---: | ---: |
| 乙 vs 丙 | 21 | **0.86** | **0.93** |
| 丁 vs project | 20 | 0.85 | 0.85 |
| 甲 vs project | 20 | 0.80 | 0.80 |
| 甲 vs 丁 | 20 | 0.70 | 0.70 |
| 甲 vs 丙 | 20 | 0.25 | 0.62 |
| 甲 vs 乙 | 20 | 0.20 | 0.60 |
| 丁 vs 乙 | 21 | 0.19 | 0.57 |
| 丙 vs project | 20 | 0.20 | 0.55 |
| 丁 vs 丙 | 21 | 0.19 | 0.55 |

That block structure is real, and it has one cause: **how many modes a reader
writes down.**

| Reader | Mean modes per defect | Rows with 1 mode | Rows with 2 |
| --- | ---: | ---: | ---: |
| 甲 | 1.00 | 20 | 0 |
| 丁 | 1.00 | 21 | 0 |
| project | 1.00 | 20 | 0 |
| 乙 | 1.74 | 6 | 17 |
| 丙 | 1.76 | 5 | 16 |

A single-mode reader can never produce the same *set* as a two-mode reader, so
"same set" collapses to ~0.2 across the groups even when both are describing the
same bug. The decisive check:

> **Do the single-mode labels fall inside the two-mode labels' union?**
> 甲 **20/20**, 丁 **20/21**, project **19/20**.

Yes, essentially always. The readers are looking at the same defect; some write
down the symptom, others write the symptom *and* the cause. Two exceptions:

- **r05** — 丁 says `crash_or_error`, 乙+丙 say `config_or_env` + `logic_or_validation`.
- **r38** — project says `data_integrity`; 乙+丙 say `regression` + `ui_or_ux`;
  甲 says `regression`; 丁 says `ui_or_ux`. **Nobody but this project calls it a
  data problem.**

So the taxonomy has not collapsed. The **annotation procedure** has a hole: it
never says whether a report gets one mode or all of them. That single missing
rule is responsible for most of the apparent disagreement.

## 3. The engine is outside every reference

Mode-level, engine scored against each annotator in turn:

| Reference | TP | FP | FN | Micro P | Micro R |
| --- | ---: | ---: | ---: | ---: | ---: |
| 甲 (strict) | 6 | 20 | 14 | 0.23 | 0.30 |
| 乙 (lenient) | 10 | 16 | 30 | 0.38 | 0.25 |
| 丙 (root-cause) | 9 | 17 | 28 | 0.35 | 0.24 |
| 丁 (headline) | 8 | 18 | 13 | 0.31 | 0.38 |
| project labels | 8 | 18 | 12 | 0.31 | 0.40 |
| **≥3-of-4 consensus** | **8** | **18** | **17** | **0.31** | **0.32** |

The project's own 0.31 is not an artifact of one harsh reader. **Every** reference
lands between 0.23 and 0.40. Requiring three of four readers to agree moves the
number by 0.01.

The clearest single failure: **`logic_or_validation`**.
- Vote distribution across the four readers, per row: 0 votes on 24 rows,
  **4 votes on 5 rows**, ≥2 votes on 14 rows.
- The engine emits it on **1 row**.
- Of the five rows all four readers call logic, the engine returned **nothing at
  all** on four of them (r21, r24, r25, r33).

The engine also returned **no mode whatsoever on 8 of 40 rows**, all of them rows
the readers call defects.

## 4. Two project labels are wrong

Against a ≥2-of-4 majority:

| Row | Issue | Majority | Project | Engine |
| --- | --- | --- | --- | --- |
| r05 | aider-5676 | 是 · `config_or_env` + `logic_or_validation` | 不是 · — | 不是 · — |
| r38 | dify-45422 | 是 · `regression` + `ui_or_ux` | 是 · `data_integrity` | 是 · `data_integrity` |

r05 is a false negative in this project's labels — three readers saw a defect.
r38 is a wrong mode, and the engine inherited it. Both are recorded here rather
than silently patched, because changing a label after the fact changes what the
published numbers mean. The honest options are: (a) keep the split frozen and
publish these two as known label errors, or (b) refreeze the split with consensus
labels and restate every number that used it. **Frozen + published errors is the
default**; restating is a larger job than this round.

## A methodological warning about majority vote

With four readers, a 2-of-4 threshold is decided entirely by 乙 and 丙, who agree
with each other 0.86 of the time and both write two modes. Their two votes make a
"majority" before 甲 or 丁 are consulted. Under a 2-vote rule the consensus mode
set contains `logic_or_validation` in 14 rows; under 3-of-4 it is 10 rows; both are
defensible, so **quote the rule alongside the number**. This is why the ≥3-of-4
figure is the one used for the engine score above.

## What this settles

1. **The binary labels in this project are trustworthy.** Four readers, κ = 0.922,
   including the hand-built 50/50 prior. The record-level engine figures
   (0.632 precision / 0.600 recall on G) stand.
2. **The mode labels are not comparable across readers yet**, because the
   procedure never fixed the granularity. Until it does, mode-level precision
   should be quoted with the reader's name attached.
3. **The engine is the outlier, not the annotators.** κ 0.20–0.31 against every
   human; adding it as a fifth rater drops group agreement from 0.911 to 0.633.
4. **The highest-value fix is not a new heuristic**, it is writing down two rules:
   one mode or many, and symptom or root cause. Everything else in the mode-level
   noise follows from those two.

## Limits

1. Four annotators, 40 rows, one split, one project family (aider + dify).
2. "Style" is inferred from filenames and observed tag counts, not from a
   questionnaire — 乙 and 丙 may simply both be thorough rather than both
   "root-cause".
3. Reading order was identical for everyone, so a shared position effect is
   possible.
4. The engine's predictions were cached from one run; they were not regenerated
   per comparison.
5. κ is computed on the binary call only. Mode-level "agreement" is reported as
   same-set rate and Jaccard, which are descriptive, not chance-corrected.

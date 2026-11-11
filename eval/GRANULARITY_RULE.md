# Labelling spec v2: one primary mode, plus opt-in causes

**Status: applied to one H workbook (40 rows) confirmed as human-filled, plus a
second returned workbook rejected as non-independent
(see [`defect_holdout/contamination_h.md`](defect_holdout/contamination_h.md)).**
Sets A–G were labelled
under v1, which never fixed granularity; their numbers are not comparable with
H's. The rule has fixed *how a workbook is filled*, not whether two independent
people now agree — no reader-to-reader agreement under v2 exists, and the
requester decided on 2026-11-11 not to collect one; simulated data was used only
to verify the scoring pipeline. See both
[`simulation_pipeline_check`](defect_holdout/simulation_pipeline_check.md) and
[`human_agreement_v2`](defect_holdout/human_agreement_v2.md).

## Why this exists

Four readers labelled the same 40 rows. They agreed on *whether* a row is a defect
(Fleiss κ = 0.922) and disagreed on the mode — but the disagreement was not about
judgement:

| Reader | Mean modes per defect |
| --- | ---: |
| 甲, 丁, this project | 1.00 |
| 乙, 丙 | 1.74 / 1.76 |

And every single-mode label fell inside the two-mode union (20/20, 20/21, 19/20).
Two readers were describing the same defect at different resolutions.

Mode-level precision compares mode **sets**, so resolution silently moves the
number. Worse, `logic_or_validation` overlaps both `data_integrity` and
`ui_or_ux`: the same bug is "the value came back wrong" (symptom) and "the code
coerced it wrong" (cause), and v1 accepts either.

## The rule

1. **Exactly one primary mode per defect report.** Not zero, not two.
2. **The primary mode is the fault's manifest form**, not its cause and not what
   the user "feels". If a request returns 400, the manifest form is a failed
   request → `crash_or_error`, even if the cause is a validation bug.
3. **`logic_or_validation` is the fallback**, used only when the fault is a wrong
   decision with no more specific manifest form (accepted invalid input, wrong
   branch taken, wrong type produced, same action executed twice).
4. **Optional: up to two cause modes**, recorded separately. These carry the
   root-cause information that 乙 and 丙 were recording, without polluting the
   primary comparison.
5. **Scoring compares the engine against primary modes only.** Cause modes are
   reported separately and never enter the headline precision/recall. They may be
   used in an explicitly labelled *sensitivity check* showing how much the number
   moves under the old everything-you-see convention — that check is not the v2
   score and must never be quoted without its label.

## Decision order

Apply in order; stop at the first match.

| # | Ask | Primary mode |
| ---: | --- | --- |
| 1 | Did the process, request or command fail outright — exception, crash, non-2xx, non-zero exit? | `crash_or_error` |
| 2 | Did it complete, but produce/lose/reorder/duplicate data? | `data_integrity` |
| 3 | Did it complete, data is fine, but the interface is wrong or unresponsive? | `ui_or_ux` |
| 4 | Did it complete, but it took pathologically long, hung, or leaked? | `performance` |
| 5 | Did it cross a boundary it must not cross (path, auth, confirmation, secret)? | `security` |
| 6 | Is the report "this worked before, it doesn't now" (version-anchored)? | `regression` |
| 7 | Is the claim that a setting/env/install was ignored or not applied? | `config_or_env` |
| 8 | Is the claim that documentation is missing or wrong? | `docs` |
| 9 | Is the claim that a required translation or locale is wrong/missing? | `i18n_or_locale` |
| 10 | None of the above — it is a wrong decision/validation with no other form | `logic_or_validation` |

Order matters. "It returns 400 because validation is too strict" hits rule 1
before rule 10. "Silently truncates to 0" hits rule 2 before rule 10.
"Wrong branch, output shape unchanged" only reaches rule 10.

## Worked examples

| Report | Primary | Cause (optional) | Why |
| --- | --- | --- | --- |
| `Uncaught ImportError in main.py` | `crash_or_error` | — | rule 1 |
| API returns 400 for a valid payload | `crash_or_error` | `logic_or_validation` | failed request first, strict-validation is the cause |
| Exported CSV has 90 rows instead of 100 | `data_integrity` | `logic_or_validation` | completes, wrong data |
| `1e-07` stored as `0` | `data_integrity` | `logic_or_validation` | value wrong on arrival |
| Sidebar overlays the content | `ui_or_ux` | — | rule 3 |
| Worker never returns | `performance` | — | rule 4 |
| `.env` silently overrides shell exports | `security` | `config_or_env` | boundary crossed (secrets redirect) before "config ignored" |
| Download link gone after a pipeline conversion | `regression` | `ui_or_ux` | version-anchored disappearance |
| Accepts a trailing newline it should reject | `logic_or_validation` | — | wrong decision, nothing else manifests |

Note the asymmetry: `security` outranks `config_or_env` because the boundary
crossing is the harm; `regression` outranks the form of the regression because
"worked before" is the actionable claim.

## What this changes

- Historical sets A–G were labelled under v1 and **are not relabelled**. Every
  number computed on them keeps its v1 meaning and must say so.
- The engine's output is already single-primary in practice, so scoring does not
  change shape — only the reference gets cleaner.
- A v2 split (set H) should be labelled under this spec, with 3–4 readers, before
  the co-occurrence redesign is judged on mode-level numbers.

## Known costs

1. Rule 1 will pull many current `logic_or_validation` rows into
   `crash_or_error`. That is intentional: those bugs *do* manifest as failed
   requests. It will make `crash_or_error` look like the dominant class, which it
   already is for the engine.
2. Relabelling costs ~15 minutes per reader for 40 rows.
3. Two readers can still disagree on rule 1 vs rule 10 at the margin — the
   decision order reduces but does not eliminate that, because "failed outright"
   has edge cases (a 200 response carrying an error body).

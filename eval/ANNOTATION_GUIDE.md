# Annotation guide (v0.1 · DRAFT)

**Current status: 0 human labels, 0 accepted cases, 0 published metrics.**

This file exists to make the next step honest. `cte run` produces **candidates**
from deterministic rules. A candidate is not a labelled example and must never
be used to report accuracy, precision, recall, coverage, or a fix rate. Only a
human can turn a candidate into an accepted eval case.

## 1. What one label is about

One label = one **(feedback clause, failure mode)** pair. A single feedback item
may produce several clauses and therefore several labels. The classifier already
splits clauses on `。！？；;\n` and English sentence boundaries; the annotator
works on the quote in `findings[].evidence.quote`, which is **redacted text**.

## 2. The eight draft failure modes

| Mode | Include when | Exclude when |
| --- | --- | --- |
| `wrong_fact` | A number, source, or fact was invented or wrong | The user only says the answer was vague |
| `tool_misuse` | Wrong tool, bad arguments, duplicate/failed calls | The tool was right but slow (→ `loop_cost`) |
| `instruction_drift` | Explicit instruction on format/language/scope was ignored | The user never stated the constraint |
| `context_loss` | Forgot earlier turns, self-contradicted, asked again | New information was legitimately introduced |
| `boundary_gap` | Acted without approval, failed to refuse, leaked data | The user is describing their own mistake |
| `incomplete_task` | Stopped halfway, skipped steps, partial answer | The task was fully done but disliked |
| `loop_cost` | Infinite retry, repeated calls, latency, token burn | A single slow response with no repetition |
| `ux_friction` | Cannot interrupt, no undo, no progress, frozen UI | Model quality complaints (use other modes) |

If none fits, use `decision: rejected` and explain in `note`. **Do not invent a
ninth mode to rescue a bad fit** — record the disagreement instead. A growing
pile of `rejected` rows is evidence the taxonomy is wrong, and that is useful.

## 3. Hard rules (inherited from earlier keyword work)

These are not style preferences. Breaking any of them produces a number that
looks good and means nothing.

1. **The target set must never be defined by "the text contains this phrase".**
   That guarantees precision 1.00 by construction. Define the target by the
   failure mode, judged independently of the wording.
2. **When labels and the engine disagree, fix the labels, not the engine.**
   The taxonomy is a measuring instrument; it may not define its own target.
3. **Diagnose before editing the vocabulary.** Separate empty predictions from
   wrong predictions. Simulate the accuracy delta first; if it is zero, stop.
4. **Quantitative gate:** a signal is kept only if `occurrences in its own mode /
   occurrences everywhere >= 60%`. Over-general words are constrained by a
   same-clause context companion (`CONTEXT_REQUIRED`), not replaced by fancier
   synonyms. Replacing a phrase loses precision; constraining it gains it.
5. **Never use bare nouns.** A bare "数字" / "number" crosses many modes.
6. **Do not add word boundaries to English signals.** Real feedback concatenates
   words (`hallucinatednumber`). Substring matching is intentional.
7. **A context list must not contain one of its own weak phrases** — locked by
   `tests/test_taxonomy.py`.
8. **Deduplicate by clause text before computing document frequency.** Four
   duplicate scrapes can fake a 100% precision.
9. **Dev / hold-out split + gain must appear on both sides + human eyeballing.**
   A gain visible only on the dev set is overfitting.
10. **Redact before anything is quoted or published.** Offsets in reports refer
    to redacted text.

## 4. Label file format

`eval/labels.jsonl` — one JSON object per line. Lines starting with `//` are
comments and are ignored.

```json
{"case_id":"cte-0001","failure_mode":"wrong_fact","decision":"accepted","annotator":"jian935","note":"clear fabricated number"}
{"case_id":"cte-0002","failure_mode":"loop_cost","decision":"rejected","annotator":"anonymous","note":"actually a boundary issue, no repetition"}
```

- `case_id`: the candidate id from `report.json`
- `failure_mode`: one of the eight modes above (the **judged** mode, not the
  predicted one — if they differ, that disagreement is the valuable part)
- `decision`: `accepted` | `rejected` | `unsure`
- `annotator`: a name or `anonymous`
- `note`: short reason, mandatory for `rejected` and `unsure`

Check structure with:

```bash
cte validate --labels eval/labels.jsonl
```

`validate` checks fields only. **Inter-annotator agreement needs at least two
annotators**; v0.1 deliberately does not compute it and does not fake it.

## 5. Two-annotator workflow (L2)

1. Export candidates from a **public, licensed** corpus (see §7).
2. Split into `dev` / `hold-out` by clause text hash, after deduplication.
3. Two independent passes over the same candidates; `unsure` goes to arbitration.
4. Report agreement, then arbitration rules, then the confusion between modes.
5. Only then measure the taxonomy's precision against the labels — and publish
   the failures alongside the headline number.
6. Freeze the accepted set as a versioned artefact; CI checks it byte-for-byte.

## 6. Why the built-in demo looks good (and why that proves nothing)

`complaint_to_eval/demo.jsonl` was **written by the author to contain the exact
phrases in the taxonomy**, including deliberate negatives and a context-free
generic sentence. It is a wiring test, not a benchmark. 12 fabricated records
producing 11 candidates is a property of how the file was authored. It is never
evidence of precision, recall, coverage, or product value. Every generated
report repeats this warning.

## 7. Corpus sourcing (still TODO in v0.1)

Preferred, in order:

1. Public datasets with an explicit licence (e.g. HuggingFace conversational /
   feedback corpora) — record dataset name, version, licence, retrieval date.
2. GitHub issues of open-source agent projects — public, attributable, and
   quote-able; snapshot them instead of live-scraping.
3. App store / forum reviews — **only if the source ToS permits redistribution**.
   Do not scrape by default.

Never ingest: private support tickets, real user identifiers, application
materials, or anything from the author's own job-search data. Run
`cte privacy --path <data dir>` before publishing, and keep raw corpora in
`.local/` (gitignored). Aggregate numbers are safe; raw text is not.

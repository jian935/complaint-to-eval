---
name: complaint-to-eval
description: Turn user complaints, GitHub issues, app reviews or support feedback into UNREVIEWED agent regression-test candidates with evidence quotes and a draft failure-mode taxonomy. Use when someone pastes a batch of negative feedback or issue exports and asks "what should we test", "help me build an eval set from these complaints", "which failure modes keep coming back", or wants to compare which complaints disappeared between two releases. Also triggers on "把这些吐槽变成评测集" and "看看用户反馈里该测什么". Does NOT run evals, does NOT score a model, and never reports a fix rate.
---

# Complaint to Eval

## Purpose

Teams collect complaints but never turn them into tests. This skill turns a
feedback corpus into a shortlist of **candidate** regression cases that a human
can review, then stage into promptfoo / Langfuse. It answers one question only:
**what is worth testing, and what is the evidence that a user actually said it?**

It does not answer "is our agent good". It has no model, no labels, and no
ground truth.

## When to use

- A user pastes feedback, issues, reviews or chat logs and asks what to test.
- Someone wants to cluster complaints into failure modes with quotes attached.
- Someone wants to compare two releases by which complaints disappeared.
- Someone needs a starting point for an eval set and has no labelled data.

## When not to use

- Running evals, scoring a model, or gating CI. Use promptfoo / Langfuse after
  a human has accepted the cases.
- Computing a fresh accuracy number on someone's corpus. Labels do not exist yet,
  so any figure would be self-scored.
- Auditing numbers inside AI output (that is the `ai-claim-audit` skill).
- Deciding whether an A/B experiment can ship (that is `experiment-copilot`).

## Workflow

### 1. Establish provenance first, then pick the taxonomy

Ask where the text came from and whether redistribution is allowed. Then decide
**which** taxonomy fits — this matters more than any flag:

```bash
# Issue-tracker export (GitHub/GitLab issues): defect modes, 10 classes
cte defects --input issues.jsonl --real --out out/defects

# Free-form feedback (reviews, chat logs, support tickets): LLM-behaviour modes
cte run --input feedback.jsonl --real --out out/report

# Fabricated data in either case
cte defects --input issues.jsonl --synthetic --out out/defects
```

Rule of thumb: if the text contains tracebacks, env vars and file paths it is a
**defect report**, not a complaint, and `cte run` will find almost nothing
(measured: 1 of 81 behaviour signals appeared across 272 real issues). If it says
"it made something up" in prose, use `cte run`.

Never omit both provenance flags. Never paste private tickets into a public
repo. Raw corpora belong in `.local/`.

### 2. Read the honesty header before the table

`out/report.md` starts with provenance, candidate count, and
**accepted = 0**. Read it aloud to the user. A high candidate count from the
built-in demo means nothing: that file was written to contain the taxonomy's
own phrases.

### 3. Redaction already happened

Every quote is redacted text; offsets refer to that redacted text. If a user
pastes raw identifiers, run `cte privacy --path <dir>` and redact before
sharing anything.

### 4. Human review is the actual work

Walk the findings with the user. For each candidate decide `accepted`,
`rejected`, or `unsure`, and record the **judged** failure mode — which may
differ from the predicted one. Those disagreements are the valuable output.
Write labels to `eval/labels.jsonl` and check structure:

```bash
cte validate --labels eval/labels.jsonl
```

Rules: never define the target set by "the text contains this phrase"; when
labels and rules disagree, fix the labels, not the engine; diagnose empty
predictions separately from wrong predictions; require a >=60% precision gate
before adding a signal; constrain generic phrases with same-clause context
instead of replacing them; deduplicate by clause text before counting. See
`eval/ANNOTATION_GUIDE.md`.

### 5. Compare releases without claiming improvement

```bash
cte diff --base out/v1/report.json --head out/v2/report.json
```

Say "resolved candidates", never "fix rate". A disappeared phrase is a
disappeared phrase, not proof that a defect was fixed.

### 6. Hand off downstream

`out/promptfoo-candidates.json` is a staging file, **not** a runnable config.
A human picks reviewed cases and copies them into `promptfooconfig.yaml`.
This project feeds promptfoo / Langfuse; it does not replace them.

## Hard rules

1. Every generated case is an unreviewed **candidate**. Never call it a label,
   a ground truth, or an eval set. `accepted_cases` is always 0.
2. The only precision/recall figures that exist are in
   `eval/defect_holdout/README.md`, measured against **model** labels on the A–G
   disjoint splits. Cite the range (mode-level precision 0.71-0.77) and say
   "model-labelled", never "human accuracy". **Split G also has four blind human
   readers**: they agree strongly on whether something is a defect (Fleiss
   κ = 0.922) but not on the mode, and against them mode-level precision is
   **0.23-0.38** — so treat 0.71-0.77 as an upper bound. **Split H has one
   workbook** under a rewritten one-primary-mode rule (0.545 / 0.429): different
   split, different prior, one source — do not compare it with the G numbers.
   That source is **unconfirmed** and a second returned workbook was rejected as
   non-independent, so never call it inter-annotator agreement or human accuracy.
   Do not compute a new accuracy number from a user's corpus — there is nothing
   to compare it to.
3. Be blunt about coverage: the engine is validated only for crashes. On the
   newest clean split it caught 13 of 15 crash reports and 2 of 12 other defects.
   If a user's corpus is mostly UI/i18n/data bugs, say the tool is weak there
   before they rely on it.
4. The built-in demo is FABRICATED. Never quote its hit count as evidence.
5. Never add a keyword without a failing example and a precision check against
   labelled data. No bare nouns (a topic word is not a defect claim); English
   signals match on a start-of-word boundary; quoted code is blanked before
   matching.
6. Redact before quoting, logging, or publishing.

## Command reference

| Command | Purpose |
| --- | --- |
| `cte demo` | FABRICATED wiring demo |
| `cte defects --input F --out D [--real\|--synthetic]` | defect modes (10) for issue trackers |
| `cte run --input F --out D [--real\|--synthetic]` | LLM-behaviour modes (8) for feedback text |
| `cte diff --base A --head B` | candidate diff between runs |
| `cte validate --labels F` | label-file structure check |
| `cte taxonomy` / `cte defect-taxonomy` | print a taxonomy + verify invariants |
| `cte privacy --path DIR` | residual personal-data scan |

Requires `pip install .` (or run `python -m complaint_to_eval` from the repo
root). Standard library only; no API key; fully offline.

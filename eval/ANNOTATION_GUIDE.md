# Annotation guide

**Current status: split G has four independent human readers (v1). Split H has
one confirmed human reader under v2, plus a second workbook rejected as
non-independent — see
[`defect_holdout/contamination_h.md`](defect_holdout/contamination_h.md).
0 accepted cases.** Every other measurement is compared against
**model-generated** labels (`annotator: model`), and every result file says so. On
split G the four readers agreed strongly on *whether* a row is a defect
(Fleiss κ = 0.922) but not on its mode; single-mode labels fell inside the
two-mode union 20/20, 20/21 and 19/20 — i.e. most mode "disagreement" is
granularity, not judgement. See
[`defect_holdout/multi_annotator.md`](defect_holdout/multi_annotator.md).
That finding produced [`GRANULARITY_RULE.md`](GRANULARITY_RULE.md) (v2), which
set H used; results in
[`defect_holdout/human_agreement_v2.md`](defect_holdout/human_agreement_v2.md). This
guide has two parts because the repo carries two taxonomies:

- **Part A — defect reports** (`cte defects`, 10 modes): the current focus, and the
  only path with published numbers.
- **Part B — feedback text** (`cte run`, 8 modes): the original v0.1 path, kept for
  the text it was designed for.

In both: a candidate is **not a labelled example**. It may never be used to report
accuracy, precision, recall, coverage or a fix rate. Only a human can turn a
candidate into an accepted eval case.

---

# Part A — defect reports (10 modes)

## A1. What one label is

One label = one **(defect report, set of modes)** row. Multi-label: a report can
contain a crash *and* a security issue. `modes: []` means "this is not a defect
report" — a feature request, a chore, a question, a vendor pitch, spam. **That empty
label is data, not a gap**; precision is meaningless without it.

Judge the **report**, not the wording. If the report says "it silently drops my
edits" the mode is `data_integrity` even though the word "data" never appears.

**Granularity is now fixed by v2 — but A–G remain v1 legacy.** Four readers on
one split disagreed more about how many modes to write than about which: two wrote
1.7 per defect, two wrote 1.0, and every single-mode pick fell inside the
two-mode union (20/20, 20/21, 19/20). Set H therefore uses
[`GRANULARITY_RULE.md`](GRANULARITY_RULE.md): **exactly one primary mode by
symptom order, up to two cause modes in a separate column**. Sets A–G were
labelled before that rule: they record every supported mode as a set. Never
compare an A–G mode set with H's primary column, and never quote a v1 and a v2
mode-level precision in the same sentence as a trend — the measuring instrument
changed, and so did the class prior.

## A2. The ten modes

| Mode | Include when | Exclude when |
| --- | --- | --- |
| `crash_or_error` | Uncaught exception, traceback, segfault, "page crashes", HTTP 500 aborting the operation | An error message the user merely quotes as expected behaviour |
| `data_integrity` | Stored or transferred data lost, truncated, corrupted, miscounted | A computed value is wrong but nothing was persisted (→ `logic_or_validation`) |
| `logic_or_validation` | Wrong value/control flow: type coercion, missing validation, duplicate execution, wrong exit status, double encoding | The setting existed and was ignored (→ `config_or_env`) |
| `config_or_env` | Env var / config / default ignored or not applied; install broken | A behaviour bug that happens to mention a config file |
| `ui_or_ux` | Clipping, misalignment, blocked input, lost focus, stale render, wrong direction | A feature request *about* a UI element |
| `i18n_or_locale` | Missing or wrong translation, fallback to English, wrong locale formatting | Code that merely mentions locales |
| `security` | Traversal, unauthorized action, confirmation bypass, arbitrary execution, injection | A report that says "security" while describing a functional bug |
| `performance` | Slow, timeout, hang, leak, N× overhead | A proposal that would be faster (that is a feature) |
| `regression` | Worked before, stopped working after version X | "Add regression tests" |
| `docs` | Missing/undocumented step, stale README, wrong architecture guide | A docs contribution that adds an example |

**When two modes both fit, pick the one naming the harm, not the mechanism.** A
parser bug that truncates an answer is `data_integrity`; a parser bug that returns
the wrong document is `logic_or_validation`. Write the reasoning in `note`.

### Recurring boundary decisions (already applied to sets A–G)

- **Truncation of a *computed* value stays `data_integrity`** if the report's own
  wording is truncation (uuidv7 overflow). A phrase list cannot tell "stored data
  truncated" from "computed value truncated"; pretending otherwise would be worse
  than the known overlap.
- **Static-analysis output** (a pasted type-checker error) has no mode. Label
  `crash_or_error` and say so in the note — it is the closest fit, not a good one.
- **A silent wrong exit status** is `logic_or_validation`, not `config_or_env`, even
  when a CLI flag is involved.
- **A feature request that lists performance numbers** is `[]`, not
  `performance`. This is the single most common false positive the engine makes.

## A3. Label file format (sets A–G)

`eval/defect_holdout/labels_holdout*.jsonl`, one JSON object per line, compact JSON:

```json
{"record_id":"dify-45934","modes":["ui_or_ux"],"annotator":"model","note":"Detail sidebar collapse drops keyboard focus"}
{"record_id":"aider-5865","modes":[],"annotator":"model","note":"Feature request (model pipeline profiles), no defect asserted"}
```

- `record_id`: matches `.local/corpus/*.jsonl` and `partitions*.json`
- `modes`: any subset of the ten, or `[]`
- `annotator`: **must be `model`** until a human does a pass. `tests/test_holdout_labels.py`
  fails the build if any row claims otherwise — that lock exists because writing
  "human" here would convert a self-check into a fake result.
- `note`: mandatory; for boundary cases write the reasoning, not just the mode

Structure is locked in CI by `tests/test_holdout_labels.py`: parseable, known modes,
`annotator == "model"`, labels match `partitions_*.json`, and **all seven sets are
pairwise disjoint**.

## A4. Contamination rule (the one that matters)

Once you have read a split's misses or false positives, **that split is burned**.
Any change motivated by it must be validated on a split no change has ever seen.
That is why seven sets exist, and why `migrations.md` lists every label edit with its
old value. Retrofitting labels to a set you just scored is the same sin as tuning on
the test set.

Practical loop:

1. Score set N, read its misses and false positives.
2. Change something for a stated *principle* (not "to fix these five rows").
3. Draw set N+1 with a new salt, excluding every earlier id.
4. Label N+1 without looking at engine output, score it, publish **both** numbers.
5. Never edit N's labels afterwards without recording it in `migrations.md`.

## A5. Class prior is part of the label

The two source repos are defect trackers, so random splits are ~88% defects, which
inflates precision. If you add labels, also record **what fraction are `[]`**.
`scripts/draw_holdout_g.py` shows how to build a deliberately balanced 20/20 set, and
`eval/defect_holdout/README.md` shows how to reweight precision to other priors. A
precision number without its class mix is not a result.

## A6. Corpus sourcing

1. Public datasets with an explicit licence — record name, version, licence, date.
2. GitHub issues of open-source projects — public, attributable; **snapshot** them
   (`scripts/build_corpus_from_issues.py`) instead of live-scraping.
3. App store / forum reviews — only if the ToS permits redistribution.

Never ingest private tickets, real identifiers, or the author's own application
materials. Run `cte privacy --path <dir>` before publishing; raw corpora stay in
`.local/` (gitignored). Short paraphrases in `note` are acceptable; full issue text
is not shipped.

---

# Part B — feedback text (8 modes, v0.1)

Measured result: run over 428 real GitHub issues, **1 of 81 strong signals** ever
appeared and the original 191-issue snapshot produced a single candidate. Those
trackers hold defect reports, not complaints. Keep this path for genuinely
complaint-shaped text; do not expect it to work on an issue export.

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
ninth mode to rescue a bad fit** — record the disagreement instead.

### Label format for `cte run`

```json
{"case_id":"cte-0001","failure_mode":"wrong_fact","decision":"accepted","annotator":"jian935","note":"clear fabricated number"}
```

`decision`: `accepted` | `rejected` | `unsure`. Check with
`cte validate --labels eval/labels.jsonl` (structure only).

### Rules that still apply

1. **The target set must never be defined by "the text contains this phrase".** That
   guarantees precision 1.00 by construction.
2. **When labels and the engine disagree, fix the labels, not the engine.**
3. **Diagnose before editing the vocabulary.** Separate empty predictions from wrong
   ones; if the simulated delta is zero, stop.
4. **Quantitative gate:** keep a signal only if it occurs in its own mode ≥60% of the
   time. Constrain over-general words with same-clause context instead of swapping
   synonyms.
5. **Never use bare nouns.** This rule was violated in rounds 1–5 of the defect
   taxonomy (`security`, `layout`, `locale`, `performance`) and every one of them
   produced topic-word false positives. It is now enforced by tests.
6. **Do not add word boundaries to `cte run`'s English signals** — real feedback
   concatenates words. The defect path is the opposite: start-of-word boundaries,
   because issue reports are well-formed and `hang` must not match inside `changes`.
7. **Redact before anything is quoted or published.** Offsets refer to redacted text.

---

# Two-annotator workflow (L2, not done)

1. Export candidates from a **public, licensed** corpus.
2. Split dev / hold-out by record hash, after deduplication.
3. Two independent passes; `unsure` goes to arbitration.
4. Report agreement, then the arbitration rules, then the mode confusion matrix.
5. Only then measure precision against human labels — and publish the failures next
   to the headline number.
6. Freeze the accepted set as a versioned artefact; CI checks it byte-for-byte.

## Why the built-in demo looks good (and why that proves nothing)

`complaint_to_eval/demo.jsonl` was **written by the author to contain the exact
phrases in the taxonomy**, including deliberate negatives and a context-free generic
sentence. It is a wiring test, not a benchmark. 12 fabricated records producing 11
candidates is a property of how the file was authored. It is never evidence of
precision, recall, coverage, or product value.

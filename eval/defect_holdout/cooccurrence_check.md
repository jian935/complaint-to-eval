# The co-occurrence redesign failed on unseen text

**Result: negative. The proposed replacement for the phrase list recovered 0 of
4 `data_integrity` rows on a split it had never seen, and produced 11 false
positives. It is not a better engine.** It ships only as a reproducible
experiment (`cte cooccurrence`), never wired into `cte defects`.

Raw data: [`cooccurrence_check.json`](cooccurrence_check.json) · Design note:
[`cooccurrence_design.md`](cooccurrence_design.md) · Reproduce with
`python scripts/eval_cooccurrence.py`.

> **On the quotes below.** This page quotes a few **short phrases from public
> issue titles** to show what the probe matched. The machine-readable result
> file stores **record ids, modes and offsets only** — no issue text — the same
> rule as `results_f.json` / `results_g.json`. The corpus itself is never
> redistributed.

## The single most important number is a gap

| Split | Role | Precision | Recall |
|---|---|---:|---:|
| **H** (40 rows, one confirmed human reader) | **design set — effectively the answer key** | 0.600 | **0.900** |
| **I** (40 rows, model labels, never seen by the rule) | **only validation set** | **0.000** | **0.000** |

H's 0.900 is not a success. Several fault entries in the probe (`without
restoring`, `does not send`, `returns nothing`, `second time`, `offset`,
`twice`, `discard`, `drop`) were taken **verbatim from H report titles**. The
design note says so explicitly. A rule written from the answer key fitting the
answer key has zero predictive content; H is recorded with
`publishable: false` and is shown here only to measure how much of the design
was memorisation.

Split I was drawn **after** the vocabulary was frozen. Its fingerprint
`0af2ac57…` is stored in [`partitions_i.json`](partitions_i.json) and checked
by the evaluation script — editing one word in the vocabulary invalidates the
split and the script exits 2. No I text was used to choose an entry. **The
vocabulary was not changed after seeing these results.**

## Full comparison on split I (n = 40, 4 `data_integrity` rows)

| Engine | TP | FP | FN | P [95% CI] | R [95% CI] |
|---|---:|---:|---:|---|---|
| v0.1 phrase list | 0 | 1 | 4 | 0.000 [0.000, 0.793] | 0.000 [0.000, 0.490] |
| topic+fault probe | 0 | **11** | 4 | 0.000 [0.000, 0.259] | 0.000 [0.000, 0.490] |
| flag everything as `data_integrity` | 4 | 36 | 0 | 0.100 [0.040, 0.231] | 1.000 [0.510, 1.000] |

**Do not read this as "the new design is worse".** With four positive rows,
both recall intervals are [0.000, 0.490] and the precision intervals overlap
heavily; this sample cannot establish a difference in P or R. What *is* a
plain count, and needs no inference, is that the probe emitted **11 candidates
where the phrase list emitted 1**, and none of the 11 was a
`data_integrity` row. It is noisier, and there is no evidence it is better.

## Why all 11 were wrong

The rule asks "do a data noun and a fault word appear in the same clause?".
That is still lexical matching — just two words instead of one. It cannot tell
whether the fault word is *about* the data noun, or whether the report is
asserting a defect at all:

- `double` in *"retry delay appears to double"* (a hardening suggestion),
  *"query and result doubles in api/tests"* (test doubles / mocks), and
  *"tokens consumed are double"* (a performance regression).
- `skip` / `swallow` / `remove` / `drop` in ordinary prose: *"instead of just
  skipping that hunk"*, `SKIP_DOM_SELECTION_TAG`, *"Remove obsolete New RAG
  documentation type suppressions"*, *"the file card is dropped"*.
- *"page loses its sidebar on refresh"* — a UI element disappearing, not data.
- *"Missing required values still block the request"* — the report's
  **expected** behaviour, not the bug.
- `instead of` in a sentence about an iteration cap.

## Why all 4 real rows were missed

| I row | What the report says | Fault wording |
|---|---|---|
| `aider-5508` | leaderboard says 90.0% where the formula gives 100.0%; `pass_rate_2` uses a different denominator | `inconsistencies`, `should read`, `different denominator` |
| `dify-45390` | `file_count` returns 3 for exactly 2 files | `counts directories`, `returns 3` |
| `dify-45423` | inputs validated and stored but never forwarded to the agent | `never reach`, `never forwarded` |
| `dify-45555` | renamed display name reverts on publish | `is reverted`, `reads the old name` |

None uses a single word from the frozen fault vocabulary. The H failures were
mostly *"content was dropped"*; the I failures were *"a number is wrong"*,
*"a value was not persisted"*, *"a field was not forwarded"*. A list of
phrases — doubled, tripled, or conditioned on co-occurrence — keeps chasing
wording instead of meaning.

## A known implementation limit, deliberately left unfixed

The negation check for positive fault words looks only 12 characters before
the fault word. It suppresses *"images are not dropped"*, but a sentence-initial
*"No images are dropped"* still produces a candidate. This was found **after**
split I was scored. Fixing it would mean editing the implementation with I's
results in hand, which converts a frozen validation split into a tuning set.
The **negation window** limitation is therefore documented and locked by a
test, not patched. It would have reduced false positives by an unknown amount;
it would not have created a true positive, because none of the four real rows
contains a fault word at all.

## Honesty limits, in writing

1. **Labels are MODEL-generated** (`annotator: model`), as in splits A–G. The
   label writer also designed the probe and knew the hypothesis. Labels were
   written before either engine was run on I, but this is **not independent
   human judgement**. These are agreement-with-model-labels, not accuracy.
2. **4 positive rows out of 40** → very wide intervals. No claim about recall
   is supportable. This is a design check, not a benchmark.
3. Split H's human labels are real, but H is the **design set**; its
   0.600 / 0.900 must never be quoted as a performance result.
4. Nothing here is an accepted eval set. `accepted_cases` stays 0.
5. `cte defects` is **unchanged**; every previously published number still
   refers to the v0.1 phrase list.

## What this does to the roadmap

The earlier conclusion — *"the phrase list is at a plateau; adding words will
not help"* — is now stronger, not weaker: **changing the shape of the word
list did not help either.** What is missing is a judgement about grammatical
roles and about whether the reporter asserts the result is wrong. That is not
something a deterministic standard-library rule set can honestly claim, and
this project does not pretend to have solved it. The redesign is closed as a
documented negative result rather than kept as a promising TODO.

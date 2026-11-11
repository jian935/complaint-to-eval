# Why the phrase list cannot say "it ran, but the content is wrong"

**Status: design note. Split H is the DESIGN set here, never a validation set.**
The examples below are the reason a new rule was written; quoting a score from
them would be circular. The only validation split for this line of work is
[`I`](partitions_i.json), drawn after the rule vocabulary was frozen.

## The observation

On split H, one confirmed human reader marked **10 rows** as `data_integrity`.
The v0.1 phrase-list engine produced `data_integrity` on **1** of them
(micro P 0.20 / R 0.10 against that reader, from
[`human_agreement_v2.json`](human_agreement_v2.json)).

That single "hit" is not a success. `dify-44952` is titled *"EML knowledge
extraction decodes already-parsed email text a second time"*, and the engine
fired on the word **`corrupt`** in a later sentence, *"Both corruptions
reproduce for all three transfer encodings"*. It matched a word about
reproduction steps, not the reported fault. The honest reading is **0 of 10
correctly reasoned**, plus one accidental lexical collision.

A second row, `dify-45238` (*"Retrying a segment status change after broker
failure succeeds without restoring its index"*), was marked `ui_or_ux` by the
engine because the word **`stale`** appears in a different sentence —
`"stale keywords are removed after retry"`. `stale` is a fault-shaped signal in
the phrase list, but here it describes cache state, not an interface defect.

## What the nine misses actually say

| Row | Title (abbreviated) | Fault expression used | Why no phrase matched |
|---|---|---|---|
| aider-5516 | Cached tokens are **billed twice** | `billed twice`, `charges ... twice` | `twice` exists only inside `logic_or_validation` compounds (`runs twice`) |
| dify-45227 | Text queries **discard image candidates** | `discard` | `discards` lives in `logic_or_validation`; here it is data loss |
| dify-44904 | DOCX extraction **silently drops embedded images** | `silently drops embedded` | the signal is `drops the`; one different article breaks it |
| dify-44737 | Keyword search **treats % and _ as LIKE wildcards** | `treats ... as` | no phrase describes a value being reinterpreted |
| dify-45183 | Image removal **keeps inline images and deletes text** | `keeps ... and deletes` | needs two predicates in one clause; a one-phrase list cannot |
| dify-45238 | ... **succeeds without restoring its index** | `without restoring` | `without` is a NEGATOR, so the clause is suppressed outright |
| dify-45004 | Credential lookup **returns nothing** | `returns nothing` | `silently returns an empty` is in the *wrong* mode |
| dify-44987 | Timestamps are **offset by the host timezone** | `offset by` | no signal for a wrong value |
| dify-45434 | Agent node **does not send uploaded images** | `does not send` | `doesn't` is a NEGATOR; the clause is suppressed |

Four shapes, none of which is "a bigger list of phrases":

1. **A data-bearing noun + a loss verb** (`images` × `discards/drops/not send`).
2. **A data-bearing noun + a wrong-value expression** (`timestamps` × `offset`,
   `tokens` × `billed twice`).
3. **Two predicates in one clause** (`keeps X and deletes Y`).
4. **Negation-shaped wording that is the fault itself** (`without restoring`,
   `does not send`). The current engine treats `without` / `doesn't` / `not`
   as negators and *deletes* the clause. This is the single most damaging
   design flaw found here: the defect is phrased as an absence.

## The proposed change (frozen before split I was drawn)

`complaint_to_eval/cooccurrence.py` scores a **clause**, not a word:

- **topic words** — nouns that can carry content: `token`, `image`, `file`,
  `text`, `index`, `timestamp`, `credential`, `attachment`, `candidate`,
  `chunk`, `record`, `row`, `email`, `content`, `output`, `count`, `cache`,
  `message`, `metadata`, `page`, `link`, `result`, `query`, `segment`.
- **fault words** — four families: *missing/lost*, *duplicated/multiplied*,
  *wrong value*, *truncated/partial*.
- A `data_integrity` candidate is emitted **only when a topic and a fault occur
  in the same clause**. Neither list may fire alone.
- Code spans are blanked (reusing `blank_code`), and the boilerplate
  "Self Checks" block of issue templates is excluded, because
  *"I have searched for existing issues"* contains both `issue` and negation
  and would otherwise manufacture hits.
- Absence-wordings (`without restoring`, `does not send`, `returns nothing`)
  are **fault words**, not negators. A negator check still applies to positive
  fault words, but only in a **12-character window immediately before** the
  fault word — it suppresses *"images are not dropped"*, and does **not**
  suppress *"No images are dropped"*. That limitation was discovered after
  split I had been scored and is recorded rather than patched; changing the
  implementation after the fact would make I a tuning set.

Two deliberate limits, stated up front:

- This is a **single-mode probe**. It does not re-implement the other nine
  modes and is not a replacement engine. `cte defects` is unchanged.
- **Correction, written after seeing split I:** the claim that this vocabulary
  is "general English plus shapes" is too generous. Several fault entries were
  taken **verbatim from H titles** — `without restoring`, `does not send`,
  `returns nothing`, `second time`, `offset`, `twice`, `discard`, `drop`.
  That is exactly why the probe recovers 9 of H's 10 rows. Split H is therefore
  not merely "the design set", it is effectively the **answer key** for part of
  the vocabulary. Its 0.600 / 0.900 is a fit measure with no predictive
  meaning, and is recorded as `publishable: false`.
- What *is* still clean: the vocabulary was frozen (hash in
  [`partitions_i.json`](partitions_i.json)) **before** any split-I text was
  read, and no I text was used to choose an entry. I is genuinely unseen by the
  rule, which is why its 0 / 4 result is the only informative number here.
  The gap between H and I measures how much of the design was memorisation.

## What would count as a failure

If the co-occurrence probe merely moves errors around — recovering
`data_integrity` rows while adding false positives on clean rows or on other
modes — that is the result to publish. The point of this experiment is to test
a *design*, not to produce a larger precision number. Four rounds of adding
and stripping phrases already showed the phrase list is at a plateau
(0.71–0.77); a redesign that only relabels the plateau is a negative result,
and a negative result is still a result.

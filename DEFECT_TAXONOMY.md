# Defect-report taxonomy (`defect-0.1.0-draft`)

**Status: DRAFT. Model-evaluated on six disjoint hold-out splits; one split has
four human readers.** Most precision/recall figures are measured against **model
labels** — see [`eval/defect_holdout/README.md`](eval/defect_holdout/README.md).
Split G was also annotated blind by four independent readers: they agree strongly
on whether a row is a defect (Fleiss κ = 0.922) but not on its mode, and against
them **mode-level micro precision is 0.23–0.38** rather than 0.71–0.77. See
[`eval/defect_holdout/multi_annotator.md`](eval/defect_holdout/multi_annotator.md).
`accepted_cases` is still 0 — a labelled split is not an accepted case set.

**Read this first: in practice the engine is a crash detector, and its precision is
a function of how broken the queue is.** On the newest random split it found 13 of
15 crash reports and 2 of 12 non-crash defects. On a deliberately balanced 50/50
split (set G) record-level precision was **0.632**, against **0.500 / 1.000** for the
trivial "flag everything" rule. Mode-level precision has sat at 0.71–0.77 across four
rounds of signal changes. Everything except `crash_or_error` is unproven. This
document explains why the taxonomy exists, how it was derived, what it does on real
data, and exactly where it is weak.

## Why a second taxonomy

The original eight modes in `taxonomy.py` target **natural-language complaints
about LLM behaviour** (`wrong_fact`, `loop_cost`, `context_loss`, …). To test
whether they generalise, the engine was run over **272 real GitHub issues**
(aider 136, dify 136, lobe 8 — all public, permissively licensed, redacted):

- **1 of 81 strong signals** ever appeared in that text.
- **1 candidate** was produced across the original 191-issue snapshot.

The reason is not only that the signals were over-fit to the fabricated demo; it
is that **issue trackers of AI tools are software defect trackers, not complaint
corpora**. 79% of aider issues are auto-filed crash reports (`Uncaught
ImportError in _svdp.py…`); dify issues are UI/config/data bugs. Users do not
write "it hallucinated" in an issue tracker — they paste a traceback.

So this taxonomy classifies **the text that actually occurs**, and the pipeline
turns it into candidate regression cases. See `.local/audit/FINDINGS.md` for the
full investigation (kept local; it is not shipped).

## The ten defect modes

| Mode | Fire when | Canonical example |
| --- | --- | --- |
| `crash_or_error` | Uncaught exception, traceback, crash, segfault | `Uncaught ImportError in main.py` |
| `data_integrity` | Data lost, dropped, truncated, corrupted, miscounted | `rows silently truncated on export` |
| `logic_or_validation` | Wrong value or control flow: coercion, bad validation, duplicate run, wrong exit status | `exits 0 when main() returns 1` |
| `config_or_env` | Env var / config ignored or not applied; install broken | `ENV_VAR is ignored in STARTTLS mode` |
| `ui_or_ux` | Clipping, misalignment, blocked input, lost focus, stale render | `preview is covered by main content` |
| `i18n_or_locale` | Missing/wrong translation, English fallback | `falls back to English for Arabic locales` |
| `security` | Traversal, unauthorized action, bypass, arbitrary exec | `path traversal outside the repository` |
| `performance` | Slow, timeout, hang, leak | `the worker hangs and never returns` |
| `regression` | Worked before, stopped working, regressed since a version | `this worked before v0.86` |
| `docs` | Missing/undocumented setup step, README gap | `readme is missing the setup step` |

## Matching rules (same discipline as the LLM taxonomy, three deliberate changes)

- **No bare nouns.** Only fault-shaped signals. `security`, `locale`, `layout`,
  `sidebar`, `tooltip`, `chevron`, `performance`, `latency` were **removed** in
  round 5 because they fire on topics, not claims: "security concerns", "delivery,
  security, and migration requirements", "doc translation", "high-performance
  models". A topic word is not a defect.
- **Negation scope** cancels a hit: "no uncaught exception was observed" is not a
  crash. A negator in a *previous* clause does not leak forward.
- **Redact first**; evidence offsets refer to redacted text.
- **Blank quoted code before matching.** Defect reports quote code — a repro
  snippet contains `timeout=120`, an error name appears in `except ValueError`, a
  traceback is pasted in a fence. `blank_code()` replaces fenced blocks and inline
  code spans with **spaces of the same length**, so matching ignores code while
  offsets (and therefore evidence quotes) stay exact. Added in round 4; it removed
  every crash false positive in that round's set.
- **One candidate per (record, mode)** — a crash dump with fifty `Traceback` lines
  yields one `crash_or_error` candidate, not fifty.
- **English matches on a start-of-word boundary.** This *differs* from
  `taxonomy.py`, which forbids word boundaries because real feedback concatenates
  words. Defect reports are well-formed English. The boundary lets a prefix signal
  catch inflections (`truncat` → `truncated`, `hang` → `hangs`) while stopping
  `hang` from firing inside `changes`.

## What it does on real data (in-sample: the corpus it was read from)

| Corpus | Records | Classified | Unclassified | Candidates | Top modes |
| --- | ---: | ---: | ---: | ---: | --- |
| aider (Apache-2.0) | 136 | 121 | 15 | 123 | crash 109, security 4, data 3, config 3 |
| dify (Apache-2.0 + additional conditions) | 136 | 70 | 66 | 88 | ui 22, data 21, crash 15, perf 13 |

**Read this as coverage, not accuracy.** dify's `ui` 22 and `data` 21 look strong
until they are measured: on the hold-out, `ui` precision was 0.00/0.67 and
`data_integrity` recall 0.00–0.14. Coverage and correctness are different numbers
and this project reports both.

## Open question: one mode or many

Four readers labelled the same 40 rows. Their single biggest disagreement was not
*which* mode is right — it was **how many modes to write down**.

- Two readers wrote **1.7 modes per defect** (symptom *and* cause).
- Two readers, and this project, wrote **1.0**.
- Every single-mode label fell inside the two-mode union: **20/20, 20/21, 19/20**.

So "the annotators disagree" is mostly "some annotators record the pair
`data_integrity` + `logic_or_validation`, others record whichever they consider
primary". The scorer compares mode *sets*, so this choice silently moves every
mode-level number.

Two rules have to be written before the next measurement:

1. **Granularity** — one mode per report (the primary fault), or every mode the
   report supports? If the former, the guide must say how to pick the primary one.
2. **Symptom vs cause** — a value truncated by a type coercion is both
   `data_integrity` (what the user saw) and `logic_or_validation` (why it
   happened). Both are currently accepted, so two careful readers can differ
   without either being wrong.

Until those rules exist, quote mode-level precision with the reference reader
named, and put the ≥3-of-4 consensus figure beside it.

## Honest limits

- **Only `crash_or_error` is validated.** Across clean splits it holds 0.95–1.00
  precision and 0.87–1.00 recall. On the newest split it caught **13 of 15
  crashes and 2 of 12 non-crash defects** — that ratio is the honest headline.
- **Precision depends on the class prior, and the default corpora are 88% defects.**
  Measured on a balanced 50/50 split it is 0.632; reweighted to a 25%-defect queue it
  is 0.36. Never quote a precision figure without the mix it came from. Table in
  [`eval/defect_holdout/README.md`](eval/defect_holdout/README.md).
- **`crash` detection is vocabulary-bound.** It needs `Uncaught`/`Traceback`. A report
  that describes the same failure in prose ("returns 400", "is not a function") is not
  recognised; on the balanced split crash precision was 0.00.
- **Over-flags non-defects.** 7 of 20 clean records on the balanced split (35%):
  feature proposals and vendor pitches that mention technical words.
- **Two repos is not a domain sample.** Both are AI-tool projects.
- **Phrase iteration has plateaued.** Rounds 2→6 added signals, removed signals,
  stripped code and added a whole mode; precision stayed in 0.71–0.77. The next
  gain needs a different design (topic+fault co-occurrence), not more phrases.
- **`logic_or_validation` did not earn its place yet.** Added in round 6 to stop
  exit-status, coercion, validation-gap and duplicate-execution bugs from polluting
  `config_or_env` / `data_integrity`. It caught **0 of 5** such cases on the fresh
  split: the real phrasings ("stringified to Python repr", "accepts a trailing
  newline", "overwrites action_name") were not anticipated. The mode is
  conceptually right; the signals are not there.
- **Human passes are not validation either.** Split G has four blind readers. They
  agree strongly on *whether* a row is a defect (Fleiss κ = 0.922) and disagree on
  the mode — but most of that disagreement is granularity (single-mode picks land
  inside the two-mode union 20/20, 20/21, 19/20), not judgement. The remaining
  ambiguity is real and unfixed: see "Open question" above. Every output is a
  candidate. `accepted_cases` is always 0.

## Progress log

1. ✅ Split into dev / hold-out by record hash.
2. ✅ Model-label the hold-out (tagged `annotator: model`, never posing as human).
3. ✅ Measure precision/recall with Wilson intervals and publish the misses.
   Round 1 (untuned, set A): 0.815 / 0.667.
4. ✅ Round 2 (new signals, fresh set B): 0.917 / 0.846 — **later shown to be
   optimistic**.
5. ✅ Round 3 (clean set C): **0.711 / 0.771**.
6. ✅ Round 4 (blank quoted code, fresh set D): **0.774 / 0.649**.
7. ✅ Round 5 (remove bare topic nouns, fresh set E): **0.710 / 0.629**.
8. ✅ Round 6 (add `logic_or_validation`, migrate 18 boundary labels, fresh set F):
   **0.714 / 0.556**. Record-level detection 0.944 / 0.630; trivial "flag
   everything" scores 0.844 / 1.000, so recall is *not* beaten.
9. ✅ Round 7 (set G, hand-built 20/20 to fix the class prior): record-level
   **0.632 P / 0.600 R** against 0.500 / 1.000 for "flag everything"; 7 of 20 clean
   records wrongly flagged; `crash_or_error` precision 0.00 because those reports
   never use crash vocabulary.
10. ✅ Round 8 (human check on set G, n = 39, blind): the binary "is it a defect"
    call replicated on **39 of 39** rows (κ = 1.000 vs the existing labels), while
    the **mode** labels disagreed on 8 of 19 defect rows. Against the human,
    mode-level micro precision is **0.31 / 0.32**, not 0.71–0.77;
    `logic_or_validation` caught 1 of 11.
11. ✅ Round 9 (four independent readers on set G): Fleiss κ = **0.922** on the
    binary call; κ against the engine **0.202–0.305**; as a fifth rater the engine
    drags group agreement from 0.911 to **0.633**. Mode-level precision against
    each reader is **0.23–0.38** (0.31 / 0.32 against a 3-of-4 consensus). Two
    project labels are wrong (r05, r38) and are published, not patched.
12. ⏳ Not done: the granularity / symptom-vs-cause rule; the co-occurrence
    redesign; a sentence-level segmenter.

Treat `cte defects` as a working prototype: reliable on crash reports, weak on
everything that requires reading comprehension, and honestly measured.

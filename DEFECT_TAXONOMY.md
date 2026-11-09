# Defect-report taxonomy (`defect-0.1.0-draft`)

**Status: DRAFT. Model-evaluated on five disjoint hold-out splits, NOT human-validated.**
All precision/recall figures are measured against **model labels** — see
[`eval/defect_holdout/README.md`](eval/defect_holdout/README.md). No human labels
exist; `accepted_cases` is always 0.

Current honest estimate over the three uncontaminated splits:
**precision ≈ 0.71–0.77, recall ≈ 0.63–0.77.** Only `crash_or_error` is
well-validated (0.95–1.00 precision); the other eight modes are aspirational.
This document explains why the taxonomy exists, how it was derived, what it does
on real data, and exactly where it is weak.

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

## The nine defect modes

| Mode | Fire when | Canonical example |
| --- | --- | --- |
| `crash_or_error` | Uncaught exception, traceback, crash, segfault | `Uncaught ImportError in main.py` |
| `data_integrity` | Data lost, dropped, truncated, corrupted, miscounted | `rows silently truncated on export` |
| `config_or_env` | Env var / config ignored or not applied; install broken | `ENV_VAR is ignored in STARTTLS mode` |
| `ui_or_ux` | Clipping, misalignment, blocked pointer input, lost focus, stale render | `preview is covered by main content` |
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

## Honest limits

- **Only `crash_or_error` is validated.** Across sets C/D/E it holds 0.95–1.00
  precision and 0.90–1.00 recall. The other eight modes are between 0.00 and 0.67
  on at least one axis, and several are 0.00.
- **`crash` is nearly free on aider.** 79% of that corpus is one auto-crash
  template, so any aider-heavy split looks good for structural reasons. dify is
  the informative corpus and the one where the taxonomy is weakest.
- **Phrase iteration has plateaued.** Rounds 2→5 added signals, removed signals
  and stripped code; precision stayed in 0.71–0.77. The next gain needs a
  different design (topic+fault co-occurrence), not more phrases.
- **A missing bucket.** Exit-code bugs, type coercion, accepted-invalid-input and
  duplicate execution are currently forced into `config_or_env` or
  `data_integrity`, and are documented as boundary cases in the label notes
  (`logic_or_validation` is the obvious missing mode).
- **Two repos is not a domain sample.** Both are AI-tool projects.
- **No human labels.** Every output is a candidate. `accepted_cases` is always 0.

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
8. ⏳ Not done: human labels on one split; `logic_or_validation` mode; wiring
   `defects` into `ci.yml`; writing it into the public README.

Treat `cte defects` as a working prototype: reliable on crash reports, weak on
everything that requires reading comprehension, and honestly measured.

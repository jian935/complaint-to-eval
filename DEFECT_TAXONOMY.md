# Defect-report taxonomy (`defect-0.1.0-draft`)

**Status: DRAFT, in-sample, unvalidated. No precision or recall is claimed.**
This document explains why this taxonomy exists, how it was derived, what it does
on real data, and exactly where it is still weak. Read it before trusting any
number it produces.

## Why a second taxonomy

The original eight modes in `taxonomy.py` target **natural-language complaints
about LLM behaviour** (`wrong_fact`, `loop_cost`, `context_loss`, …). To test
whether they generalise, the engine was run over **191 real GitHub issues**
(aider 136, dify 47, lobe 8 — all public, permissively licensed, redacted):

- **1 of 81 strong signals** ever appeared in that text.
- **1 candidate** was produced across all 191 issues.

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
| `ui_or_ux` | Layout, focus, alignment, hover, clipping | `sidebar hover preview is covered` |
| `i18n_or_locale` | Missing translations, wrong locale, English fallback | `zh-Hant: contacts.json is missing keys` |
| `security` | Traversal, unauthorized action, bypass, arbitrary exec | `path traversal outside the repository` |
| `performance` | Slow, timeout, hang, leak, latency | `the worker hangs and never returns` |
| `regression` | Worked before, stopped working, regressed since a version | `this worked before v0.86` |
| `docs` | Missing/undocumented setup step, README gap | `readme is missing the setup step` |

## Matching rules (same discipline as the LLM taxonomy, one deliberate change)

- **No bare nouns**; only specific multi-word or multi-char signals.
- **Negation scope** cancels a hit: "no uncaught exception was observed" is not a
  crash. A negator in a *previous* clause does not leak forward.
- **Redact first**; evidence offsets refer to redacted text.
- **One candidate per (record, mode)** — a crash dump with fifty `Traceback`
  lines yields one `crash_or_error` candidate, not fifty.
- **English signals match on whole-word boundaries here.** This *differs* from
  `taxonomy.py`, which forbids word boundaries because real feedback concatenates
  words. Defect reports are well-formed English, so boundaries are correct — and
  necessary: it stops `hang` from firing inside `changes` (a real false positive
  this draft hit and fixed).

## What it does on real data (in-sample, the corpus it was read from)

| Corpus | Records | Classified | Unclassified | Candidates | Top modes |
| --- | ---: | ---: | ---: | ---: | --- |
| aider (Apache-2.0) | 136 | 124 | 12 | 129 | crash 111, security 7, performance 6 |
| dify (Apache-2.0 + terms) | 47 | 25 | 22 | 28 | crash 10, ui 5, i18n 4, data_integrity 3 |

**Read this as coverage, not accuracy.** Spot checks confirmed the `crash` and
`security` hits are mostly real, and caught and fixed false positives (`hang` in
`changes`; `regression tests`; `Docs:` title). But no systematic precision has
been measured, because there is no held-out labelled set.

## Honest limits

- **In-sample.** Signals were read off these same issues. Nothing here is a
  generalisation claim.
- **`crash` is trivial on aider.** 79% of that corpus is the auto-crash template,
  so a high `crash_or_error` count mostly proves template detection, not skill.
  dify (UI / i18n / data) is the more informative corpus.
- **Sparse on the interesting modes.** `data_integrity`, `regression`, `docs`
  have single-digit counts — too few to say anything about precision.
- **Two repos is not a domain sample.** Both are AI-tool projects; other kinds of
  software will differ.
- **No human labels.** Every output is a candidate. `accepted_cases` is always 0.

## Next step (the actual work)

1. Split the 191 issues into **dev / hold-out** by record hash.
2. Model-label the hold-out (tagged `annotator: model`, never posing as human).
3. Measure **precision/recall with Wilson intervals** on the hold-out and publish
   the misses, not just the hits.
4. Only then wire `defects` into `ci.yml` and write it into the public README.

Until step 3 exists, treat `cte defects` as a working prototype on real data and
nothing more.

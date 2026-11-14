# Changelog

All notable changes to this project are documented here. This project publishes
its negative results with the same prominence as its features — several entries
below are things that **did not work**.

## 0.2.0 — 2026-11-14

First tagged release of the 0.2.0 line: tag `v0.2.0` on `main`. Before this push
the public repository sat at an **untagged v0.1 snapshot** (`01dd1e7`); there
has never been a `v0.1.0` tag or an earlier GitHub Release in this repository.

### Added

- `cte defects`: a deterministic, zero-dependency **10-mode defect taxonomy**
  for issue-tracker text (`DEFECT_TAXONOMY.md`), with code-span blanking that
  preserves offsets, start-of-word boundaries for English signals, and
  negation scope. The original 8-mode LLM-behaviour taxonomy is kept but is now
  explicitly marked as a different instrument with different signal rules.
- **Hold-out method**: nine pairwise-disjoint splits (A–I), deterministic
  `md5(salt:record_id)` draws, one rule change per split, results never
  overwritten, Wilson intervals, trivial baselines, and a
  prior-sensitivity table. Set G is a deliberately balanced 50/50 split.
- **Human data**: split G labelled blind by four independent readers
  (binary Fleiss κ = 0.922); split H labelled by one confirmed human reader
  under a rewritten v2 one-primary-mode rule (mode-level 0.545 / 0.429).
  `accepted_cases` remains **0**.
- **Contamination tooling**: `check_labeling_independence.py` (exit 2 =
  suspicious, exit 3 = previously rejected workbook), a fingerprint-only
  reject list with no answer text, and public writeups of each rejection.
- **Simulated-reader pipeline check**: verifies both κ layers and documents why
  a κ that can be dialled from 0.221 to 1.000 is not evidence.
- `cte cooccurrence`: an **experimental** single-mode topic+fault probe,
  shipped with its frozen vocabulary fingerprint and a full negative result.
  It is deliberately NOT wired into `cte defects`. Its committed result file
  stores record ids, modes and character offsets only — never issue text.
- `CONTRIBUTING.md`, this changelog, historical round snapshots for sets A–E,
  and consistent `partitions_a.json` / `labels_holdout_a.jsonl` naming.
- Package metadata now states what the tool actually is (candidate labels, not
  a runnable suite), declares `openpyxl` as an **optional** `labeling` extra
  rather than a dependency, and carries project URLs. A new test asserts that
  no public surface can reintroduce the old "minimal reproducible input" or
  "regression-test candidates" claim, and that `pyproject.toml` never drifts
  from `__version__`.

### Changed

- Package version 0.1.0 → 0.2.0. `DEFECT_VERSION` stays `0.1.0-draft` —
  the taxonomy did not change, only the surrounding evaluation apparatus.
- `test_holdout_labels.py` now covers set I as well; 119 tests pass.

### Falsified (the important part)

- **"Add more phrases"**: four rounds of signal edits left mode-level
  precision flat at 0.71–0.77.
- **"Precision 0.94 means it is accurate"**: that number comes from a 90%
  defect feed; reweighted to a 25% queue it is 0.36.
- **"It beats flagging everything"**: on a 50/50 split it wins on precision
  (0.632 vs 0.500) and loses badly on recall (0.600 vs 1.000).
- **"Rewrite the annotation rule and readers will agree"**: untested by
  decision. Two returned second workbooks were non-independent (one was a
  paraphrase, one a resubmission with two sentences edited). No
  reader-to-reader κ under v2 is published.
- **"Change the shape of the word list"**: the co-occurrence probe recovered
  **0 of 4** `data_integrity` rows on unseen split I with **11 false
  positives**. It fits design set H at 0.900 recall only because parts of its
  vocabulary were copied from H titles. The plateau is a design limit, not a
  missing word. See `eval/defect_holdout/cooccurrence_check.md`.

### Post-release patch (no version bump, no new tag)

- `cte diff` now refuses `cte defects`' `defects.json` with a readable error
  and exit code 2 instead of raising `KeyError: 'key'`. Its cases use ordinal
  ids that can shift between runs, so diffing them would produce unreliable
  `resolved_candidates`; supporting that input was deliberately declined.
- English / Chinese READMEs and `SKILL.md` now state the input contract
  explicitly. Three new tests lock the error shape, missing required fields
  and a traceback-free CLI failure; 126 tests pass.
- No engine rules, labels, result files or published numbers changed.

### Known limitations

- All A–G/I labels are **model-generated**; only G (four readers) and H (one
  reader) have human labels. No human accuracy or gold standard is claimed.
- Candidate cases are **not executable**: `input` is a quote from the report,
  not a repro script. This was a false claim in v0.1 and is fixed.
- Zero real users, zero production data, zero repair-rate figures.
- Both source corpora are software issue trackers, not a domain sample of
  "user complaints"; the 100% English evaluation set says nothing about the
  Chinese signals.
- `cte cooccurrence`'s negation window is 12 characters; a sentence-initial
  "No" does not suppress a hit. Discovered after split I was scored and left
  unfixed on purpose so I would not become a tuning set.

## 0.1.0

Initial release: 8-mode LLM-behaviour taxonomy, offline deterministic CLI,
`npx skills add jian935/complaint-to-eval` installable, MIT, CI green, demo gif.
Later measurement on real issue corpora found near-zero recall for that
taxonomy, which is what motivated 0.2.0. **No `v0.1.0` tag or Release exists.**
The demo GIF in `assets/` comes from that period and is a repository file, not
a release asset; do not mix files from the old `main` snapshot with the
`v0.2.0` tag.

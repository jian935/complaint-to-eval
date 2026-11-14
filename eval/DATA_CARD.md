# Corpus & reproduction card

**This card collects facts that were previously scattered across
`defect_holdout/README.md`, `eval/ANNOTATION_GUIDE.md` and `CHANGELOG.md`.
It adds no new measurement and changes no published number.**
Every value below is read from a committed file; where the repository does not
record something, it says so rather than guessing.

## 1. What the corpus is

| Source | Records | Licence | Where it lives |
| --- | ---: | --- | --- |
| aider GitHub issues | 478 | Apache-2.0 | `.local/corpus/`, gitignored |
| dify GitHub issues | 266 | Apache-2.0 with additional conditions | `.local/corpus/`, gitignored |

Total **744**. Both are **software issue trackers**, not general user
complaints, app reviews or support tickets. All evaluation text is **English**.
`complaint_to_eval/defects.py` does ship a Chinese signal list, but
**Chinese signals are UNVERIFIED** — no Chinese evaluation split exists.

- The corpora were **snapshotted**, not live-scraped
  (`scripts/build_corpus_from_issues.py`). The pool was expanded to 12 pages
  after earlier splits ran dry; A–G consumed 271 ids, leaving enough unused
  records to draw H and I (40 each).
- **Snapshot dates are not recorded in this repository.** Only the local
  snapshot under `.local/corpus/` holds that information; it is not shipped.
- Raw issue text is **never published**. Committed label/result files contain
  record ids, mode labels and character offsets only. Docs quote short phrases
  from public issue titles as evidence, not full text.
- Human answer workbooks and rejected workbooks likewise stay local; only label
  fingerprints and aggregate results are committed
  (`rejected_workbooks.json`, `contamination_h.md`).

Before publishing anything from a corpus, run `cte privacy --path .` (CI runs
it too) and keep raw data in `.local/`. Use `--real` only when you have checked
licence and consent; `--synthetic` marks fabricated data.

## 2. The nine disjoint splits (A–I)

Rules below are the `rule` / `salt` / `strategy` fields of
`eval/defect_holdout/partitions_*.json`, quoted as recorded. `tests/test_holdout_labels.py`
locks pairwise disjointness, known modes and `annotator: model` for model sets.

| Set | Draw rule as recorded | Notes |
| --- | --- | --- |
| A | `sort by md5(record_id); first N per corpus is hold-out` | no salt |
| B | `exclude set A; sort by md5('v2:'+id); first N per corpus` | salt `v2:` |
| C | exclude A, B; `md5('v3:'+id)` | salt `v3:`; dify arm capped at 15 and **reported**, never padded |
| D | exclude A–C; `md5('v4:'+id)` | salt `v4:` |
| E | exclude earlier sets; `md5('v5:'+id)` | salt `v5:` |
| F | exclude earlier sets; `md5('v6:'+id)` | 32 records (aider derive pool exhausted) |
| G | `hand-picked 50/50 mix: 20 non-defect + 20 defect` | deliberately balanced, **not** a random draw; see `draw_holdout_g.py` |
| H | salt `v9`, `stratified by crash template` | 40 rows; one confirmed human reader under v2; **no model labels** |
| I | salt `v10-cooc-probe`, `stratified by crash template` | drawn **after** the probe vocabulary was frozen; fingerprint `0af2ac57…`; scored once |

G and H have no hash salt because neither is a hash draw. The `v7:` / `v8:`
names do not appear in any committed partition file; this card does not infer
what they were used for.

**Contamination rule:** once a split's misses or false positives have been read,
that split is burned. Any later change must be measured on a fresh split that no
change has ever seen. `migrations.md` records every historical label edit.
Split I's 12-character negation-window limitation was found **after** scoring and
left unfixed on purpose, so I would not become a tuning set.

## 3. Who labelled what

| Split(s) | Label source | What may be claimed |
| --- | --- | --- |
| A–F, I | `annotator: model` | agreement with model labels only; **not** human accuracy or a gold standard |
| G | committed label file is `annotator: model`; **separately**, the same 40 rows were blind-labelled by four independent human readers (`multi_annotator.json`) | binary Fleiss κ = 0.922; mode-level precision against the readers 0.23–0.38 |
| H | **one** confirmed human reader under the v2 one-primary-mode rule; **no model labels** | engine-vs-one-reader 0.545 / 0.429; one reader is **not** a gold standard |
| I | model labels; `labeler_knew_experiment: true` | "agreement with model labels" only |

Two further H second-reader workbooks were **rejected** as non-independent
(one a paraphrase, one a resubmission with two sentences edited); v2 therefore
has **no reader-to-reader κ, and none will be collected**. Simulated readers
exist only to check the scoring pipeline (`publishable: false`). G-set and
H-set numbers must never be subtracted — different class priors, scoring
conventions and readers. `accepted_cases` is `0` everywhere.

## 4. Committed result files

`results_f.json`, `results_g.json` (verbatim generated output),
`human_agreement_v2.json`, `multi_annotator.json`, `cooccurrence_check.json`,
`contamination_h.json`, `rejected_workbooks.json`,
`simulation_pipeline_check.json` (`kind: simulation`, `publishable: false`),
`historical_rounds.json` (`not_recomputed: true`: sets A–E never had standalone
result JSONs; their numbers are transcribed from the round table, and C/D/E
labels were rewritten after round 6 with those sets in view, so re-running
would not reproduce them — do not average these rounds or compare them with
G/H), and the `labels_holdout_*.jsonl` / `partitions_*.json` pairs. There is no
`labels_holdout_h.jsonl`: H has no model labels. Markdown twins sit beside them.

## 5. Reproduce

Labels and splits are committed; the **local corpus snapshot is required** for
the two headline runs (it is gitignored, so a fresh clone cannot reproduce them
without re-snapshotting the source repos under the same licence):

```bash
python scripts/eval_defects_holdout.py --holdout .local/corpus/holdoutF.jsonl \
    --labels eval/defect_holdout/labels_holdout_f.jsonl --out out/eval_defects_f.json
python scripts/eval_defects_holdout.py --holdout .local/corpus/holdoutG.jsonl \
    --labels eval/defect_holdout/labels_holdout_g.jsonl --out out/eval_defects_g.json
```

Everything else runs on committed files only:

```bash
python -m unittest discover -s tests
python -m complaint_to_eval defects --input tests/fixtures/defect_input.jsonl --synthetic --out out/defects-smoke
python -m complaint_to_eval privacy --path .
python scripts/check_labeling_independence.py --workbook A.xlsx --workbook B.xlsx --out out/independence.json
```

`A.xlsx` / `B.xlsx` above are placeholders for real workbook paths; the script
exits `2` for a non-independent pair and `3` when a workbook matches a rejected
label fingerprint. Neither the workbooks nor their answers are shipped.

The demo GIF is regenerated from a real fixture run, not hand-drawn:
`python scripts/make_demo_gif.py --out assets/demo.gif`.

## 6. What this card deliberately does not provide

Original issue text, human answer workbooks, snapshot dates, a repair rate, a
fix rate, real-user or production data, or any Chinese evaluation result. If you
want to contribute a new corpus or a counter-example, use the two issue
templates under `.github/ISSUE_TEMPLATE/`.

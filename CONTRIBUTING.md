# Contributing

Thanks for looking at this repo. Its main product is **a method you can check**,
not a high score, so the contribution rules are mostly about not breaking the
method. They are short but non-negotiable.

## The five rules

1. **Never edit a split that has already been read.** A–I are pairwise
   disjoint hold-outs. Once a split's misses or false positives have informed a
   change, that split is contaminated forever. If you change a signal, draw a
   **new** split with `scripts/draw_holdout_stratified.py --exclude <every
   previous partitions file>` and measure there. Tests enforce zero overlap.
2. **Never call a model label a human label.** `labels_holdout_*.jsonl` files
   say `annotator: model` and an honesty lock fails CI if they say anything
   else. Human rounds live in separate artefacts with explicit provenance
   (`confirmed` / `unconfirmed` / `rejected`). If you receive a filled
   workbook, run `scripts/check_labeling_independence.py` **before** computing
   any agreement statistic. Exit 2 = suspicious, exit 3 = already rejected.
3. **`accepted_cases` stays 0.** Everything produced is an unreviewed
   *candidate*. A labelled split is not an accepted eval set, and `input` is a
   quote from the report, not a runnable repro script. Do not "improve" this by
   quietly claiming otherwise.
4. **No self-certifying numbers.** A κ computed between your own generated
   reader and your own labels is `kind: simulation`, `publishable: false`.
   Simulation may verify that the *pipeline* works; it may not answer a claim
   about people. The `--simulated` flag refuses to write into `eval/`.
5. **Quote numbers with their denominator, interval and baseline.** Precision
   depends on the class prior. Never quote 0.94 without saying it came from a
   90%-defect feed; never quote 0.71–0.77 without saying it is model-labelled
   and that four human readers scored it 0.23–0.38. Negative results go in
   the README honesty table, not into an appendix.

## If you want to extend the classifier

Read [`eval/defect_holdout/cooccurrence_design.md`](eval/defect_holdout/cooccurrence_design.md)
and [`cooccurrence_check.md`](eval/defect_holdout/cooccurrence_check.md) first.
Adding words, and changing the shape of the word list, have both been tried and
both failed on unseen data. A contribution that simply adds phrases will be
closed; a contribution that brings a genuinely different mechanism (and a fresh
split to prove it) is welcome.

The two taxonomies are not interchangeable:

| | `taxonomy.py` | `defects.py` |
|---|---|---|
| Input | free-form user feedback | issue tracker / bug reports |
| Modes | 8 LLM behaviours | 10 defects |
| English matching | substring, **no** word boundary | start-of-word boundary |
| Status | near-zero recall on real issue corpora | current engine |

## Local workflow

```bash
python -m unittest discover -s tests          # must pass
python -m complaint_to_eval defect-taxonomy   # invariants
python -m complaint_to_eval privacy --path .  # no personal data in eval/
python -m complaint_to_eval defects --input tests/fixtures/defect_input.jsonl \
    --synthetic --out out/smoke
```

- Pure standard library at runtime. `openpyxl` is only needed to *generate*
  labelling workbooks, never to use the CLI.
- Raw corpora live in `.local/corpus/` and are gitignored. **Never commit raw
  issue text, user IDs, phone numbers, or real submission data.** `eval/` is a
  public directory: only ids, partitions, labels, offsets and aggregate numbers.
  A committed result file may say *"record aider-5165, `message` + `double`,
  chars 269-275"*; it may **not** contain the sentence those offsets point at.
  Documentation files may quote a few words from a public issue title as
  evidence, never a paragraph.
- Keep LF line endings; several artefacts are byte-compared by tests.
- New result files need a matching test in `tests/` that locks their numbers
  and their honesty fields. A number with no provenance is worse than no number.

## Reporting a problem

Open an issue with the exact command, the split name and the artefact path.
If you found a claim that the data does not support, that is the most valuable
kind of report this project can receive.

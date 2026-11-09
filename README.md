# complaint-to-eval

**Your users already wrote your eval set. You just never turned it into one.**

Turn user complaints into **unreviewed regression-test candidates** for AI agents:
an evidence-backed failure taxonomy, a minimal reproducible input for every
finding, and a diff between two versions. Deterministic, standard library only,
no API key, no model calls.

```text
$ python -m complaint_to_eval demo
records=12 candidates=11 accepted=0
provenance=synthetic (FABRICATED; demo artefact only, never a metric)
wrote out/demo/report.json
wrote out/demo/report.md
wrote out/demo/promptfoo-candidates.json
```

**Note:** `accepted = 0`. There is no human-labelled set yet. Every case produced
by this tool is a **candidate**, not a labelled example. Nothing here may be used
to report accuracy, precision, recall, coverage, or a fix rate. See
[Honesty contract](#honesty-contract).

[中文说明](README.zh-CN.md)

## Why this exists

Teams that run agents already collect complaints: GitHub issues, support tickets,
app reviews, chat logs. Those complaints almost never become tests. Meanwhile the
downstream tooling is mature: [promptfoo](https://github.com/promptfoo/promptfoo)
and [Langfuse](https://github.com/langfuse/langfuse) will happily run an eval
suite and gate CI on it. The missing piece is upstream: **where does the suite
come from, and who decided that this complaint means this failure mode?**

This project works on that gap. It does not run evals. It produces the raw
material a human can turn into an eval set.

## Quickstart

No install needed:

```bash
git clone <this-repo> && cd complaint-to-eval
python -m complaint_to_eval demo
```

Or install the `cte` command:

```bash
pip install .
cte run --input feedback.jsonl --real --out out/report
```

`--real` is a declaration that you checked the licence and consent for that
corpus. Use `--synthetic` for fabricated data. Omitting both marks the report
`provenance: unspecified` and prints a warning.

## Input format

`.jsonl` or `.csv`. Lines starting with `//` are ignored.

```json
{"id":"r1","text":"回答里直接编造数据，说转化率是 87%。","source":"github-issues","product":"demo","version":"v1"}
```

Accepted text fields: `text`, `feedback`, `body`, `content`, `comment`.
Optional: `source`, `product`, `version`. Rows without text are skipped.

Personal data is redacted **before** classification and before anything is
quoted. Evidence offsets refer to the redacted text.

## What you get

| File | Content |
| --- | --- |
| `report.json` | findings, candidates, counts, provenance, warnings |
| `report.md` | readable report with the honesty header repeated |
| `promptfoo-candidates.json` | staged tests for a human to copy into a config |

A candidate looks like this:

```json
{
  "id": "cte-0001",
  "failure_mode": "wrong_fact",
  "input": "回答里直接编造数据，说转化率是 87%",
  "assertion": {"type": "must_not_reproduce_failure_mode", "value": "wrong_fact"},
  "status": "candidate",
  "human_review_required": true,
  "review": null
}
```

## Commands

| Command | Purpose |
| --- | --- |
| `cte demo` | run the built-in FABRICATED demo dataset |
| `cte run --input F --out D [--synthetic\|--real]` | analyse a feedback file |
| `cte diff --base A.json --head B.json` | diff two runs (candidates only) |
| `cte validate --labels F.jsonl` | check label-file structure |
| `cte taxonomy` | print the draft taxonomy and verify its invariants |
| `cte privacy --path DIR` | scan data files for residual personal data |

## Scope: what this is not

- **Not an eval framework and not an observability platform.** It *feeds*
  promptfoo / Langfuse; it does not replace them. `promptfoo-candidates.json`
  is deliberately **not** a runnable promptfoo config, because shipping
  unreviewed candidates straight into CI is the mistake this project exists
  to prevent.
- **Not an agent framework, harness, or memory layer.** Those positions are
  taken.
- **Not a release gate.** [release-contract](https://github.com/jian935/release-contract)
  decides whether a build can ship from offline evidence; this project decides
  what is worth testing in the first place. Upstream and downstream, with
  different inputs and outputs — no results or numbers are shared between them.
- **Not a requirement-to-test generator.** `responsibleai/ASSERT` starts from a
  requirements document; this starts from what users actually complained about.
- **Not a paper taxonomy.** MAST classifies multi-agent failures academically;
  this ships a working, versionable, reproducible pipeline around a draft
  taxonomy.
- **Not a continuation of the author's earlier projects.** `ai-claim-audit`
  audits numbers inside AI output, `experiment-copilot` decides whether an A/B
  result can ship, and `career-loop` matches JDs to experience. Different input,
  different output, different question. What carries over is the method:
  context-constrained signals, negation scope, human labels, and redaction first.

## Honesty contract

1. Everything generated is an unreviewed **candidate**. `accepted_cases` is
   always `0` in v0.1 because no human labels exist.
2. `complaint_to_eval/demo.jsonl` is **fabricated**. It was written to contain
   the exact phrases in the taxonomy, so a high hit count is a property of how
   the file was authored, not evidence of quality. Every report repeats this.
3. The taxonomy is a **draft** (`0.1.0-draft`). No precision, recall, coverage,
   or agreement figure is claimed, computed, or implied anywhere.
4. `cte diff` compares matched phrases on candidates. It reports
   `resolved_candidates`, explicitly **not** a fix rate.
5. When human labels disagree with the rules, fix the labels, not the engine.
   Full rules in [eval/ANNOTATION_GUIDE.md](eval/ANNOTATION_GUIDE.md).
6. Raw corpora belong in `.local/` (gitignored). Only aggregate numbers and
   redacted quotes belong in a public repo.

## Roadmap

| Stage | Deliverable |
| --- | --- |
| L1 (now) | single-purpose CLI plus an installable Agent Skill |
| L2 | 300 human-labelled cases, two annotators, agreement + confusion published, dev/hold-out split, versioned accepted set in CI |
| L3 | community badcase submissions and a weekly regression report |

Contributions to L1 are welcome in the form of **reverse tests**: a sentence
that the rules currently misclassify, plus the correct judged mode. Do not send
a new keyword without a case showing the failure and a precision check against
the labelled set; generic words are constrained by same-clause context, not
added bare.

## License

MIT. Copyright (c) 2026 jian935.

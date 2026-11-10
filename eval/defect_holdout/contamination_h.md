# A returned second workbook failed the independence check

**Status: the v2 hypothesis is STILL untested.** A second filled workbook came
back for the H split, but it is not an independent second reader. It is not used
for any reader-to-reader number in this repository.

Raw output: [`contamination_h.json`](contamination_h.json). Reproduce with
`scripts/check_labeling_independence.py` (exit code 2 = suspicious).

## What happened

Two workbooks with the same 40 rows and identical source text were compared.
One had been scored as the first H reader; the second was the newly returned one.
Both are complete (40 answers, no format errors). On the 39 rows where both gave
a definite 是 / 不是 verdict:

| Signal | Result | Why it matters |
| --- | ---: | --- |
| Binary agreement / Cohen's κ | **1.000 / 1.000** | independent readers do not do this on ambiguous reports |
| Primary-mode agreement / κ | **1.000 / 1.000** | same |
| Optional cause column, row-exact | **40 / 40** | an *optional* column, identical even where it was left blank |
| Cause labels, Jaccard | **1.000** (25/25) | no divergence at all |
| Free-text reasons, mean similarity | **0.843** | near-identical content |
| Reasons byte-identical | **0 / 40** | everything was reworded, nothing copied verbatim |

The last two rows together are the signature of **paraphrase, not independent
judgement**: the labels are the same, the explanations say the same things in
slightly different words. The one row where they differ (`r32`) is a verdict
change from 是 to 不确定, with a much longer explanation — consistent with a
second pass over the same material, not with a second person reading cold.

Examples (first reader / second workbook), same judgement, rewording only:

- `tree_sitter 的 rust 语言库找不到，属依赖未装全` / `rust 语言包找不到，依赖没装全`
- `litellm 的 tokenizer json 缺失，装包不完整` / `litellm 的 anthropic_tokenizer.json 不存在`
- `scipy 的 _spropack 动态库加载失败，环境里的二进制有问题` / `_spropack 动态库 dlopen 失败`

## The number that must never be published

Had these two been accepted as two independent readers, the result would have
been:

> "Under the v2 rule, two readers agree perfectly: binary Fleiss κ = 1.000,
> primary-mode κ = 1.000. The rewritten rule fixed the disagreement."

**That sentence would be false**, and it is the most attractive false result this
project could produce — it would have "fixed" the exact problem v2 was written
for. It is recorded here as a warning, not as a finding. The tool
`check_labeling_independence.py` exists so this cannot happen silently again.
It can only *falsify* independence; it cannot certify that anyone is human,
blind, or unaided. Only provenance can.

## A second, more serious problem

The first workbook's provenance was **never confirmed** either. Its result file
[`human_agreement_v2.json`](human_agreement_v2.json) now carries
`annotator_status: "unconfirmed"` and a warning. If that first workbook was
produced by a model or with model assistance, then:

- 0.545 / 0.429 is **not** a human-vs-machine comparison;
- every "human reader" phrase in [`human_agreement_v2.md`](human_agreement_v2.md)
  and in the READMEs is wrong;
- the "engine is an outlier, not an annotator" conclusion from split G still
  stands (four independent human readers there), but the H round adds no
  independent evidence for or against v2.

Nothing has been silently relabelled. The numbers are left in place with their
status downgraded, because deleting a published result after the fact is worse
than marking it conditional. Provenance is being confirmed with the requester.

## Disposition

- Both workbooks are stored outside the repo under `.local/human_labeling/` as
  `H_r1.xlsx` and `H_r2_unverified.xlsx` (gitignored, third-party issue text).
- **No reader-reader κ is computed from them.** `eval_human_agreement_v2.py`
  supports multiple workbooks, but running it on these two would produce the
  false result above, so the pair is excluded.
- The v2 rule's effect on agreement between people remains **unmeasured**.
- Set H still has no model label file; the "model labels only for A–G" honesty
  lock is unchanged.

## What a valid next round needs

1. A person who has not seen either filled workbook, working without a model
   filling the sheet for them.
2. The blank workbook regenerated from `make_labeling_workbook.py --spec v2`;
   its 怎么填 sheet now states the independence requirement explicitly.
3. On return: run `check_labeling_independence.py` **before** any agreement
   statistic. A `NO_RED_FLAG` result is necessary, not sufficient.
4. Only then run `eval_human_agreement_v2.py` with both workbooks.

This is the second time in this project that a result had to be discarded for
contamination (the first was set B's optimistic 0.917 / 0.846). Recording it is
part of the method, not an embarrassment to hide.

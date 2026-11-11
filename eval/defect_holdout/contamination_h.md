# A returned second workbook failed the independence check

**Status: the v2 hypothesis is STILL untested.** A second filled workbook came
back for the H split, but it was not an independent second reader. The same
labels were later resubmitted with two reason sentences edited (see
[Resubmission](#resubmission-of-the-same-workbook-2026-11-11)). Neither is used
for any reader-to-reader number in this repository.

Raw output: [`contamination_h.json`](contamination_h.json). Reproduce with
`scripts/check_labeling_independence.py` (exit 2 = suspicious, exit 3 =
duplicate of a rejected workbook).

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

## The first workbook is human — that does not rescue the round

On 2026-11-10 the requester confirmed that the **first** H workbook was filled
by a person. Its result file
[`human_agreement_v2.json`](human_agreement_v2.json) now carries
`annotator_status: "confirmed"`, so 0.545 / 0.429 *is* a genuine
engine-versus-person comparison, and the "human reader" wording in
[`human_agreement_v2.md`](human_agreement_v2.md) is correct.

Three limits remain, unchanged by that confirmation:

- It is **one reader**. One person's labels are not a gold standard, and the
  figure must not be called "human accuracy" or quoted without its baselines.
- The rejected second workbook adds **no** second opinion. Its provenance is
  still unknown, but that is irrelevant: it failed on independence, not on who
  or what filled it.
- The "engine is an outlier, not an annotator" result comes from split G's
  **four** independent human readers (Fleiss κ = 0.922 binary). H does not
  replicate it and does not contradict it.

Nothing was silently relabelled in either direction. When provenance was
unknown the result was marked conditional; now that it is confirmed the status
was upgraded and the numbers were left exactly as they were — the same
`0.545 / 0.429`, recomputed from the same rows.

## Resubmission of the same workbook (2026-11-11)

A third workbook was returned, named as a fresh independent human round. It is
**the same data as the rejected second workbook**, with two reason sentences
edited:

- 38 of 40 rows are byte-identical across all seven columns;
- the two differences are prose only (`r16`: "one attachment link" → "two";
  `r32`: a slightly shorter explanation of the same 不确定 verdict);
- **D / E / F — the columns any statistic actually uses — are identical on all
  40 rows**, so its label fingerprint
  `e81efa74…fded09` is byte-for-byte the rejected workbook's;
- against the confirmed first reader it still produces κ = 1.000 on both layers.

Rewording reasons cannot create a new reader. It also cannot change a single
published number: the scorer reads the verdict and the two category columns.

To make this a one-line check instead of an argument, the reject list
[`rejected_workbooks.json`](rejected_workbooks.json) now stores label
fingerprints of rejected workbooks — **no answer text, no reasons, no personal
data**. `check_labeling_independence.py` hashes D/E/F of every submitted
workbook and exits `3` on a hit. The 2026-11-11 submission was caught this way.

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
   statistic. A `NO_RED_FLAG` result is necessary, not sufficient; a
   `REJECTED_DUPLICATE` (exit 3) means the same labels were handed back again,
   however the prose was edited.
4. Only then run `eval_human_agreement_v2.py` with both workbooks.

This is the second time in this project that a result had to be discarded for
contamination (the first was set B's optimistic 0.917 / 0.846). Recording it is
part of the method, not an embarrassment to hide.

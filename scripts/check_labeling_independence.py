"""Check whether two returned labelling workbooks are plausibly independent.

This tool CANNOT prove that anyone is human. It can only *falsify* independence:
two independent readers on 40 ambiguous reports do not produce identical optional
cause columns and near-identical free-text reasons. Catching that before a number
is published is the whole point.

Typical failure this catches:

* one workbook is a paraphrase of the other (reasons ~0.85 similar, zero rows
  byte-identical, but every label identical);
* an LLM was asked to "fill this in" and reproduced the same priors;
* a second reader was shown the first workbook.

Usage:
    python scripts/check_labeling_independence.py \
        --workbook a.xlsx --workbook b.xlsx --out out/independence.json

Exit code 0 = no obvious non-independence found (NOT a certificate of blindness).
Exit code 2 = suspicious; do not treat these as two independent readers.
"""

from __future__ import annotations

import argparse
import difflib
import json
import sys
from pathlib import Path

from openpyxl import load_workbook

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from complaint_to_eval.defects import DEFECT_MODES  # noqa: E402


def read_workbook(path: Path) -> dict[str, dict]:
    ws = load_workbook(path, data_only=True)["待标注"]
    out = {}
    for r in range(2, ws.max_row + 1):
        rid = ws.cell(row=r, column=1).value
        if not rid or not str(rid).startswith("r"):
            continue
        out[str(rid)] = {
            "text": ws.cell(row=r, column=3).value or "",
            "verdict": (ws.cell(row=r, column=4).value or "").strip(),
            "primary": (ws.cell(row=r, column=5).value or "").strip(),
            "secondary": (ws.cell(row=r, column=6).value or "").strip(),
            "reason": (ws.cell(row=r, column=7).value or "").strip(),
        }
    return out


def cohen_kappa(pairs: list[tuple[str, str]]) -> tuple[float, float]:
    n = len(pairs)
    if not n:
        return 0.0, 0.0
    po = sum(1 for a, b in pairs if a == b) / n
    cats = sorted({v for p in pairs for v in p})
    pe = sum((sum(1 for a, _ in pairs if a == c) / n) *
             (sum(1 for _, b in pairs if b == c) / n) for c in cats)
    return po, ((po - pe) / (1 - pe) if pe < 1 else 0.0)


def compare(left: dict, right: dict, left_name: str, right_name: str) -> dict:
    common = sorted(set(left) & set(right))
    text_diff = [r for r in common if left[r]["text"].strip() != right[r]["text"].strip()]
    scored = [r for r in common
              if left[r]["verdict"] in {"是", "不是"}
              and right[r]["verdict"] in {"是", "不是"}]

    bin_pairs = [(left[r]["verdict"], right[r]["verdict"]) for r in scored]
    mode_pairs = [(left[r]["primary"] or "none", right[r]["primary"] or "none")
                  for r in scored]
    bin_po, bin_k = cohen_kappa(bin_pairs)
    mode_po, mode_k = cohen_kappa(mode_pairs)

    sec_exact = sum(1 for r in common
                    if left[r]["secondary"] == right[r]["secondary"])
    inter = union = 0
    for r in common:
        a = {x.strip() for x in left[r]["secondary"].replace("，", ",").split(",") if x.strip()}
        b = {x.strip() for x in right[r]["secondary"].replace("，", ",").split(",") if x.strip()}
        inter += len(a & b)
        union += len(a | b)

    sims = [difflib.SequenceMatcher(None, left[r]["reason"], right[r]["reason"]).ratio()
            for r in common]
    reason_exact = sum(1 for r in common if left[r]["reason"] == right[r]["reason"])

    flags = []
    if text_diff:
        flags.append(f"source text differs on {len(text_diff)} rows; not the same split")
    sec_rate = sec_exact / len(common) if common else 0.0
    sim_mean = sum(sims) / len(sims) if sims else 0.0
    if sec_rate >= 0.95:
        flags.append("optional cause column is identical on >=95% of rows")
    if sim_mean >= 0.75:
        flags.append(f"free-text reasons are {sim_mean:.2f} similar on average")
    if reason_exact == 0 and sim_mean >= 0.75:
        flags.append("reasons are consistently reworded, never byte-identical "
                     "(paraphrase signature, not independent writing)")
    if bin_po == 1.0 and mode_po == 1.0 and len(scored) >= 20:
        flags.append("perfect agreement on >=20 scored rows is implausible for "
                     "independent readers on ambiguous reports")
    if not flags:
        flags.append("no independence red flag found — this is NOT proof of blindness")

    verdict = "SUSPECT" if any(
        f.startswith(("optional cause", "free-text", "reasons are", "perfect", "source text"))
        for f in flags) else "NO_RED_FLAG"

    return {
        "left": left_name, "right": right_name,
        "common_rows": len(common), "scored_rows": len(scored),
        "source_text_differences": len(text_diff),
        "binary": {"agreement": bin_po, "kappa": bin_k},
        "primary_mode": {"agreement": mode_po, "kappa": mode_k},
        "secondary": {"row_exact_rate": sec_rate, "row_exact": sec_exact,
                      "jaccard": inter / union if union else None,
                      "intersection": inter, "union": union},
        "reasons": {"mean_similarity": sim_mean,
                    "median_similarity": sorted(sims)[len(sims) // 2] if sims else 0.0,
                    "min_similarity": min(sims) if sims else 0.0,
                    "byte_identical_rows": reason_exact},
        "verdict": verdict,
        "flags": flags,
        "scope": "A 'NO_RED_FLAG' result does not certify that either reader is "
                 "human, blind, or independent. Only the reader's provenance can.",
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workbook", action="append", required=True,
                    help="repeat for each returned workbook (at least two)")
    ap.add_argument("--out", default=str(ROOT / "out/labeling_independence.json"))
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()
    if len(args.workbook) < 2:
        raise SystemExit("need at least two workbooks to check independence")

    workbooks = {}
    for raw in args.workbook:
        path = Path(raw)
        workbooks[path.stem] = read_workbook(path)

    names = list(workbooks)
    pairs = [compare(workbooks[a], workbooks[b], a, b)
             for i, a in enumerate(names) for b in names[i + 1:]]
    payload = {
        "workbooks": {n: {"rows": len(w),
                          "answered_rows": sum(1 for r in w.values() if r["verdict"])}
                      for n, w in workbooks.items()},
        "pairs": pairs,
        "overall": "SUSPECT" if any(p["verdict"] == "SUSPECT" for p in pairs)
                   else "NO_RED_FLAG",
        "note": "This checks independence, not humanness. A model and a human "
                "can agree for bad reasons; two models can agree perfectly.",
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    if not args.quiet:
        for p in pairs:
            print(f"{p['left']} vs {p['right']}: {p['verdict']}  "
                  f"({p['common_rows']} rows, {p['scored_rows']} scored)")
            print(f"  binary  agreement {p['binary']['agreement']:.3f}  "
                  f"kappa {p['binary']['kappa']:.3f}")
            print(f"  primary agreement {p['primary_mode']['agreement']:.3f}  "
                  f"kappa {p['primary_mode']['kappa']:.3f}")
            print(f"  secondary exact {p['secondary']['row_exact_rate']:.3f}  "
                  f"jaccard {p['secondary']['jaccard']}")
            print(f"  reasons mean similarity {p['reasons']['mean_similarity']:.3f}  "
                  f"byte-identical {p['reasons']['byte_identical_rows']}")
            for f in p["flags"]:
                print(f"    - {f}")
        print(f"\nwrote {out}")
    return 2 if payload["overall"] == "SUSPECT" else 0


if __name__ == "__main__":
    raise SystemExit(main())

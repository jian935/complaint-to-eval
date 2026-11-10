"""Compare a returned human-labelling workbook against the existing labels.

Run:  python scripts/eval_human_agreement.py \
          --workbook ".local/human_labeling/filled.xlsx" \
          --labels eval/defect_holdout/labels_holdout_g.jsonl \
          --holdout .local/corpus/holdoutG.jsonl \
          --out out/human_agreement.json

Reports three things, in this order:

1. Record level — does the record report a defect at all. Human vs the existing
   reader (Cohen's kappa), and human vs the engine (precision/recall).
2. Mode level — per-mode precision/recall, taking the human as reference.
3. Every disagreement, with both reasons, so it can be argued about instead of
   silently averaged.

"unclear" verdicts are excluded from kappa and counted separately. They are not
silently coerced to either side.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

from openpyxl import load_workbook

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from complaint_to_eval.defects import DEFECT_MODES, analyze_defects  # noqa: E402
from complaint_to_eval.pipeline import load_records  # noqa: E402


def read_workbook(path: Path) -> dict[str, dict]:
    wb = load_workbook(path, data_only=True)
    if "待标注" not in wb.sheetnames:
        raise SystemExit(f"sheet '待标注' not found in {path}: {wb.sheetnames}")
    ws = wb["待标注"]
    out: dict[str, dict] = {}
    for r in range(2, ws.max_row + 1):
        rid = ws.cell(row=r, column=1).value
        if not rid or not str(rid).startswith("r"):
            continue
        verdict = (ws.cell(row=r, column=4).value or "").strip()
        modes_raw = (ws.cell(row=r, column=5).value or "").strip()
        reason = (ws.cell(row=r, column=6).value or "").strip()
        modes = [m.strip() for m in modes_raw.replace("，", ",").split(",") if m.strip()]
        out[str(rid)] = {"verdict": verdict, "modes": modes, "reason": reason}
    return out


def cohen_kappa(pairs: list[tuple[str, str]]) -> tuple[float, float]:
    n = len(pairs)
    if not n:
        return 0.0, 0.0
    labels = sorted({x for p in pairs for x in p})
    po = sum(1 for a, b in pairs if a == b) / n
    pe = 0.0
    for label in labels:
        pa = sum(1 for a, _ in pairs if a == label) / n
        pb = sum(1 for _, b in pairs if b == label) / n
        pe += pa * pb
    kappa = (po - pe) / (1 - pe) if pe < 1 else 0.0
    return po, kappa


def wilson(k: int, n: int) -> tuple[float, float]:
    if n == 0:
        return 0.0, 0.0
    z = 1.96
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    m = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5)
    return (c - m) / d, (c + m) / d


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workbook", required=True)
    ap.add_argument("--labels", required=True, help="existing labels for the same split")
    ap.add_argument("--holdout", required=True, help="the split, for record order")
    ap.add_argument("--out", default="out/human_agreement.json")
    args = ap.parse_args()

    human = read_workbook(Path(args.workbook))
    records = load_records(Path(args.holdout))
    reader: dict[str, set[str]] = {}
    for line in Path(args.labels).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            row = json.loads(line)
            reader[row["record_id"]] = set(row["modes"])

    report = analyze_defects(records, dataset_label="agreement", synthetic=False)
    engine: dict[str, set[str]] = defaultdict(set)
    for finding in report["findings"]:
        engine[finding["record_id"]].add(finding["defect_mode"])

    rows = []
    for idx, rec in enumerate(records, start=1):
        rid = f"r{idx:02d}"
        h = human.get(rid)
        if h is None:
            raise SystemExit(f"missing answer for {rid} (record {rec.id})")
        mine = reader.get(rec.id, set())
        eng = engine.get(rec.id, set())
        h_verdict = h["verdict"] or "空"
        rows.append({
            "row": rid,
            "record_id": rec.id,
            "human_verdict": h_verdict,
            "human_modes": sorted(h["modes"]),
            "reader_modes": sorted(mine),
            "engine_modes": sorted(eng),
            "human_reason": h["reason"],
        })

    unclear = [r for r in rows if r["human_verdict"] == "不确定"]
    bad_verdict = [r for r in rows if r["human_verdict"] not in {"是", "不是", "不确定"}]
    scored = [r for r in rows if r["human_verdict"] in {"是", "不是"}]

    pairs_hr = [(r["human_verdict"] == "是", bool(r["reader_modes"])) for r in scored]
    po_hr, kappa_hr = cohen_kappa([("y" if a else "n", "y" if b else "n") for a, b in pairs_hr])
    pairs_he = [(r["human_verdict"] == "是", bool(r["engine_modes"])) for r in scored]
    po_he, kappa_he = cohen_kappa([("y" if a else "n", "y" if b else "n") for a, b in pairs_he])

    tp = sum(1 for a, b in pairs_he if a and b)
    he_p = tp / sum(1 for _, b in pairs_he if b) if any(b for _, b in pairs_he) else 0.0
    he_r = tp / sum(1 for a, _ in pairs_he if a) if any(a for a, _ in pairs_he) else 0.0

    mode_tp: Counter[str] = Counter()
    mode_fp: Counter[str] = Counter()
    mode_fn: Counter[str] = Counter()
    for r in scored:
        gold = set(r["human_modes"]) if r["human_verdict"] == "是" else set()
        pred = set(r["engine_modes"])
        for m in pred & gold:
            mode_tp[m] += 1
        for m in pred - gold:
            mode_fp[m] += 1
        for m in gold - pred:
            mode_fn[m] += 1

    print(f"rows labelled: {len(rows)}  |  scored (是/不是): {len(scored)}  |  不确定: {len(unclear)}")
    if bad_verdict:
        print(f"WARNING unreadable verdicts: {[r['row'] for r in bad_verdict]}")
    if unclear:
        print(f"  不确定 rows: {[r['row'] for r in unclear]}")
    print()
    print("== record level: is this a defect report at all ==")
    print(f"human vs existing reader : agreement {po_hr:.3f}  kappa {kappa_hr:.3f}  (n={len(pairs_hr)})")
    print(f"human vs engine          : agreement {po_he:.3f}  kappa {kappa_he:.3f}")
    lo, hi = wilson(tp, sum(1 for _, b in pairs_he if b))
    print(f"engine vs human          : precision {he_p:.3f} [{lo:.3f},{hi:.3f}]  recall {he_r:.3f}"
          f"  (TP {tp})")
    print()
    print("== mode level (human = reference) ==")
    print(f"{'mode':22}{'TP':>4}{'FP':>4}{'FN':>4}{'P':>8}{'R':>8}")
    for mode in DEFECT_MODES:
        t, f, n = mode_tp[mode], mode_fp[mode], mode_fn[mode]
        p = t / (t + f) if (t + f) else float("nan")
        rr = t / (t + n) if (t + n) else float("nan")
        if t or f or n:
            print(f"{mode:22}{t:>4}{f:>4}{n:>4}{p:>8.2f}{rr:>8.2f}")
    tot_tp, tot_fp, tot_fn = sum(mode_tp.values()), sum(mode_fp.values()), sum(mode_fn.values())
    mp = tot_tp / (tot_tp + tot_fp) if (tot_tp + tot_fp) else 0.0
    mr = tot_tp / (tot_tp + tot_fn) if (tot_tp + tot_fn) else 0.0
    print(f"{'micro':22}{tot_tp:>4}{tot_fp:>4}{tot_fn:>4}{mp:>8.2f}{mr:>8.2f}")

    disagreements = [r for r in rows if (r["human_verdict"] == "是") != bool(r["reader_modes"])
                     or (r["human_verdict"] == "是" and set(r["human_modes"]) != set(r["reader_modes"]))]
    print()
    print(f"== disagreements between human and existing reader: {len(disagreements)} ==")
    for r in disagreements:
        print(f"{r['row']} {r['record_id']}: human={r['human_verdict']} {r['human_modes'] or '-'}"
              f" | reader={r['reader_modes'] or '-'} | engine={r['engine_modes'] or '-'}")
        print(f"    human said: {r['human_reason'][:140]}")

    payload = {
        "labelled_rows": len(rows),
        "scored_rows": len(scored),
        "unclear_rows": [r["row"] for r in unclear],
        "record_level": {
            "human_vs_reader_agreement": po_hr,
            "human_vs_reader_kappa": kappa_hr,
            "human_vs_engine_agreement": po_he,
            "human_vs_engine_kappa": kappa_he,
            "engine_precision": he_p,
            "engine_recall": he_r,
            "engine_precision_ci": list(wilson(tp, sum(1 for _, b in pairs_he if b))),
            "tp": tp,
        },
        "mode_level": {
            m: {"tp": mode_tp[m], "fp": mode_fp[m], "fn": mode_fn[m]} for m in DEFECT_MODES
        },
        "micro": {"tp": tot_tp, "fp": tot_fp, "fn": tot_fn,
                  "precision": mp, "recall": mr},
        "rows": rows,
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nwrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

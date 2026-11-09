"""Score the defect classifier against MODEL labels on the hold-out split.

Labels are model-generated (annotator: model), never human. The signals were
authored with visibility into both corpora, so this is an *optimistic, in-house*
estimate, not a clean generalisation result. It still measures something real:
where the deterministic rules agree and disagree with a careful reader.

Usage:
    python scripts/eval_defects_holdout.py
"""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

import sys

sys.path.insert(0, str(ROOT))

from complaint_to_eval.defects import DEFECT_MODES, analyze_defects  # noqa: E402
from complaint_to_eval.pipeline import load_records  # noqa: E402

HOLDOUT = ROOT / ".local/corpus/holdout.jsonl"
LABELS = ROOT / "eval/defect_holdout/labels_holdout.jsonl"


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = (z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--holdout", default=str(HOLDOUT))
    ap.add_argument("--labels", default=str(LABELS))
    ap.add_argument("--out", default=str(ROOT / "out/eval_defects.json"))
    args = ap.parse_args()

    records = load_records(Path(args.holdout))
    report = analyze_defects(records, dataset_label="holdout", synthetic=False)

    labels: dict[str, set[str]] = {}
    for line in Path(args.labels).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        row = json.loads(line)
        labels[row["record_id"]] = set(row["modes"])

    engine: dict[str, set[str]] = defaultdict(set)
    for f in report["findings"]:
        engine[f["record_id"]].add(f["defect_mode"])

    holdout_ids = [r.id for r in records]
    # Only score records that have a label (all should).
    scored = [rid for rid in holdout_ids if rid in labels]

    pred_n: Counter[str] = Counter()
    label_n: Counter[str] = Counter()
    tp_n: Counter[str] = Counter()
    misses: list[tuple[str, str]] = []
    false_pos: list[tuple[str, str]] = []

    for rid in scored:
        lab = labels[rid]
        eng = engine.get(rid, set())
        for mode in eng:
            pred_n[mode] += 1
            if mode in lab:
                tp_n[mode] += 1
            else:
                false_pos.append((rid, mode))
        for mode in lab:
            label_n[mode] += 1
            if mode not in eng:
                misses.append((rid, mode))

    total_pred = sum(pred_n.values())
    total_label = sum(label_n.values())
    total_tp = sum(tp_n.values())

    micro_p = total_tp / total_pred if total_pred else 0.0
    micro_r = total_tp / total_label if total_label else 0.0
    mp_lo, mp_hi = wilson(total_tp, total_pred)
    mr_lo, mr_hi = wilson(total_tp, total_label)

    print(f"hold-out records scored: {len(scored)}  (labels are MODEL, not human)")
    print(f"engine candidates: {total_pred}  |  label-positive instances: {total_label}  |  TP: {total_tp}")
    print(f"MICRO precision = {micro_p:.3f}  [95% Wilson {mp_lo:.3f}, {mp_hi:.3f}]")
    print(f"MICRO recall    = {micro_r:.3f}  [95% Wilson {mr_lo:.3f}, {mr_hi:.3f}]")
    print()
    print(f"{'mode':16} {'prec':>6} {'rec':>6} {'TP':>4} {'pred':>5} {'label':>6}   Wilson(P)")
    for mode in DEFECT_MODES:
        p_ = pred_n[mode]
        l_ = label_n[mode]
        if p_ == 0 and l_ == 0:
            continue
        prec = tp_n[mode] / p_ if p_ else float("nan")
        rec = tp_n[mode] / l_ if l_ else float("nan")
        if p_:
            lo, hi = wilson(tp_n[mode], p_)
            wci = f"[{lo:.2f},{hi:.2f}]"
        else:
            wci = "-"
        prec_s = f"{prec:.2f}" if p_ else "  - "
        rec_s = f"{rec:.2f}" if l_ else "  - "
        print(f"{mode:16} {prec_s:>6} {rec_s:>6} {tp_n[mode]:>4} {p_:>5} {l_:>6}   {wci}")

    print()
    print(f"MISSES (label has it, engine missed): {len(misses)}")
    for rid, mode in misses[:25]:
        print(f"  - {rid} :: {mode}")
    print(f"FALSE POSITIVES (engine fired, label absent): {len(false_pos)}")
    for rid, mode in false_pos[:25]:
        print(f"  - {rid} :: {mode}")

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(
            {
                "scored": len(scored),
                "annotator": "model",
                "micro": {"precision": micro_p, "recall": micro_r,
                          "precision_ci": [mp_lo, mp_hi], "recall_ci": [mr_lo, mr_hi],
                          "candidates": total_pred, "label_positive": total_label, "tp": total_tp},
                "per_mode": {m: {"precision": (tp_n[m] / pred_n[m] if pred_n[m] else None),
                                 "recall": (tp_n[m] / label_n[m] if label_n[m] else None),
                                 "tp": tp_n[m], "pred": pred_n[m], "label": label_n[m]}
                             for m in DEFECT_MODES},
                "misses": misses,
                "false_positives": false_pos,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"\nwrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

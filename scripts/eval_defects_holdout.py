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
LABELS = ROOT / "eval/defect_holdout/labels_holdout_a.jsonl"


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

    # --- Record-level detection -------------------------------------------------
    # Mode-level scores punish a right-issue-wrong-bucket call twice (once as a
    # false positive, once as a miss). For a triage tool the first question is
    # "did it flag an issue that really has a defect?", so this level is reported
    # alongside and is the fairer headline for that use.
    flagged = {rid for rid in scored if engine.get(rid)}
    has_defect = {rid for rid in scored if labels[rid]}
    clean = set(scored) - has_defect
    hit = flagged & has_defect
    det_p = len(hit) / len(flagged) if flagged else 0.0
    det_r = len(hit) / len(has_defect) if has_defect else 0.0
    dp_lo, dp_hi = wilson(len(hit), len(flagged))
    dr_lo, dr_hi = wilson(len(hit), len(has_defect))
    clean_flags = sorted(flagged & clean)

    # --- Baselines --------------------------------------------------------------
    # These corpora are defect-heavy, so a trivial rule can score well. Without
    # these two lines every number below is uninterpretable.
    #   always-flag: call every record defective (record level)
    #   majority-mode: predict the most common labelled mode on every record
    base_det_p = len(has_defect) / len(scored) if scored else 0.0
    base_det_r = 1.0 if has_defect else 0.0
    majority = label_n.most_common(1)[0][0] if label_n else None
    base_mode_tp = label_n[majority] if majority else 0
    base_mode_p = base_mode_tp / len(scored) if scored else 0.0
    base_mode_r = base_mode_tp / total_label if total_label else 0.0

    print(f"hold-out records scored: {len(scored)}  (labels are MODEL, not human)")
    print(f"engine candidates: {total_pred}  |  label-positive instances: {total_label}  |  TP: {total_tp}")
    print(f"MODE-LEVEL micro precision = {micro_p:.3f}  [95% Wilson {mp_lo:.3f}, {mp_hi:.3f}]")
    print(f"MODE-LEVEL micro recall    = {micro_r:.3f}  [95% Wilson {mr_lo:.3f}, {mr_hi:.3f}]")
    print()
    print(
        f"RECORD-LEVEL detection precision = {det_p:.3f}  [95% Wilson {dp_lo:.3f}, {dp_hi:.3f}]"
        f"   ({len(hit)}/{len(flagged)} flagged records really have a defect)"
    )
    print(
        f"RECORD-LEVEL detection recall    = {det_r:.3f}  [95% Wilson {dr_lo:.3f}, {dr_hi:.3f}]"
        f"   ({len(hit)}/{len(has_defect)} defect records flagged)"
    )
    print(f"clean records wrongly flagged: {len(clean_flags)} of {len(clean)}"
          + (f"  {clean_flags}" if clean_flags else ""))
    print()
    # --- Prior sensitivity ------------------------------------------------------
    # Precision depends on how many negatives the queue actually contains. Both
    # source repos are defect trackers, so their natural prior (~88% defects) is
    # far more positive than a real triage queue. Reweight the two measured rates
    # (recall on positives, flag-rate on negatives) to other priors. Both rates
    # come from THIS set, so a set with few negatives gives a noisy curve.
    rec_pos = len(hit) / len(has_defect) if has_defect else 0.0
    fp_rate = len(clean_flags) / len(clean) if clean else float("nan")
    print("PRIOR SENSITIVITY (record level; precision if that share of the queue is defective):")
    if clean:
        print(f"  measured on this set: recall on defects {rec_pos:.3f}, "
              f"flag-rate on clean {fp_rate:.3f} (n_clean={len(clean)})")
        for prior in (0.90, 0.75, 0.50, 0.25, 0.10):
            p = rec_pos * prior
            q = fp_rate * (1 - prior)
            prec = p / (p + q) if (p + q) else 0.0
            print(f"    prior {prior:.2f} -> precision {prec:.3f}")
    else:
        print("  n/a: this set has no clean records, so precision cannot be reweighted")
    print()
    print("BASELINES (a trivial rule must not beat the engine):")
    print(f"  always-flag every record        -> record P {base_det_p:.3f} / R {base_det_r:.3f}")
    print(f"  always-predict '{majority}'  -> mode   P {base_mode_p:.3f} / R {base_mode_r:.3f}")
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
                "record_level": {
                    "detection_precision": det_p,
                    "detection_recall": det_r,
                    "precision_ci": [dp_lo, dp_hi],
                    "recall_ci": [dr_lo, dr_hi],
                    "flagged": len(flagged),
                    "defect_records": len(has_defect),
                    "clean_records": len(clean),
                    "clean_wrongly_flagged": clean_flags,
                },
                "baselines": {
                    "always_flag_record_precision": base_det_p,
                    "always_flag_record_recall": base_det_r,
                    "majority_mode": majority,
                    "majority_mode_precision": base_mode_p,
                    "majority_mode_recall": base_mode_r,
                },
                "prior_sensitivity": {
                    "recall_on_defects": rec_pos,
                    "flag_rate_on_clean": None if clean == 0 else fp_rate,
                    "n_clean": len(clean),
                    "precision_by_prior": {} if not clean else {
                        f"{prior:.2f}": (
                            (rec_pos * prior) / (rec_pos * prior + fp_rate * (1 - prior))
                            if (rec_pos * prior + fp_rate * (1 - prior)) else 0.0
                        )
                        for prior in (0.90, 0.75, 0.50, 0.25, 0.10)
                    },
                },
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

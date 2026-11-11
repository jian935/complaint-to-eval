"""Score the topic+fault probe against split I, alongside the v0.1 phrase list.

Run:
    python scripts/eval_cooccurrence.py \
        --out eval/defect_holdout/cooccurrence_check.json

Split I was drawn AFTER the probe vocabulary was frozen; the fingerprint is
stored in partitions_i.json and checked here. If the vocabulary is edited
afterwards this script exits 2 and the split is invalid.

Everything here is scored against MODEL labels. This is not human accuracy,
not a gold standard, and the label writer knew what the experiment was for.
See cooccurrence_design.md for why split H is only a design set.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from complaint_to_eval.cooccurrence import (  # noqa: E402
    COOCCURRENCE_VERSION, PROBE_MODE, find_cooccurrence_hits,
    vocabulary_fingerprint,
)
from complaint_to_eval.defects import find_defect_hits  # noqa: E402
from complaint_to_eval.pipeline import load_records  # noqa: E402
from complaint_to_eval.redact import redact  # noqa: E402

PART = ROOT / "eval/defect_holdout"


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = (z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


def metrics(pred: set[str], gold: set[str], universe: set[str]) -> dict:
    tp = pred & gold
    fp = pred - gold
    fn = gold - pred
    p = len(tp) / len(pred) if pred else 0.0
    r = len(tp) / len(gold) if gold else 0.0
    return {
        "true_positive": len(tp), "false_positive": len(fp),
        "false_negative": len(fn),
        "true_negative": len(universe - pred - gold),
        "predicted": len(pred), "gold": len(gold),
        "precision": p, "precision_ci95": list(wilson(len(tp), len(pred))),
        "recall": r, "recall_ci95": list(wilson(len(tp), len(gold))),
        "tp_ids": sorted(tp), "fp_ids": sorted(fp), "fn_ids": sorted(fn),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--partitions", default=str(PART / "partitions_i.json"))
    ap.add_argument("--holdout", default=str(ROOT / ".local/corpus/holdoutI.jsonl"))
    ap.add_argument("--labels", default=str(PART / "labels_holdout_i.jsonl"))
    ap.add_argument("--out", default=str(ROOT / "out/cooccurrence_check.json"))
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    part = json.loads(Path(args.partitions).read_text(encoding="utf-8"))
    fp_now = vocabulary_fingerprint()
    if part.get("vocabulary_fingerprint") != fp_now:
        print(f"FATAL: vocabulary changed since split I was drawn. "
              f"recorded={part.get('vocabulary_fingerprint')} now={fp_now}. "
              f"Draw a new split; this one is contaminated.", file=sys.stderr)
        return 2

    # I must be disjoint from every earlier split.
    used: set[str] = set()
    for p in sorted(PART.glob("partitions*.json")):
        if p.name == "partitions_i.json":
            continue
        for ids in json.loads(p.read_text(encoding="utf-8"))["holdout"].values():
            used |= set(ids)
    i_ids = [rid for bucket in part["holdout"].values() for rid in bucket]
    if used & set(i_ids):
        print(f"FATAL: I overlaps earlier splits: {sorted(used & set(i_ids))}",
              file=sys.stderr)
        return 2

    labels: dict[str, list[str]] = {}
    for line in Path(args.labels).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if row.get("annotator") != "model":
            print(f"FATAL: unexpected annotator {row.get('annotator')}", file=sys.stderr)
            return 2
        labels[row["record_id"]] = list(row["modes"])
    records = {r.id: r for r in load_records(Path(args.holdout))}
    if set(records) != set(i_ids) or set(labels) != set(i_ids):
        print("FATAL: corpus / labels / partitions disagree", file=sys.stderr)
        return 2

    universe = set(i_ids)
    gold = {rid for rid, modes in labels.items() if PROBE_MODE in modes}

    old_pred: set[str] = set()
    new_pred: set[str] = set()
    evidence: list[dict] = []
    for rid, record in records.items():
        clean, _ = redact(record.text)
        if any(h.mode == PROBE_MODE for h in find_defect_hits(clean)):
            old_pred.add(rid)
        for hit in find_cooccurrence_hits(clean):
            new_pred.add(rid)
            evidence.append({
                "record_id": rid,
                "topic": hit.topic, "fault": hit.fault,
                "fault_family": hit.family,
                "quote": hit.quote[:180],
                "label_modes": labels[rid],
                "is_true_positive": rid in gold,
            })
            break  # one candidate per record

    # Design-set recovery: split H's ten human data_integrity rows are the
    # cases the vocabulary was written from. This number is deliberately
    # NOT publishable and is reported only to show the H/I gap.
    design_set: dict = {"role": "design_set_recovery", "publishable": False}
    h_corpus = ROOT / ".local/corpus/holdoutH.jsonl"
    h_result = PART / "human_agreement_v2.json"
    if h_corpus.exists() and h_result.exists():
        h_part = json.loads((PART / "partitions_h.json").read_text(encoding="utf-8"))
        h_order = [rid for b in h_part["holdout"].values() for rid in b]
        h_rows = json.loads(h_result.read_text(encoding="utf-8"))
        h_labels = h_rows["readers"]["H_r1"]["primary_only"]["rows"]
        h_recs = {r.id: r for r in load_records(h_corpus)}
        h_gold = {h_order[i] for i, r in enumerate(h_labels)
                  if r["primary"] == PROBE_MODE}
        h_pred = {rid for rid, rec in h_recs.items()
                  if find_cooccurrence_hits(redact(rec.text)[0])}
        design_set = {
            "role": "design_set_recovery",
            "publishable": False,
            "annotator": "human (one confirmed reader, v2 rule)",
            "warning": ("The vocabulary contains phrases copied verbatim from "
                        "these H titles. This number measures fit to the answer "
                        "key, not predictive performance. Never quote it."),
            "precision": len(h_pred & h_gold) / len(h_pred) if h_pred else 0.0,
            "recall": len(h_pred & h_gold) / len(h_gold) if h_gold else 0.0,
            "predicted": len(h_pred), "gold": len(h_gold),
            "true_positive": len(h_pred & h_gold),
        }

    baseline = metrics(universe, gold, universe)
    payload = {
        "kind": "cooccurrence_probe_check",
        "split": "I",
        "n_records": len(universe),
        "engine_version": COOCCURRENCE_VERSION,
        "vocabulary_fingerprint": fp_now,
        "disjoint_from_A_to_H": True,
        "design_set": "H (NOT used for scoring)",
        "labels": {
            "path": "eval/defect_holdout/labels_holdout_i.jsonl",
            "annotator": "model",
            "labeler_knew_experiment": True,
            "warning": ("One model wrote the labels AND designed the probe. "
                        "Labels were written before either engine was run on I, "
                        "but this is NOT independent human judgement. Results "
                        "are agreement-with-model-labels, not accuracy."),
            "mode": PROBE_MODE,
            "gold_rows": len(gold),
            "class_prior": len(gold) / len(universe),
        },
        "v0_1_phrase_engine": metrics(old_pred, gold, universe),
        "cooccurrence_probe": metrics(new_pred, gold, universe),
        "baseline_flag_everything_as_data_integrity": baseline,
        "design_set_H_not_publishable": design_set,
        "probe_evidence": evidence,
        "publishable": True,
        "not_publishable_as": ["human accuracy", "gold standard",
                               "inter-annotator agreement", "improvement over v0.1"],
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                   encoding="utf-8")

    if not args.quiet:
        for name in ("v0_1_phrase_engine", "cooccurrence_probe",
                     "baseline_flag_everything_as_data_integrity"):
            m = payload[name]
            print(f"{name:48} P={m['precision']:.3f} "
                  f"[{m['precision_ci95'][0]:.3f},{m['precision_ci95'][1]:.3f}]  "
                  f"R={m['recall']:.3f} "
                  f"[{m['recall_ci95'][0]:.3f},{m['recall_ci95'][1]:.3f}]  "
                  f"TP={m['true_positive']} FP={m['false_positive']} FN={m['false_negative']}")
        print(f"gold={len(gold)}/{len(universe)} | wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

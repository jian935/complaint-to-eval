"""Audit the v0.1 taxonomy against a *real* corpus.

Runs the deterministic engine over a feedback corpus and reports, per failure
mode, how many candidate cases fired and how many of that mode's strong
signals actually occur in the text. The point is to measure how far the
hand-written signals generalise beyond the fabricated demo, not to flatter it.

Usage:
    python scripts/audit_real_corpus.py --corpus .local/corpus/aider_corpus.jsonl --label aider

Output is plain text plus a JSON summary under out/audit/<label>.json.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from complaint_to_eval.pipeline import analyze, load_records  # noqa: E402
from complaint_to_eval.taxonomy import RULES  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", required=True)
    ap.add_argument("--label", required=True)
    ap.add_argument("--out", default="out/audit")
    args = ap.parse_args()

    records = load_records(ROOT / args.corpus if not Path(args.corpus).is_absolute() else args.corpus)
    report = analyze(records, dataset_label=args.label, synthetic=False)

    # Distinct-mode candidate counts (one finding per mode per clause already).
    cand = Counter(f["failure_mode"] for f in report["findings"])
    joined = " ".join(r.text.lower() for r in records)

    # For each mode: how many of its strong signals appear at least once?
    signal_rows = []
    total_signals = 0
    seen_signals = 0
    for rule in RULES:
        present = [s for s in rule.strong if s.lower() in joined]
        total_signals += len(rule.strong)
        seen_signals += len(present)
        signal_rows.append(
            {
                "mode": rule.mode,
                "candidates": cand.get(rule.mode, 0),
                "strong_total": len(rule.strong),
                "strong_seen": len(present),
                "examples_seen": present[:3],
            }
        )

    summary = {
        "label": args.label,
        "records": len(records),
        "candidates": report["honesty"]["candidate_cases"],
        "records_with_no_finding": len(records) - len({f["record_id"] for f in report["findings"]}),
        "redactions": report["redactions"],
        "strong_signals_total": total_signals,
        "strong_signals_seen": seen_signals,
        "per_mode": signal_rows,
    }

    out = Path(args.out)
    if not out.is_absolute():
        out = ROOT / out
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{args.label}.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[{args.label}] records={len(records)} candidates={report['honesty']['candidate_cases']} "
          f"records_with_no_finding={summary['records_with_no_finding']}")
    print(f"  strong signals present in corpus: {seen_signals}/{total_signals}")
    print(f"  {'mode':18} {'cands':>6} {'signals_seen':>12}  examples")
    for row in signal_rows:
        ex = ", ".join(row["examples_seen"]) if row["examples_seen"] else "-"
        print(f"  {row['mode']:18} {row['candidates']:>6} {row['strong_seen']:>3}/{row['strong_total']:<3}   {ex}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Fourth hold-out (set D) — the only split no signal change has ever seen.

Lineage of contamination:
  * A  — used for the first round of error analysis (signals were added from it).
  * B  — one boundary fix was made after seeing it miss "silently truncates".
  * C  — measured clean (0.711 / 0.771), then its false positives were inspected,
         which motivated blanking quoted code. So C is no longer clean either.

Set D excludes A, B and C and uses a fresh salt. Every signal in this run was
written before D was drawn, so D is the first split where the reported number
is not the number that produced the change.

The dify corpus was expanded (pages 3-6) before drawing D, because A+B+C had
exhausted the original 47 issues; without that, D would have been aider-only and
precision would have been dominated by crash reports.

Rule: drop A/B/C ids, sort the rest by md5("v4:" + record_id), take up to N per
corpus. Pools smaller than N are capped and reported, never padded.

Usage:
    python scripts/split_holdout_d.py
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

SOURCES = {
    "aider": (ROOT / ".local/corpus/aider_corpus.jsonl", 24),
    "dify": (ROOT / ".local/corpus/dify_corpus.jsonl", 16),
}
PARTITIONS = [
    ROOT / "eval/defect_holdout/partitions.json",
    ROOT / "eval/defect_holdout/partitions_b.json",
    ROOT / "eval/defect_holdout/partitions_c.json",
]


def _ids_from(path: Path) -> set[str]:
    data = json.loads(path.read_text(encoding="utf-8"))["holdout"]
    return {i for ids in data.values() for i in ids}


def _key(record_id: str) -> str:
    return hashlib.md5(("v4:" + record_id).encode("utf-8")).hexdigest()


def main() -> int:
    used: set[str] = set()
    for path in PARTITIONS:
        used |= _ids_from(path)

    holdout: list[dict] = []
    partition = {
        "rule": "exclude sets A, B and C; sort by md5('v4:'+id); first N per corpus",
        "holdout": {},
        "capped": {},
    }
    for name, (path, n) in SOURCES.items():
        rows = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
        pool = [r for r in rows if r["id"] not in used]
        pool.sort(key=lambda r: _key(r["id"]))
        held = pool[:n]
        if len(held) < n:
            partition["capped"][name] = {"wanted": n, "available": len(pool)}
            print(f"[{name}] POOL TOO SMALL: wanted {n}, available {len(pool)} — capped at {len(held)}")
        holdout.extend(held)
        partition["holdout"][name] = [r["id"] for r in held]
        print(f"[{name}] pool={len(pool)} holdoutD={len(held)}")

    out_local = ROOT / ".local/corpus/holdoutD.jsonl"
    with out_local.open("w", encoding="utf-8") as fh:
        for r in holdout:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")

    (ROOT / "eval/defect_holdout/partitions_d.json").write_text(
        json.dumps(partition, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    d_ids = {r["id"] for r in holdout}
    print(f"\noverlap with A/B/C: {len(used & d_ids)} (must be 0)")
    print(f"wrote {out_local} ({len(holdout)} records)")
    print("\n=== LABELLING LINES (set D) ===")
    for r in holdout:
        text = " ".join(r["text"].split())[:320]
        print(f"{r['id']} :: {text}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

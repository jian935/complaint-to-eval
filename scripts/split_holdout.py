"""Deterministic dev/hold-out split for defect-taxonomy evaluation.

Rule: sort each corpus by md5(record_id), take the first N as hold-out, the rest
as dev. Deterministic and reproducible from record ids alone (no text ships).
Writes hold-out records to a local corpus file and the id list to eval/.

Usage:
    python scripts/split_holdout.py            # prints labelling lines + writes files
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

SOURCES = {
    "aider": (ROOT / ".local/corpus/aider_corpus.jsonl", 24),
    "dify": (ROOT / ".local/corpus/dify_corpus.jsonl", 16),
}


def _key(record_id: str) -> str:
    return hashlib.md5(record_id.encode("utf-8")).hexdigest()


def main() -> int:
    holdout: list[dict] = []
    partition = {"rule": "sort by md5(record_id); first N per corpus is hold-out", "holdout": {}}
    for name, (path, n) in SOURCES.items():
        rows = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
        rows.sort(key=lambda r: _key(r["id"]))
        held = rows[:n]
        holdout.extend(held)
        partition["holdout"][name] = [r["id"] for r in held]
        print(f"[{name}] total={len(rows)} holdout={len(held)} dev={len(rows) - len(held)}")

    out_local = ROOT / ".local/corpus/holdout.jsonl"
    out_local.parent.mkdir(parents=True, exist_ok=True)
    with out_local.open("w", encoding="utf-8") as fh:
        for r in holdout:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")

    eval_dir = ROOT / "eval/defect_holdout"
    eval_dir.mkdir(parents=True, exist_ok=True)
    (eval_dir / "partitions_a.json").write_text(
        json.dumps(partition, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(f"\nwrote {out_local} ({len(holdout)} records)")
    print(f"wrote {eval_dir / 'partitions_a.json'}")
    print("\n=== LABELLING LINES (id :: text) ===")
    for r in holdout:
        text = " ".join(r["text"].split())[:300]
        print(f"{r['id']} :: {text}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

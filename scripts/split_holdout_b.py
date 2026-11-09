"""Second, disjoint hold-out (set B) for re-validating defect signals.

Set A (eval/defect_holdout/partitions.json) was used for error analysis. Set B
must be disjoint from A so that signal changes motivated by A are tested on a
fresh split. Rule: drop A ids, sort the rest by md5("v2" + record_id), take the
first N per corpus.

Usage:
    python scripts/split_holdout_b.py
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
SET_A = ROOT / "eval/defect_holdout/partitions.json"


def _key(record_id: str) -> str:
    return hashlib.md5(("v2:" + record_id).encode("utf-8")).hexdigest()


def main() -> int:
    a_ids = {i for ids in json.loads(SET_A.read_text(encoding="utf-8"))["holdout"].values() for i in ids}

    holdout: list[dict] = []
    partition = {"rule": "exclude set A; sort by md5('v2:'+id); first N per corpus", "holdout": {}}
    for name, (path, n) in SOURCES.items():
        rows = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
        pool = [r for r in rows if r["id"] not in a_ids]
        pool.sort(key=lambda r: _key(r["id"]))
        held = pool[:n]
        holdout.extend(held)
        partition["holdout"][name] = [r["id"] for r in held]
        print(f"[{name}] pool={len(pool)} holdoutB={len(held)} derive={len(pool) - len(held)}")

    out_local = ROOT / ".local/corpus/holdoutB.jsonl"
    with out_local.open("w", encoding="utf-8") as fh:
        for r in holdout:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")

    (ROOT / "eval/defect_holdout/partitions_b.json").write_text(
        json.dumps(partition, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(f"\nwrote {out_local} ({len(holdout)} records)")
    print("\n=== LABELLING LINES (set B) ===")
    for r in holdout:
        text = " ".join(r["text"].split())[:300]
        print(f"{r['id']} :: {text}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

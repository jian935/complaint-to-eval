"""Third, disjoint hold-out (set C) — clean confirmation of round 2 numbers.

Sets A and B have both been looked at: A drove the first round of signal changes,
and one boundary fix was made after seeing B miss "silently truncates". Any number
measured on A or B is therefore mildly contaminated. Set C excludes both and uses a
fresh salt, so it is the first split that no signal change has ever seen.

Rule: drop A and B ids, sort the rest by md5("v3:" + record_id), take up to N per
corpus. Pools smaller than N are capped and reported, not padded.

Usage:
    python scripts/split_holdout_c.py
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
SET_B = ROOT / "eval/defect_holdout/partitions_b.json"


def _ids_from(path: Path) -> set[str]:
    data = json.loads(path.read_text(encoding="utf-8"))["holdout"]
    return {i for ids in data.values() for i in ids}


def _key(record_id: str) -> str:
    return hashlib.md5(("v3:" + record_id).encode("utf-8")).hexdigest()


def main() -> int:
    used = _ids_from(SET_A) | _ids_from(SET_B)

    holdout: list[dict] = []
    partition = {
        "rule": "exclude sets A and B; sort by md5('v3:'+id); first N per corpus",
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
        print(f"[{name}] pool={len(pool)} holdoutC={len(held)}")

    out_local = ROOT / ".local/corpus/holdoutC.jsonl"
    with out_local.open("w", encoding="utf-8") as fh:
        for r in holdout:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")

    (ROOT / "eval/defect_holdout/partitions_c.json").write_text(
        json.dumps(partition, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    a_ids = _ids_from(SET_A)
    b_ids = _ids_from(SET_B)
    c_ids = {r["id"] for r in holdout}
    print(f"\noverlap A∩C={len(a_ids & c_ids)} B∩C={len(b_ids & c_ids)}")
    print(f"wrote {out_local} ({len(holdout)} records)")
    print("\n=== LABELLING LINES (set C) ===")
    for r in holdout:
        text = " ".join(r["text"].split())[:300]
        print(f"{r['id']} :: {text}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

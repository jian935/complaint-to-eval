"""Generic hold-out drawer for new evaluation sets (sets E and later).

The first four sets keep their own frozen scripts so each drawing rule stays
auditable: ``split_holdout.py`` (A, hash of the record id), ``split_holdout_b.py``,
``split_holdout_c.py``, ``split_holdout_d.py``. New sets use this tool instead of
copying that logic a fifth time.

Rule, always: exclude every id already used by earlier sets, sort the rest by
``md5("<salt>:<record_id>")``, take up to N per corpus. Pools that are too small
are capped and reported — never padded, never re-drawn after seeing results.

Usage:
    python scripts/draw_holdout.py --salt v5 --name e \
        --exclude eval/defect_holdout/partitions_a.json \
        --exclude eval/defect_holdout/partitions_b.json \
        --exclude eval/defect_holdout/partitions_c.json \
        --exclude eval/defect_holdout/partitions_d.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

SOURCES = {
    "aider": ROOT / ".local/corpus/aider_corpus.jsonl",
    "dify": ROOT / ".local/corpus/dify_corpus.jsonl",
}


def _ids_from(path: Path) -> set[str]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))["holdout"]
    return {i for ids in data.values() for i in ids}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--salt", required=True, help="hash salt, e.g. v5")
    ap.add_argument("--name", required=True, help="set name, e.g. e")
    ap.add_argument("--exclude", action="append", default=[], help="partitions_*.json to exclude")
    ap.add_argument("--aider-n", type=int, default=24)
    ap.add_argument("--dify-n", type=int, default=16)
    args = ap.parse_args()

    used: set[str] = set()
    for path in args.exclude:
        resolved = Path(path) if Path(path).is_absolute() else ROOT / path
        used |= _ids_from(resolved)

    wanted = {"aider": args.aider_n, "dify": args.dify_n}
    holdout: list[dict] = []
    partition: dict = {
        "rule": f"exclude earlier sets; sort by md5('{args.salt}:'+id); first N per corpus",
        "holdout": {},
        "capped": {},
    }

    for name, path in SOURCES.items():
        n = wanted[name]
        rows = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
        pool = [r for r in rows if r["id"] not in used]
        pool.sort(key=lambda r: hashlib.md5(f"{args.salt}:{r['id']}".encode("utf-8")).hexdigest())
        held = pool[:n]
        if len(held) < n:
            partition["capped"][name] = {"wanted": n, "available": len(pool)}
            print(f"[{name}] POOL TOO SMALL: wanted {n}, available {len(pool)} — capped at {len(held)}")
        holdout.extend(held)
        partition["holdout"][name] = [r["id"] for r in held]
        print(f"[{name}] pool={len(pool)} holdout={len(held)}")

    out_local = ROOT / f".local/corpus/holdout{args.name.upper()}.jsonl"
    with out_local.open("w", encoding="utf-8") as fh:
        for r in holdout:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")

    target = ROOT / f"eval/defect_holdout/partitions_{args.name}.json"
    target.write_text(json.dumps(partition, ensure_ascii=False, indent=2), encoding="utf-8")

    new_ids = {r["id"] for r in holdout}
    print(f"\noverlap with excluded sets: {len(used & new_ids)} (must be 0)")
    print(f"wrote {out_local} ({len(holdout)} records)")
    print(f"wrote {target}")
    print(f"\n=== LABELLING LINES (set {args.name.upper()}) ===")
    for r in holdout:
        text = " ".join(r["text"].split())[:320]
        print(f"{r['id']} :: {text}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

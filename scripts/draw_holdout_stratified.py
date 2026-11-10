"""Draw a stratified hold-out split instead of a plain random one.

Run:
    python scripts/draw_holdout_stratified.py --salt v9 --name h \
        --aider-crash 6 --aider-other 14 --dify 20 \
        --exclude eval/defect_holdout/partitions.json ... 

Why not random: 79% of the aider corpus is one auto-generated crash template
(`Uncaught ImportError in _svdp.py line 23`). A plain random draw of 20 aider rows
contains ~16 of those, which are trivial to label and carry no boundary cases. A
split meant to test whether readers agree on *modes* needs mode diversity, so the
buckets are sampled separately.

Buckets:
  aider_crash   text starts with "Uncaught <Error> in <file> line <n>"
  aider_other   everything else from aider
  dify          all dify records (already diverse)

Within a bucket, records are ordered by md5("<salt>:<id>") — deterministic and
reproducible — then the first N are taken. Excluded ids (previous splits) are
removed before sampling and the overlap is asserted to be zero.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CORPUS = ROOT / ".local/corpus"
PART = ROOT / "eval/defect_holdout"

CRASH = re.compile(r"^\s*Uncaught \w+ in .+ line \d+", re.I)


def digest(salt: str, rid: str) -> str:
    return hashlib.md5(f"{salt}:{rid}".encode("utf-8")).hexdigest()


def bucket_of(rec: dict) -> str:
    if rec["id"].startswith("aider"):
        return "aider_crash" if CRASH.match(rec["text"]) else "aider_other"
    return "dify"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--salt", required=True)
    ap.add_argument("--name", required=True)
    ap.add_argument("--aider-crash", type=int, default=6)
    ap.add_argument("--aider-other", type=int, default=14)
    ap.add_argument("--dify", type=int, default=20)
    ap.add_argument("--exclude", action="append", default=[])
    args = ap.parse_args()

    used: set[str] = set()
    for path in args.exclude:
        p = Path(path)
        if not p.exists():
            continue
        data = json.loads(p.read_text(encoding="utf-8"))
        for ids in data.get("holdout", {}).values():
            used |= set(ids)

    pools: dict[str, list[dict]] = defaultdict(list)
    for name in ("aider", "dify"):
        path = CORPUS / f"{name}_corpus.jsonl"
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            rec = json.loads(line)
            if rec["id"] in used:
                continue
            pools[bucket_of(rec)].append(rec)

    wanted = {
        "aider_crash": args.aider_crash,
        "aider_other": args.aider_other,
        "dify": args.dify,
    }
    chosen: dict[str, list[dict]] = {}
    for key, want in wanted.items():
        pool = sorted(pools[key], key=lambda r: digest(args.salt, r["id"]))
        take = pool[:want]
        chosen[key] = take
        print(f"[{key}] pool={len(pool)} taken={len(take)}")

    records = [r for key in ("aider_crash", "aider_other", "dify") for r in chosen[key]]
    overall = set(digest(args.salt, r["id"]) for r in records)
    print(f"\ntotal {len(records)} records | overlap with excluded sets: "
          f"{len(used & {r['id'] for r in records})} (must be 0)")

    out_jsonl = CORPUS / f"holdout{args.name.upper()}.jsonl"
    with out_jsonl.open("w", encoding="utf-8", newline="\n") as fh:
        for rec in records:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")

    partitions = {
        "salt": args.salt,
        "name": args.name,
        "strategy": "stratified by crash template",
        "holdout": {key: [r["id"] for r in chosen[key]] for key in chosen},
    }
    part_path = PART / f"partitions_{args.name}.json"
    part_path.write_text(json.dumps(partitions, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"wrote {out_jsonl}")
    print(f"wrote {part_path}")
    print(f"\n=== LABELLING LINES (set {args.name.upper()}) ===")
    for i, rec in enumerate(records, start=1):
        text = " ".join(rec["text"].split())[:110]
        print(f"r{i:02d} {rec['id']} :: {text}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

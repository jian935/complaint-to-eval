"""Set G: a deliberately balanced (50/50) split to measure precision under a realistic prior.

Why this exists. Every split A-F is ~88% defect reports, because both source repos
are defect trackers. That inflates precision: with few negatives, a false positive
rate of 0.2 barely moves the number. A real triage queue contains far more feature
requests and questions, so the published precision must also be reported at a prior
closer to reality.

This set is *deliberately* balanced rather than randomly drawn, and the selection is
by hand from the unused pool (title says "Feature"/"Add"/"Chore"/"Question", or the
body is a vendor pitch / spam). Selection bias is therefore real and is disclosed:
the negatives here are the kind of non-defect a triage queue actually contains, not a
uniform sample of non-defects.

Usage:
    python scripts/draw_holdout_g.py
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASE = ROOT / "eval/defect_holdout"

# Hand-picked negatives: feature requests, chores, questions, vendor pitches, spam.
NEGATIVE = [
    "aider-5719",  # vendor pitch: hosted MCP for smaller context
    "aider-5713",  # docs request: add a provider to the docs
    "aider-5712",  # feature request: hook system
    "aider-5677",  # feature proposal, body says "Issue None"
    "aider-5676",  # feature request: model resilience on 404/402
    "aider-5673",  # question about project maintenance
    "aider-5647",  # discussion about maintenance status
    "aider-5646",  # spam
    "aider-5639",  # docs contribution
    "aider-5634",  # vendor offer: leaderboard runs
    "dify-45584",  # chore/refactor
    "dify-45573",  # feature: run chat on its own model
    "dify-45560",  # feature: output moderation mode
    "dify-45559",  # feature: OpenTelemetry spans
    "dify-45539",  # feature: personal access token
    "dify-45448",  # feature: OpenTelemetry metrics
    "dify-45355",  # chore: dependency upgrade
    "dify-45352",  # refactor/chore
    "dify-45349",  # chore: release preparation
    "dify-45213",  # feature: maintenance triage skill
]

# Hand-picked positives: fresh defect reports, none used by sets A-F.
POSITIVE = [
    "aider-5761",  # benchmark marks solved on non-zero exit (logic)
    "aider-5748",  # auto-accept default applies edits without asking (config/logic)
    "aider-5706",  # valid multi-file edit silently discarded (data loss)
    "aider-5681",  # benchmark scores on exit code (logic)
    "aider-5662",  # find_filename misses indented fences (logic)
    "aider-5654",  # stream drops leading lines (data loss)
    "aider-5624",  # reads output one char at a time, ~60x slower (performance)
    "aider-5622",  # .env overrides exported vars (config)
    "dify-45701",  # file defaults ignore configured size limits (config)
    "dify-45684",  # form arrays encoded as Python list string (logic)
    "dify-45682",  # think block collapses mid-stream (ui)
    "dify-45667",  # dialogs overflow viewport (ui)
    "dify-45609",  # cron parser rejects quoted expressions (logic)
    "dify-45580",  # API returns 400 (crash/error)
    "dify-45547",  # small exponent numbers truncated to zero (data)
    "dify-45516",  # negative index returns the wrong document (logic)
    "dify-45508",  # mismatched vector/document counts accepted (logic)
    "dify-45422",  # converted bases lose source-file downloads (data loss)
    "dify-45391",  # crypto.randomUUID is not a function (crash)
    "dify-45184",  # markdown link removal corrupts images (data)
]


def _ids_from(path: Path) -> set[str]:
    data = json.loads(path.read_text(encoding="utf-8"))["holdout"]
    return {i for ids in data.values() for i in ids}


def main() -> int:
    used: set[str] = set()
    for p in sorted(BASE.glob("partitions*.json")):
        if p.name == "partitions_g.json":
            continue
        used |= _ids_from(p)

    chosen = NEGATIVE + POSITIVE
    dupes = {i for i in chosen if chosen.count(i) > 1}
    overlap = set(chosen) & used
    if dupes or overlap:
        print(f"ABORT duplicates={sorted(dupes)} overlap_with_A_F={sorted(overlap)}")
        return 1

    rows: dict[str, dict] = {}
    for name in ("aider", "dify"):
        path = ROOT / f".local/corpus/{name}_corpus.jsonl"
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                rows[r["id"]] = r

    missing = [i for i in chosen if i not in rows]
    if missing:
        print(f"ABORT ids not in corpus: {missing}")
        return 1

    holdout = [rows[i] for i in chosen]
    out_local = ROOT / ".local/corpus/holdoutG.jsonl"
    with out_local.open("w", encoding="utf-8", newline="\n") as fh:
        for r in holdout:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")

    partition = {
        "rule": "hand-picked 50/50 mix: 20 non-defect (feature/chore/question/pitch) + 20 defect",
        "holdout": {"balanced": chosen},
        "design": {
            "positives": POSITIVE,
            "negatives": NEGATIVE,
            "note": "deliberately balanced, not a random draw; see draw_holdout_g.py docstring",
        },
        "capped": {},
    }
    (BASE / "partitions_g.json").write_text(
        json.dumps(partition, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(f"wrote {out_local} ({len(holdout)} records: 20 negative, 20 positive)")
    print("overlap with A-F: 0")
    print("\n=== LABELLING LINES (set G) ===")
    for r in holdout:
        text = " ".join(r["text"].split())[:300]
        print(f"{r['id']} :: {text}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Compare two runs. Candidates only: no fix-rate claims are produced."""

from __future__ import annotations


def _index(report: dict) -> dict[str, dict]:
    return {
        case["key"]: {
            "id": case["id"],
            "key": case["key"],
            "failure_mode": case["failure_mode"],
            "input": case["input"],
            "status": case.get("status", "candidate"),
        }
        for case in report.get("cases", [])
    }


def compare(base: dict, head: dict) -> dict:
    older, newer = _index(base), _index(head)
    added = [newer[k] for k in sorted(newer.keys() - older.keys())]
    resolved = [older[k] for k in sorted(older.keys() - newer.keys())]
    persistent = [newer[k] for k in sorted(older.keys() & newer.keys())]
    return {
        "schema_version": "0.1",
        "base": {
            "run_id": base.get("run_id"),
            "dataset": base.get("dataset"),
            "candidate_cases": len(older),
        },
        "head": {
            "run_id": head.get("run_id"),
            "dataset": head.get("dataset"),
            "candidate_cases": len(newer),
        },
        "added": added,
        "resolved": resolved,
        "persistent": persistent,
        "summary": {
            "added": len(added),
            "resolved_candidates": len(resolved),
            "persistent": len(persistent),
            "note": (
                "These are UNREVIEWED CANDIDATES from a deterministic classifier. "
                "This is a diff of matched phrases, NOT a measured fix rate, "
                "NOT an accuracy figure, and NOT evidence that anything improved."
            ),
        },
    }

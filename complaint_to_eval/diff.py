"""Compare two runs. Candidates only: no fix-rate claims are produced.

Only ``cte run``'s ``report.json`` is accepted: its cases carry a stable
``key``. ``cte defects`` writes ``defects.json`` with ordinal ids that can
shift between runs, so diffing it would produce unreliable
``resolved_candidates``. Passing that file here used to raise a bare
``KeyError`` with no explanation; it now fails with a readable message.
"""

from __future__ import annotations

_INPUT_HINT = (
    "only `cte run`'s report.json can be diffed: its cases carry a stable `key`. "
    "`cte defects` writes defects.json, whose cases have ordinal ids "
    "(`finding_id` / `id`) that can shift between runs; using them would "
    "produce unreliable `resolved_candidates`, so this command refuses it."
)


def _validated_cases(report: dict, label: str) -> list[dict]:
    if not isinstance(report, dict):
        raise ValueError(f"{label}: expected a JSON object (report.json); {_INPUT_HINT}")
    cases = report.get("cases")
    if not isinstance(cases, list):
        raise ValueError(f"{label}: expected a `cases` list. {_INPUT_HINT}")
    required = ("key", "id", "failure_mode", "input")
    for i, case in enumerate(cases):
        if not isinstance(case, dict):
            raise ValueError(f"{label}: case #{i} is not a JSON object")
        missing = [k for k in required if k not in case]
        if missing:
            raise ValueError(
                f"{label}: case #{i} is missing {', '.join(missing)}. {_INPUT_HINT}"
            )
    return cases


def _index(cases: list[dict]) -> dict[str, dict]:
    return {
        case["key"]: {
            "id": case["id"],
            "key": case["key"],
            "failure_mode": case["failure_mode"],
            "input": case["input"],
            "status": case.get("status", "candidate"),
        }
        for case in cases
    }


def compare(base: dict, head: dict) -> dict:
    older = _index(_validated_cases(base, "base"))
    newer = _index(_validated_cases(head, "head"))
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

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from complaint_to_eval.diff import compare  # noqa: E402
from complaint_to_eval.exporters import to_promptfoo_candidates, to_markdown  # noqa: E402


def _report(cases, run_id):
    return {
        "run_id": run_id,
        "dataset": {"label": "unit", "provenance": "synthetic", "records": 1},
        "cases": cases,
    }


def _case(key, mode="wrong_fact"):
    return {
        "id": "cte-" + key,
        "key": key,
        "failure_mode": mode,
        "input": "some quote",
        "status": "candidate",
        "human_review_required": True,
        "review": None,
        "evidence_record_id": "r1",
        "finding_id": "f-" + key,
        "assertion": {"type": "must_not_reproduce_failure_mode", "value": mode,
                      "description": "test"},
    }


class TestDiff(unittest.TestCase):
    def test_added_resolved_persistent(self):
        base = _report([_case("a"), _case("b")], "base")
        head = _report([_case("b"), _case("c")], "head")
        result = compare(base, head)
        self.assertEqual(["c"], [c["key"] for c in result["added"]])
        self.assertEqual(["a"], [c["key"] for c in result["resolved"]])
        self.assertEqual(["b"], [c["key"] for c in result["persistent"]])
        self.assertEqual(1, result["summary"]["added"])
        self.assertEqual(1, result["summary"]["resolved_candidates"])

    def test_diff_never_calls_itself_a_fix_rate(self):
        result = compare(_report([], "a"), _report([], "b"))
        self.assertIn("NOT a measured fix rate", result["summary"]["note"])

    def test_rejects_defects_json_shape_with_a_readable_error(self):
        bad = {"findings": [{"record_id": "r1", "mode": "crash_or_error"}]}
        with self.assertRaises(ValueError) as ctx:
            compare(bad, _report([], "head"))
        self.assertIn("report.json", str(ctx.exception))
        self.assertIn("defects.json", str(ctx.exception))

    def test_rejects_case_missing_required_fields(self):
        bad = _report([{"key": "a"}], "base")
        with self.assertRaises(ValueError) as ctx:
            compare(bad, _report([], "head"))
        self.assertIn("missing", str(ctx.exception))

    def test_cli_returns_2_instead_of_a_traceback(self):
        import argparse
        import contextlib
        import io
        from unittest.mock import patch

        from complaint_to_eval.cli import _cmd_diff

        buf = io.StringIO()
        ns = argparse.Namespace(base="a.json", head="b.json", out="")
        with patch("complaint_to_eval.cli.Path.read_text",
                   return_value='{"findings": []}'), contextlib.redirect_stderr(buf):
            rc = _cmd_diff(ns)
        self.assertEqual(2, rc)
        self.assertIn("report.json", buf.getvalue())
        self.assertNotIn("Traceback", buf.getvalue())


class TestExporters(unittest.TestCase):
    def setUp(self):
        self.report = {
            "schema_version": "0.1",
            "tool": "complaint-to-eval",
            "taxonomy_version": "0.1.0-draft",
            "run_id": "unit",
            "dataset": {"label": "unit", "provenance": "synthetic", "records": 1},
            "honesty": {"candidate_cases": 1, "accepted_cases": 0, "note": "none"},
            "counts": {"wrong_fact": 1},
            "total_findings": 1,
            "redactions": {},
            "warnings": ["UNREVIEWED CANDIDATES", "FABRICATED"],
            "findings": [{
                "id": "f-0001", "record_id": "r1", "source": "unit",
                "product": "", "version": "", "failure_mode": "wrong_fact",
                "matched_phrase": "编造数据", "strength": "strong",
                "evidence": {"quote": "回答里编造数据", "start": 3, "end": 7,
                             "offsets_refer_to": "redacted text"},
                "key": "k", "status": "candidate",
            }],
            "cases": [_case("k")],
        }

    def test_markdown_repeats_the_honesty_header(self):
        text = to_markdown(self.report)
        self.assertIn("UNREVIEWED CANDIDATES", text)
        self.assertIn("FABRICATED", text)
        self.assertIn("Accepted (human-reviewed) cases: **0**", text)

    def test_promptfoo_export_is_not_a_config(self):
        payload = to_promptfoo_candidates(self.report)
        self.assertEqual("promptfoo-test-candidates", payload["format"])
        self.assertIn("NOT a promptfoo config", payload["note"])
        self.assertEqual("candidate", payload["tests"][0]["status"])


if __name__ == "__main__":
    unittest.main()

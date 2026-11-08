import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from complaint_to_eval.pipeline import (  # noqa: E402
    PROVENANCE_WARNING,
    SYNTHETIC_WARNING,
    FeedbackRecord,
    analyze,
    case_key,
    load_records,
)

ROOT = Path(__file__).resolve().parents[1]


class TestLoading(unittest.TestCase):
    def test_builtin_demo_skips_comment_lines(self):
        records = load_records(ROOT / "complaint_to_eval" / "demo.jsonl")
        self.assertEqual(12, len(records))
        self.assertEqual("demo-001", records[0].id)

    def test_csv_loading(self):
        with tempfile.TemporaryDirectory(dir=str(ROOT)) as tmp:
            path = Path(tmp) / "f.csv"
            path.write_text("id,text,source\nr1,回答里编造数据,public\n", encoding="utf-8")
            records = load_records(path)
        self.assertEqual(1, len(records))
        self.assertEqual("r1", records[0].id)
        self.assertEqual("public", records[0].source)

    def test_bad_json_reports_line_number(self):
        with tempfile.TemporaryDirectory(dir=str(ROOT)) as tmp:
            path = Path(tmp) / "f.jsonl"
            path.write_text('{"id":"a","text":"ok"}\nNOT JSON\n', encoding="utf-8")
            with self.assertRaises(ValueError) as ctx:
                load_records(path)
        self.assertIn(":2:", str(ctx.exception))

    def test_unsupported_suffix(self):
        with self.assertRaises(ValueError):
            load_records(ROOT / "eval" / "ANNOTATION_GUIDE.md")


class TestAnalyze(unittest.TestCase):
    def setUp(self):
        self.records = [
            FeedbackRecord("r1", "回答里编造数据，邮箱 a.li@example.com", "public"),
            FeedbackRecord("r2", "这个数字挺好看的。", "public"),
        ]

    def test_output_shape_and_honesty(self):
        report = analyze(self.records, dataset_label="unit", synthetic=True, run_id="t")
        self.assertEqual("synthetic", report["dataset"]["provenance"])
        self.assertEqual(2, report["dataset"]["records"])
        self.assertEqual(0, report["honesty"]["accepted_cases"])
        self.assertEqual(report["total_findings"], report["honesty"]["candidate_cases"])
        for case in report["cases"]:
            self.assertEqual("candidate", case["status"])
            self.assertTrue(case["human_review_required"])
            self.assertIsNone(case["review"])

    def test_redaction_reaches_the_evidence(self):
        report = analyze(self.records, synthetic=True, run_id="t")
        blob = json.dumps(report, ensure_ascii=False)
        self.assertIn("[EMAIL]", blob)
        self.assertNotIn("a.li@example.com", blob)
        self.assertEqual({"EMAIL": 1}, report["redactions"])

    def test_context_free_generic_sentence_produces_nothing(self):
        report = analyze([self.records[1]], synthetic=True, run_id="t")
        self.assertEqual(0, report["total_findings"])

    def test_provenance_when_undeclared(self):
        report = analyze(self.records, run_id="t")
        self.assertEqual("unspecified", report["dataset"]["provenance"])
        self.assertIn(PROVENANCE_WARNING, report["warnings"])

    def test_synthetic_warning(self):
        report = analyze(self.records, synthetic=True, run_id="t")
        self.assertIn(SYNTHETIC_WARNING, report["warnings"])

    def test_real_is_declared_not_verified(self):
        report = analyze(self.records, synthetic=False, run_id="t")
        self.assertEqual("declared-real", report["dataset"]["provenance"])
        self.assertNotIn(PROVENANCE_WARNING, report["warnings"])

    def test_empty_input(self):
        report = analyze([], synthetic=True, run_id="t")
        self.assertEqual(0, report["total_findings"])
        self.assertEqual(0, report["honesty"]["accepted_cases"])

    def test_case_key_is_stable_under_whitespace_and_case(self):
        self.assertEqual(
            case_key("wrong_fact", "  A  Hallucinated   Number "),
            case_key("wrong_fact", "a hallucinated number"),
        )
        self.assertNotEqual(
            case_key("wrong_fact", "same text"),
            case_key("loop_cost", "same text"),
        )


if __name__ == "__main__":
    unittest.main()

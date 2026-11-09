"""Tests for the defect-report taxonomy and the `cte defects` command."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from complaint_to_eval.defects import (  # noqa: E402
    DEFECT_MODES,
    analyze_defects,
    find_defect_hits,
    validate_defect_taxonomy,
)
from complaint_to_eval.pipeline import load_records  # noqa: E402

FIXTURE = ROOT / "tests" / "fixtures" / "defect_input.jsonl"


def modes_of(text: str) -> list[str]:
    return sorted({h.mode for h in find_defect_hits(text)})


class DefectTaxonomyTests(unittest.TestCase):
    def test_invariants_hold(self):
        self.assertEqual([], validate_defect_taxonomy())

    def test_every_mode_has_a_rule(self):
        seen = set(DEFECT_MODES)
        for mode in modes_of("Uncaught ImportError"):
            self.assertIn(mode, seen)

    def test_crash(self):
        self.assertIn("crash_or_error", modes_of("Uncaught ImportError in main.py"))

    def test_security(self):
        self.assertIn(
            "security",
            modes_of("path traversal lets a model access files outside the repository"),
        )

    def test_ui(self):
        self.assertIn("ui_or_ux", modes_of("The sidebar hover preview is covered"))

    def test_negation_cancels_crash(self):
        # 'uncaught' is a real signal; a negator right before it cancels the hit.
        self.assertNotIn("crash_or_error", modes_of("No uncaught exception was observed"))
        self.assertIn("crash_or_error", modes_of("An uncaught exception occurred"))

    def test_word_boundary_does_not_match_inside_word(self):
        # 'hang' must NOT fire inside 'changes' — the bug this guards against.
        self.assertNotIn("performance", modes_of("the program changes files quietly"))
        # but the real word still fires
        self.assertIn("performance", modes_of("the worker hangs and never returns"))


class DefectAnalyzeTests(unittest.TestCase):
    def test_dedup_one_candidate_per_record_per_mode(self):
        records = load_records(FIXTURE)
        report = analyze_defects(records, dataset_label="fixture", synthetic=True)
        # dfix-1 and dfix-5 are crashes (dfix-5 has two sentences -> still one),
        # dfix-2 security, dfix-3 ui, dfix-4 negated (none).
        self.assertEqual(2, report["counts"]["crash_or_error"])
        self.assertEqual(1, report["counts"]["security"])
        self.assertEqual(1, report["counts"]["ui_or_ux"])
        self.assertEqual(0, report["honesty"]["accepted_cases"])
        self.assertEqual("synthetic", report["dataset"]["provenance"])

    def test_unclassified_counted(self):
        records = load_records(FIXTURE)
        report = analyze_defects(records, synthetic=True)
        self.assertGreaterEqual(report["honesty"]["unclassified_records"], 1)


class DefectCliTests(unittest.TestCase):
    def run_cli(self, *args: str):
        return subprocess.run(
            [sys.executable, "-m", "complaint_to_eval", *args],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )

    def test_defects_end_to_end(self):
        with tempfile.TemporaryDirectory() as td:
            code = self.run_cli(
                "defects", "--input", str(FIXTURE), "--synthetic", "--out", td
            ).returncode
            self.assertEqual(0, code)
            payload = json.loads((Path(td) / "defects.json").read_text(encoding="utf-8"))
            self.assertEqual(5, payload["dataset"]["records"])
            self.assertEqual(0, payload["honesty"]["accepted_cases"])
            self.assertTrue((Path(td) / "defects.md").exists())

    def test_defect_taxonomy_command(self):
        proc = self.run_cli("defect-taxonomy")
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        self.assertIn("defect-taxonomy", proc.stdout)


if __name__ == "__main__":
    unittest.main()

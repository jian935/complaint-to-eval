import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "complaint_to_eval" / "demo.jsonl"


def run_cli(*args: str) -> tuple[int, str]:
    proc = subprocess.run(
        [sys.executable, "-m", "complaint_to_eval", *args],
        cwd=str(ROOT),
        capture_output=True,
        encoding="utf-8",
        errors="replace",
    )
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


class TestCli(unittest.TestCase):
    def test_version(self):
        from complaint_to_eval import __version__
        code, out = run_cli("--version")
        self.assertEqual(0, code)
        self.assertIn(f"cte {__version__}", out)

    def test_demo_is_explicitly_synthetic(self):
        with tempfile.TemporaryDirectory(dir=str(ROOT)) as tmp:
            code, out = run_cli("demo", "--out", str(Path(tmp) / "demo"))
            self.assertEqual(0, code, out)
            self.assertIn("accepted=0", out)
            self.assertIn("provenance=synthetic", out)
            report = json.loads(
                (Path(tmp) / "demo" / "report.json").read_text(encoding="utf-8")
            )
            self.assertEqual("synthetic", report["dataset"]["provenance"])
            self.assertEqual(0, report["honesty"]["accepted_cases"])

    def test_run_declared_synthetic(self):
        with tempfile.TemporaryDirectory(dir=str(ROOT)) as tmp:
            code, out = run_cli(
                "run", "--input", str(DEMO), "--synthetic",
                "--out", str(Path(tmp) / "r"),
            )
            self.assertEqual(0, code, out)
            self.assertIn("provenance=synthetic", out)

    def test_run_without_provenance_warns(self):
        with tempfile.TemporaryDirectory(dir=str(ROOT)) as tmp:
            code, out = run_cli(
                "run", "--input", str(DEMO), "--out", str(Path(tmp) / "r")
            )
            self.assertEqual(0, code, out)
            self.assertIn("WARNING: provenance unspecified", out)

    def test_taxonomy_reports_draft(self):
        code, out = run_cli("taxonomy")
        self.assertEqual(0, code)
        self.assertIn("DRAFT", out)
        self.assertIn("No precision or recall is claimed", out)

    def test_validate_accepts_fixture_and_rejects_bad_rows(self):
        good = ROOT / "tests" / "fixtures" / "labels_valid.jsonl"
        code, out = run_cli("validate", "--labels", str(good))
        self.assertEqual(0, code, out)
        self.assertIn("OK", out)
        with tempfile.TemporaryDirectory(dir=str(ROOT)) as tmp:
            bad = Path(tmp) / "bad.jsonl"
            bad.write_text(
                '{"case_id":"x","failure_mode":"nope","decision":"accepted","annotator":"a"}\n',
                encoding="utf-8",
            )
            code, out = run_cli("validate", "--labels", str(bad))
            self.assertEqual(1, code)
            self.assertIn("INVALID", out)

    def test_privacy_scan_on_fixture(self):
        code, out = run_cli(
            "privacy", "--path", str(ROOT / "tests" / "fixtures" / "labels_valid.jsonl")
        )
        self.assertEqual(0, code, out)
        self.assertIn("OK", out)

    def test_privacy_skips_fabricated_files_unless_forced(self):
        code, out = run_cli("privacy", "--path", str(ROOT / "complaint_to_eval"))
        self.assertEqual(0, code, out)
        self.assertIn("skipped", out)
        code, out = run_cli(
            "privacy", "--path", str(ROOT / "complaint_to_eval"),
            "--include-fabricated",
        )
        self.assertEqual(1, code)
        self.assertIn("POSSIBLE PII", out)

    def test_diff_end_to_end(self):
        with tempfile.TemporaryDirectory(dir=str(ROOT)) as tmp:
            base_dir, head_dir = Path(tmp) / "base", Path(tmp) / "head"
            self.assertEqual(0, run_cli("demo", "--out", str(base_dir))[0])
            self.assertEqual(0, run_cli("demo", "--out", str(head_dir))[0])
            code, out = run_cli(
                "diff", "--base", str(base_dir / "report.json"),
                "--head", str(head_dir / "report.json"),
            )
            self.assertEqual(0, code, out)
            self.assertIn("NOT a fix rate", out)


if __name__ == "__main__":
    unittest.main()

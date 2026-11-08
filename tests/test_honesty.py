import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from complaint_to_eval.pipeline import analyze, load_records  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


class TestHonestyLocks(unittest.TestCase):
    def test_demo_file_declares_itself_fabricated(self):
        head = (ROOT / "complaint_to_eval" / "demo.jsonl").read_text(
            encoding="utf-8"
        ).splitlines()[0]
        self.assertIn("FABRICATED", head)

    def test_demo_never_yields_accepted_cases(self):
        report = analyze(
            load_records(ROOT / "complaint_to_eval" / "demo.jsonl"),
            dataset_label="built-in synthetic demo",
            synthetic=True,
            run_id="test",
        )
        self.assertEqual(0, report["honesty"]["accepted_cases"])
        self.assertTrue(all(c["status"] == "candidate" for c in report["cases"]))

    def test_readmes_link_to_each_other(self):
        en = (ROOT / "README.md").read_text(encoding="utf-8")
        zh = (ROOT / "README.zh-CN.md").read_text(encoding="utf-8")
        self.assertIn("README.zh-CN.md", en)
        self.assertIn("README.md", zh)

    def test_both_readmes_state_the_candidate_boundary(self):
        for name in ("README.md", "README.zh-CN.md"):
            text = (ROOT / name).read_text(encoding="utf-8")
            self.assertIn("candidate", text.lower(), name)
            self.assertIn("accepted", text.lower(), name)

    def test_annotation_guide_forbids_self_validation(self):
        text = (ROOT / "eval" / "ANNOTATION_GUIDE.md").read_text(encoding="utf-8")
        self.assertIn("not a labelled example", text.lower())
        self.assertIn("fix the labels, not the engine", text.lower())

    def test_private_data_dir_is_gitignored(self):
        self.assertIn(".local/", (ROOT / ".gitignore").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()

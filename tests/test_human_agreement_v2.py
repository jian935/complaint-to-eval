"""Structure locks for the v2 human-labelling round (CI-safe, no raw corpus).

The returned workbook itself lives outside the repo (third-party issue text and
hand-written reasons are not published). What IS committed is the computed result
and its writeup. These tests make sure the published numbers still add up to the
published rows, and that the round cannot quietly turn into an "accepted eval set"
or a second model-labelled split.

The helper-function tests need openpyxl; they are skipped where it is absent
(CI installs no dependencies). The artefact tests always run.
"""

from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from complaint_to_eval.defects import DEFECT_MODES  # noqa: E402

BASE = ROOT / "eval/defect_holdout"
RESULT = BASE / "human_agreement_v2.json"
WRITEUP = BASE / "human_agreement_v2.md"
SCRIPT = ROOT / "scripts" / "eval_human_agreement_v2.py"


def result() -> dict:
    return json.loads(RESULT.read_text(encoding="utf-8"))


class V2ArtefactTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = result()

    def test_result_is_human_and_not_accepted(self):
        self.assertEqual("human", self.data["annotator"])
        self.assertIn("v2", self.data["rule"])
        self.assertNotIn("accepted_cases", self.data)
        self.assertEqual([], self.data["problems"].get("H_r1", ["missing"]))

    def test_every_row_is_present_and_well_formed(self):
        d = self.data
        self.assertEqual(40, d["rows_in_split"])
        self.assertEqual(40, d["readers"]["H_r1"]["primary_only"]["scored_rows"])
        rows = d["readers"]["H_r1"]["primary_only"]["rows"]
        self.assertEqual(40, len(rows))
        for row in rows:
            self.assertIn(row["verdict"], {"是", "不是", "不确定"})
            self.assertIsInstance(row["gold"], list)
            self.assertIsInstance(row["engine"], list)
            self.assertLessEqual(len(row["secondary"]), 2)
            self.assertTrue(row["reason"], f"{row['row']} has no reason")
            if row["verdict"] == "是":
                self.assertIn(row["primary"], DEFECT_MODES)
                self.assertIn(row["primary"], row["gold"])
            else:
                self.assertEqual("", row["primary"])
                self.assertEqual([], row["gold"])

    def test_micro_adds_up_to_one_primary_per_defect_row(self):
        p = self.data["readers"]["H_r1"]["primary_only"]
        mi, rl = p["micro"], p["record_level"]
        self.assertEqual(28, mi["tp"] + mi["fn"])
        self.assertEqual(rl["human_positive"], mi["tp"] + mi["fn"])
        self.assertEqual(rl["tp"], sum(1 for r in p["rows"] if r["gold"] and r["engine"]))
        self.assertAlmostEqual(mi["precision"], mi["tp"] / (mi["tp"] + mi["fp"]))
        self.assertAlmostEqual(mi["recall"], mi["tp"] / (mi["tp"] + mi["fn"]))
        self.assertAlmostEqual(rl["precision"], rl["tp"] / rl["engine_flagged"])
        self.assertAlmostEqual(rl["recall"], rl["tp"] / rl["human_positive"])

    def test_granularity_changes_recall_not_the_rows(self):
        p = self.data["readers"]["H_r1"]["primary_only"]
        w = self.data["readers"]["H_r1"]["with_secondary"]
        self.assertEqual(p["scored_rows"], w["scored_rows"])
        self.assertEqual("primary only", p["gold_definition"])
        self.assertEqual("primary+secondary", w["gold_definition"])
        self.assertGreater(w["micro"]["fn"], p["micro"]["fn"])
        self.assertLess(w["micro"]["recall"], p["micro"]["recall"])

    def test_baselines_are_present_so_numbers_are_not_read_alone(self):
        rl = self.data["readers"]["H_r1"]["primary_only"]["record_level"]
        self.assertEqual(1.0, rl["baseline_always_flag"]["recall"])
        self.assertGreater(
            self.data["readers"]["H_r1"]["primary_only"]["baseline_top_mode"]["precision"], 0
        )

    def test_published_distribution_matches_the_rows(self):
        # The writeup quotes these counts. If the workbook changes, they must
        # change too — a hand-edited number in a doc is how this project lies.
        rows = self.data["readers"]["H_r1"]["primary_only"]["rows"]
        primaries = [r["primary"] for r in rows if r["primary"]]
        self.assertEqual(28, len(primaries))
        self.assertEqual(11, primaries.count("crash_or_error"))
        self.assertEqual(10, primaries.count("data_integrity"))
        self.assertEqual(5, primaries.count("ui_or_ux"))
        self.assertEqual(0, primaries.count("logic_or_validation"))
        causes = [m for r in rows for m in r["secondary"]]
        self.assertEqual(25, sum(1 for r in rows if r["secondary"]))
        self.assertEqual(15, causes.count("logic_or_validation"))
        self.assertIn("15 as", WRITEUP.read_text(encoding="utf-8"))

    def test_writeup_micro_numbers_are_the_computed_ones(self):
        p = self.data["readers"]["H_r1"]["primary_only"]
        text = WRITEUP.read_text(encoding="utf-8")
        for value in (p["micro"]["precision"], p["micro"]["recall"],
                      p["record_level"]["precision"], p["record_level"]["recall"]):
            self.assertIn(f"{value:.3f}", text)

    def test_writeup_states_the_one_reader_limit(self):
        text = WRITEUP.read_text(encoding="utf-8")
        self.assertIn("one reader is not an agreement study", text)
        self.assertIn("second person", text)
        self.assertIn("0.545", text)
        self.assertIn("0.429", text)

    def test_h_has_no_model_label_file(self):
        # H is the human round. Adding model labels to it would let a later
        # reader quietly re-use them as gold and break the blind design.
        self.assertFalse((BASE / "labels_holdout_h.jsonl").exists())


@unittest.skipUnless(importlib.util.find_spec("openpyxl"),
                     "openpyxl is not installed (CI runs dependency-free)")
class V2HelperTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location("v2_eval", SCRIPT)
        assert spec and spec.loader
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        cls.mod = mod

    def test_perfect_agreement_is_kappa_one(self):
        pairs = [("y", "y"), ("n", "n"), ("y", "y"), ("n", "n")]
        self.assertEqual(1.0, self.mod.cohen_kappa(pairs)[1])
        self.assertEqual(1.0, self.mod.fleiss_kappa([["a", "a"], ["b", "b"]], ["a", "b"]))

    def test_total_disagreement_drops_fleiss_below_zero(self):
        k = self.mod.fleiss_kappa(
            [["a", "b"], ["a", "b"], ["a", "b"]], ["a", "b"]
        )
        self.assertLess(k, 0.0)

    def test_wilson_bounds_contain_the_point_estimate(self):
        lo, hi = self.mod.wilson(12, 22)
        self.assertLess(lo, 12 / 22)
        self.assertGreater(hi, 12 / 22)
        self.assertEqual((0.0, 0.0), self.mod.wilson(0, 0))

    def test_split_secondary_accepts_both_comma_styles(self):
        self.assertEqual(["a", "b"], self.mod.split_secondary("a，b"))
        self.assertEqual(["a"], self.mod.split_secondary(" a "))
        self.assertEqual([], self.mod.split_secondary(""))


if __name__ == "__main__":
    unittest.main()

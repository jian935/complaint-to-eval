"""Locks for the co-occurrence NEGATIVE result (CI-safe: no raw corpus).

The probe was designed from split H and scored on split I. These tests make it
impossible to quietly edit the vocabulary, reuse H as a validation set, or
promote the model-labelled I numbers into "human accuracy".
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PART = ROOT / "eval/defect_holdout"

from complaint_to_eval.cooccurrence import (  # noqa: E402
    find_cooccurrence_hits, vocabulary_fingerprint,
)


class TestFrozenSplit(unittest.TestCase):
    def setUp(self):
        self.part = json.loads((PART / "partitions_i.json").read_text(encoding="utf-8"))
        self.result = json.loads(
            (PART / "cooccurrence_check.json").read_text(encoding="utf-8")
        )

    def test_vocabulary_has_not_changed_since_split_I_was_drawn(self):
        # Editing one fault word after seeing the results would turn I into a
        # tuning set. If you really need to change it, draw a NEW split.
        self.assertEqual(self.part["vocabulary_fingerprint"],
                         vocabulary_fingerprint())
        self.assertTrue(self.part["drawn_after_vocabulary_freeze"])
        self.assertEqual(self.result["vocabulary_fingerprint"],
                         vocabulary_fingerprint())

    def test_split_I_is_disjoint_from_every_earlier_split(self):
        ids = {rid for b in self.part["holdout"].values() for rid in b}
        self.assertEqual(40, len(ids))
        for path in sorted(PART.glob("partitions*.json")):
            if path.name == "partitions_i.json":
                continue
            other = json.loads(path.read_text(encoding="utf-8"))
            for bucket in other["holdout"].values():
                self.assertEqual(set(), ids & set(bucket),
                                 f"I overlaps {path.name}")

    def test_I_labels_are_model_only_and_cover_the_split(self):
        labels = [json.loads(l) for l in
                  (PART / "labels_holdout_i.jsonl").read_text(encoding="utf-8").splitlines()
                  if l.strip()]
        ids = {rid for b in self.part["holdout"].values() for rid in b}
        self.assertEqual(ids, {r["record_id"] for r in labels})
        self.assertTrue(all(r["annotator"] == "model" for r in labels))
        self.assertTrue(all(r.get("labeler_knew_experiment") is True for r in labels))

    def test_result_is_marked_as_model_labelled_and_not_human_accuracy(self):
        self.assertEqual("model", self.result["labels"]["annotator"])
        self.assertTrue(self.result["labels"]["labeler_knew_experiment"])
        self.assertEqual("I", self.result["split"])
        self.assertEqual("H (NOT used for scoring)", self.result["design_set"])
        banned = self.result["not_publishable_as"]
        for phrase in ("human accuracy", "gold standard",
                       "inter-annotator agreement", "improvement over v0.1"):
            self.assertIn(phrase, banned)

    def test_design_set_H_is_explicitly_not_publishable(self):
        h = self.result["design_set_H_not_publishable"]
        self.assertFalse(h["publishable"])
        self.assertEqual("design_set_recovery", h["role"])
        self.assertIn("verbatim", h["warning"])
        self.assertEqual(9, h["true_positive"])
        self.assertEqual(15, h["predicted"])
        self.assertEqual(10, h["gold"])
        self.assertAlmostEqual(0.600, h["precision"], places=3)
        self.assertAlmostEqual(0.900, h["recall"], places=3)

    def test_the_negative_result_is_locked(self):
        probe = self.result["cooccurrence_probe"]
        self.assertEqual(0, probe["true_positive"])
        self.assertEqual(11, probe["false_positive"])
        self.assertEqual(4, probe["false_negative"])
        self.assertEqual(0.0, probe["precision"])
        self.assertEqual(0.0, probe["recall"])
        self.assertEqual(4, self.result["labels"]["gold_rows"])
        old = self.result["v0_1_phrase_engine"]
        self.assertEqual(1, old["false_positive"])
        # Both intervals are wide and overlap: the md must NOT claim "worse".
        self.assertEqual(["0.000", "0.490"],
                         [f"{x:.3f}" for x in probe["recall_ci95"]])
        md = (PART / "cooccurrence_check.md").read_text(encoding="utf-8")
        self.assertIn('Do not read this as "the new design is worse"', md)
        self.assertIn("was not changed after seeing these results", md)

    def test_result_file_stores_offsets_not_issue_text(self):
        # eval/ is public. A committed result may name an id and an offset, but
        # must never carry the sentence those offsets point at -- same rule as
        # results_f/results_g.
        allowed = {"record_id", "topic", "fault", "fault_family",
                   "evidence_start", "evidence_end", "label_modes",
                   "is_true_positive"}
        self.assertTrue(self.result["probe_evidence"])
        for item in self.result["probe_evidence"]:
            self.assertEqual(allowed, set(item))
            self.assertIsInstance(item["evidence_start"], int)
            self.assertIsInstance(item["evidence_end"], int)
        raw = (PART / "cooccurrence_check.json").read_text(encoding="utf-8")
        self.assertNotIn('"quote"', raw)

    def test_probe_is_not_wired_into_the_shipping_engine(self):
        from complaint_to_eval.defects import analyze_defects
        import inspect
        src = inspect.getsource(analyze_defects)
        self.assertNotIn("cooccurrence", src)
        self.assertNotIn("find_cooccurrence_hits", src)


class TestProbeSemantics(unittest.TestCase):
    def test_neither_list_fires_alone(self):
        self.assertEqual([], find_cooccurrence_hits("The sidebar has a tooltip"))
        self.assertEqual([], find_cooccurrence_hits("Images are shown here"))
        self.assertEqual([], find_cooccurrence_hits("Something was dropped"))

    def test_cooccurrence_in_one_clause_fires(self):
        hits = find_cooccurrence_hits("DOCX extraction drops embedded images")
        self.assertEqual(1, len(hits))
        self.assertEqual("image", hits[0].topic)
        self.assertEqual("missing", hits[0].family)

    def test_absence_wording_is_a_fault_not_a_negation(self):
        # v0.1 deletes clauses starting with "does not" / "without".
        for text in ("does not send uploaded images to the model",
                     "succeeds without restoring its index",
                     "credential lookup returns nothing"):
            with self.subTest(text=text):
                self.assertTrue(find_cooccurrence_hits(text), text)

    def test_issue_template_boilerplate_is_ignored(self):
        self.assertEqual([], find_cooccurrence_hits(
            "I have searched for existing issues, including closed ones"))
        self.assertEqual([], find_cooccurrence_hits(
            "### Self Checks - [x] I confirm that I am using English"))

    def test_negation_window_is_a_known_limit_not_silently_fixed(self):
        # The negation check only looks 12 chars before the fault word, so a
        # sentence-initial "No" does NOT suppress it. This was found after I
        # was scored. Fixing it would mean editing the implementation after
        # seeing a frozen split's results, which turns I into a tuning set --
        # so the limitation is recorded, not patched.
        self.assertEqual([], find_cooccurrence_hits("images are not dropped"))
        self.assertEqual(1, len(find_cooccurrence_hits("No images are dropped")))
        self.assertIn("negation window", (PART / "cooccurrence_check.md")
                      .read_text(encoding="utf-8"))


class TestAnalyzeCooccurrence(unittest.TestCase):
    """The function the CLI actually calls, not just the matcher."""

    def setUp(self):
        from complaint_to_eval.cooccurrence import analyze_cooccurrence
        from complaint_to_eval.pipeline import load_records
        self.recs = load_records(ROOT / "tests/fixtures/defect_input.jsonl")
        self.analyze = analyze_cooccurrence

    def test_report_shape(self):
        rep = self.analyze(self.recs, dataset_label="fixture", synthetic=True)
        self.assertEqual("experimental_single_mode_probe", rep["engine_kind"])
        self.assertEqual(0, rep["honesty"]["accepted_cases"])
        self.assertEqual("synthetic", rep["dataset"]["provenance"])
        self.assertEqual("fixture", rep["dataset"]["label"])
        self.assertEqual(vocabulary_fingerprint(), rep["vocabulary_fingerprint"])
        self.assertEqual({"data_integrity": len(rep["findings"])}, rep["counts"])

    def test_one_candidate_per_record(self):
        rep = self.analyze(self.recs, synthetic=True)
        ids = [f["record_id"] for f in rep["findings"]]
        self.assertEqual(len(ids), len(set(ids)))
        for f in rep["findings"]:
            self.assertEqual("data_integrity", f["defect_mode"])
            self.assertIn("topic", f["evidence"])
            self.assertIn("fault", f["evidence"])
            self.assertIn("fault_family", f["evidence"])
            self.assertEqual("candidate", f["status"])

    def test_provenance_is_declared_not_guessed(self):
        rep = self.analyze(self.recs, synthetic=False)
        self.assertEqual("declared-real", rep["dataset"]["provenance"])
        rep = self.analyze(self.recs, synthetic=None)
        self.assertEqual("unspecified", rep["dataset"]["provenance"])


if __name__ == "__main__":
    unittest.main()

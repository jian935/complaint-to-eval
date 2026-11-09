"""Structure locks for the defect hold-out artefacts (CI-safe, no raw corpus)."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from complaint_to_eval.defects import DEFECT_MODES  # noqa: E402

LABELS = ROOT / "eval/defect_holdout/labels_holdout.jsonl"
PARTITIONS = ROOT / "eval/defect_holdout/partitions.json"
LABELS_B = ROOT / "eval/defect_holdout/labels_holdout_b.jsonl"
PARTITIONS_B = ROOT / "eval/defect_holdout/partitions_b.json"


def load_rows(path: Path) -> list[dict]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def load_labels() -> list[dict]:
    return load_rows(LABELS)


class HoldoutLabelsTests(unittest.TestCase):
    def test_labels_parse_and_fields(self):
        rows = load_labels()
        self.assertGreater(len(rows), 0)
        for row in rows:
            self.assertTrue(row.get("record_id"))
            self.assertIsInstance(row.get("modes"), list)
            self.assertTrue(row.get("note"))

    def test_modes_are_known(self):
        for row in load_labels():
            for mode in row["modes"]:
                self.assertIn(mode, DEFECT_MODES, f"{row['record_id']}: bad mode {mode}")

    def test_labels_are_never_human(self):
        # Honesty lock: this set is model-labelled. Never let it claim a human.
        for row in load_labels():
            self.assertEqual("model", row["annotator"],
                             f"{row['record_id']}: annotator must be 'model'")

    def test_no_duplicate_records(self):
        ids = [r["record_id"] for r in load_labels()]
        self.assertEqual(len(ids), len(set(ids)))

    def test_matches_partition_file(self):
        parts = json.loads(PARTITIONS.read_text(encoding="utf-8"))
        partition_ids = {i for ids in parts["holdout"].values() for i in ids}
        label_ids = {r["record_id"] for r in load_labels()}
        self.assertEqual(partition_ids, label_ids)

    def test_set_b_labels_are_model_and_valid(self):
        rows = load_rows(LABELS_B)
        self.assertGreater(len(rows), 0)
        for row in rows:
            self.assertEqual("model", row["annotator"])
            for mode in row["modes"]:
                self.assertIn(mode, DEFECT_MODES)
        parts_b = json.loads(PARTITIONS_B.read_text(encoding="utf-8"))
        b_ids = {i for ids in parts_b["holdout"].values() for i in ids}
        self.assertEqual(b_ids, {r["record_id"] for r in rows})

    def test_a_and_b_are_disjoint(self):
        # Set B must never overlap set A (else Round 2 is not a clean validation).
        a_ids = set(r["record_id"] for r in load_labels())
        b_ids = set(r["record_id"] for r in load_rows(LABELS_B))
        self.assertEqual(set(), a_ids & b_ids)


if __name__ == "__main__":
    unittest.main()

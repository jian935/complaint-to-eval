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


def load_labels() -> list[dict]:
    rows = []
    for line in LABELS.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


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


if __name__ == "__main__":
    unittest.main()

"""Structure locks for the defect hold-out artefacts (CI-safe, no raw corpus).

Seven model-labelled disjoint splits exist (a–g); set h is the separate
v2 round (one workbook of unconfirmed provenance) and has no model label file
by design. These tests
guarantee:
  * every label file is well-formed and uses known modes;
  * every annotator in those files is ``model`` — none of them was labelled by a
    human, and the human rounds live in separate artefacts;
  * each label file matches its partition file exactly;
  * no two splits overlap, so a "clean" validation set really is clean.

If a new set is added, add it to ``SETS`` and the invariants apply automatically.
"""

from __future__ import annotations

import json
import sys
import unittest
from itertools import combinations
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from complaint_to_eval.defects import DEFECT_MODES  # noqa: E402

BASE = ROOT / "eval/defect_holdout"

#: set name -> (labels file, partitions file). Order is the drawing order.
SETS: dict[str, tuple[Path, Path]] = {
    "a": (BASE / "labels_holdout.jsonl", BASE / "partitions.json"),
    "b": (BASE / "labels_holdout_b.jsonl", BASE / "partitions_b.json"),
    "c": (BASE / "labels_holdout_c.jsonl", BASE / "partitions_c.json"),
    "d": (BASE / "labels_holdout_d.jsonl", BASE / "partitions_d.json"),
    "e": (BASE / "labels_holdout_e.jsonl", BASE / "partitions_e.json"),
    "f": (BASE / "labels_holdout_f.jsonl", BASE / "partitions_f.json"),
    "g": (BASE / "labels_holdout_g.jsonl", BASE / "partitions_g.json"),
}


def load_rows(path: Path) -> list[dict]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def label_ids(name: str) -> set[str]:
    return {r["record_id"] for r in load_rows(SETS[name][0])}


class HoldoutLabelsTests(unittest.TestCase):
    def test_every_set_is_present(self):
        for name, (labels, partitions) in SETS.items():
            self.assertTrue(labels.exists(), f"set {name}: missing {labels.name}")
            self.assertTrue(partitions.exists(), f"set {name}: missing {partitions.name}")

    def test_labels_parse_and_fields(self):
        for name, (labels, _) in SETS.items():
            rows = load_rows(labels)
            self.assertGreater(len(rows), 0, f"set {name} is empty")
            for row in rows:
                self.assertTrue(row.get("record_id"), f"set {name}: empty record_id")
                self.assertIsInstance(row.get("modes"), list)
                self.assertTrue(row.get("note"), f"set {name}: {row.get('record_id')} has no note")

    def test_modes_are_known(self):
        for name, (labels, _) in SETS.items():
            for row in load_rows(labels):
                for mode in row["modes"]:
                    self.assertIn(mode, DEFECT_MODES, f"set {name}: {row['record_id']} bad mode {mode}")

    def test_labels_are_never_human(self):
        # Honesty lock: no human annotated these. Never let a file claim one.
        for name, (labels, _) in SETS.items():
            for row in load_rows(labels):
                self.assertEqual(
                    "model", row["annotator"],
                    f"set {name}: {row['record_id']} annotator must be 'model'",
                )

    def test_no_duplicate_records_within_a_set(self):
        for name, (labels, _) in SETS.items():
            ids = [r["record_id"] for r in load_rows(labels)]
            self.assertEqual(len(ids), len(set(ids)), f"set {name} has duplicates")

    def test_labels_match_partition_files(self):
        for name, (labels, partitions) in SETS.items():
            parts = json.loads(partitions.read_text(encoding="utf-8"))
            partition_ids = {i for ids in parts["holdout"].values() for i in ids}
            self.assertEqual(partition_ids, label_ids(name), f"set {name}: labels != partitions")

    def test_all_sets_are_pairwise_disjoint(self):
        # A set that overlaps an earlier one was not a clean validation.
        for left, right in combinations(SETS, 2):
            overlap = label_ids(left) & label_ids(right)
            self.assertEqual(set(), overlap, f"sets {left} and {right} share {sorted(overlap)}")

    def test_h_partition_is_disjoint_from_every_labelled_split(self):
        # The v2 human round must be blind to all earlier model-labelled splits.
        parts = json.loads((BASE / "partitions_h.json").read_text(encoding="utf-8"))
        h_ids = {i for ids in parts["holdout"].values() for i in ids}
        self.assertEqual(40, len(h_ids))
        for name in SETS:
            self.assertEqual(
                set(), h_ids & label_ids(name),
                f"set h overlaps {name}: {sorted(h_ids & label_ids(name))}",
            )

    def test_h_has_no_model_labels(self):
        self.assertFalse((BASE / "labels_holdout_h.jsonl").exists())


if __name__ == "__main__":
    unittest.main()

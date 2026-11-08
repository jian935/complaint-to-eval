import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from complaint_to_eval.taxonomy import (  # noqa: E402
    FAILURE_MODES,
    RULES,
    find_hits,
    modes,
    validate_taxonomy,
)


class TestTaxonomy(unittest.TestCase):
    def test_invariants_hold(self):
        self.assertEqual([], validate_taxonomy())

    def test_modes_and_rules_match(self):
        self.assertEqual(set(FAILURE_MODES), set(modes()))
        self.assertEqual(len(FAILURE_MODES), len(RULES))

    def test_negation_cancels_a_hit(self):
        hits = find_hits("没有编造数据，一切都正常。")
        self.assertNotIn("wrong_fact", [h.mode for h in hits])

    def test_negation_does_not_leak_into_the_next_clause(self):
        hits = find_hits("没有编造数据，但工具调用失败了，重试三次还是报错。")
        found = {h.mode for h in hits}
        self.assertNotIn("wrong_fact", found)
        self.assertIn("tool_misuse", found)

    def test_english_negation(self):
        hits = find_hits("There was no hallucinated number in the answer.")
        self.assertNotIn("wrong_fact", [h.mode for h in hits])

    def test_generic_phrase_needs_context(self):
        self.assertEqual([], find_hits("这个数字挺好看的。"))
        hits = find_hits("回答里这个数字写错了。")
        self.assertIn("wrong_fact", [h.mode for h in hits])

    def test_english_signals_have_no_word_boundaries(self):
        hits = find_hits("The report gave ahallucinated numberand moved on.")
        self.assertIn("wrong_fact", [h.mode for h in hits])

    def test_one_hit_per_mode_per_clause(self):
        hits = find_hits("死循环，无限重试，反复调用，token 烧完也没结果。")
        self.assertEqual(1, len([h for h in hits if h.mode == "loop_cost"]))

    def test_context_list_never_contains_its_own_weak_phrase(self):
        for rule in RULES:
            for weak in rule.weak:
                for context in rule.context:
                    self.assertNotIn(weak, context, f"{rule.mode}: {weak} / {context}")
                    self.assertNotIn(context, weak, f"{rule.mode}: {weak} / {context}")

    def test_evidence_offsets_point_at_the_matched_phrase(self):
        text = "回答里直接编造数据，说转化率是 87%。"
        hit = find_hits(text)[0]
        self.assertEqual("编造数据", text[hit.start:hit.end])


if __name__ == "__main__":
    unittest.main()

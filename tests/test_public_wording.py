"""Locks on the project's public claims.

The v0.1 landing page said findings came with "a minimal reproducible input
for every finding". They do not: `input` is a quote, not a repro script. That
claim was fixed, but nothing stopped it (or the equally wrong
"regression-test candidates") from reappearing in `pip show`, the skill
description or `cte --help`. These tests are that stop.

Later locks cover three more ways a published page can drift out of date:
stale status sentences about human labels, the unverified Chinese signals,
and the fact that every measurement comes from English issue trackers.

`CHANGELOG.md` is deliberately NOT scanned: it is allowed to quote the old
claim when recording that it was wrong.
"""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

#: Phrases that assert a capability this project does not have.
BANNED = (
    "regression-test candidate",
    "regression candidate",
    "minimal reproducible input",
    "reproducible input for every",
    "回归用例候选",
    "回归测试用例",
    "最小可复现输入",
)

#: Sentences that were true in v0.1 and became false once human readers
#: labelled splits G and H. They must not return to any user-visible surface.
STALE_STATUS_CLAIMS = (
    "no precision / recall number is claimed anywhere",
    "there is no human-labelled set yet",
    "the only precision/recall figures that exist are in",
)

#: Every surface a user sees before reading the code. `taxonomy.py` and
#: `pipeline.py` were added after an audit found an outdated status sentence
#: in the former's docstring that none of the earlier locks covered.
SURFACES = (
    "README.md",
    "README.zh-CN.md",
    "SKILL.md",
    "pyproject.toml",
    "CONTRIBUTING.md",
    "DEFECT_TAXONOMY.md",
    "complaint_to_eval/__init__.py",
    "complaint_to_eval/cli.py",
    "complaint_to_eval/defects.py",
    "complaint_to_eval/cooccurrence.py",
    "complaint_to_eval/taxonomy.py",
    "complaint_to_eval/pipeline.py",
)

#: The whole evaluation corpus is English. A Chinese signal list exists in
#: `defects.py`, but it has never been measured. Every entry point must say so
#: in the same machine-checkable words.
ZH_BOUNDARY_MARKER = "Chinese signals are UNVERIFIED"
ZH_BOUNDARY_SURFACES = (
    "README.md",
    "README.zh-CN.md",
    "DEFECT_TAXONOMY.md",
    "SKILL.md",
)


class PublicClaimTests(unittest.TestCase):
    def test_no_surface_promises_a_runnable_suite(self):
        for name in SURFACES:
            text = (ROOT / name).read_text(encoding="utf-8").lower()
            for phrase in BANNED:
                self.assertNotIn(
                    phrase, text,
                    f"{name} still asserts '{phrase}'. Findings are evidence-"
                    f"backed candidate labels, not runnable cases.",
                )

    def test_no_stale_status_claim_on_any_surface(self):
        for name in SURFACES:
            text = (ROOT / name).read_text(encoding="utf-8").lower()
            for phrase in STALE_STATUS_CLAIMS:
                self.assertNotIn(
                    phrase, text,
                    f"{name} still says '{phrase}'. Splits G (four readers) "
                    f"and H (one confirmed reader) are human-labelled.",
                )

    def test_chinese_signal_boundary_is_visible_everywhere(self):
        for name in ZH_BOUNDARY_SURFACES:
            text = (ROOT / name).read_text(encoding="utf-8")
            self.assertIn(
                ZH_BOUNDARY_MARKER, text,
                f"{name} must state that the Chinese signals were never "
                f"validated; every evaluation split is English.",
            )

    def test_front_page_states_the_corpus_scope(self):
        en = (ROOT / "README.md").read_text(encoding="utf-8")
        zh = (ROOT / "README.zh-CN.md").read_text(encoding="utf-8")
        self.assertIn("English-language issue trackers", en)
        self.assertIn("英文 issue 追踪器", zh)
        for text in (en, zh):
            self.assertIn("aider", text)
            self.assertIn("dify", text)

    def test_corpus_card_and_issue_templates_are_present(self):
        card = ROOT / "eval" / "DATA_CARD.md"
        self.assertTrue(card.is_file(), "the corpus/reproduction card is missing")
        card_text = card.read_text(encoding="utf-8")
        self.assertIn("Apache-2.0", card_text)
        self.assertIn("gitignored", card_text)
        for name in ("counter-example.yml", "new-corpus.yml"):
            template = ROOT / ".github" / "ISSUE_TEMPLATE" / name
            self.assertTrue(template.is_file(), f"missing issue template {name}")
            self.assertIn(
                "licen", template.read_text(encoding="utf-8").lower(),
                f"{name} must ask about the source licence",
            )

    def test_front_page_still_carries_its_self_refutation(self):
        en = (ROOT / "README.md").read_text(encoding="utf-8")
        zh = (ROOT / "README.zh-CN.md").read_text(encoding="utf-8")
        # The honesty table must exist and must keep the two hardest rows.
        self.assertIn("| Claim | Status |", en)
        self.assertIn("| 声称 | 实际状态 |", zh)
        for text in (en, zh):
            self.assertIn("0.71", text)
            self.assertIn("0.23", text)
        self.assertIn("accepted_cases", en)
        self.assertIn("accepted_cases", zh)

    def test_skill_description_keeps_its_scope_limits(self):
        skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        head = skill.split("---")[1]
        self.assertIn("name: complaint-to-eval", head)
        self.assertIn("description:", head)
        self.assertIn("UNREVIEWED", head)
        self.assertIn("Does NOT run evals", head)
        self.assertIn("never reports a fix rate", head)


class MetadataConsistencyTests(unittest.TestCase):
    def test_pyproject_version_matches_the_package(self):
        from complaint_to_eval import __version__
        toml = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        m = re.search(r'^version\s*=\s*"([^"]+)"', toml, re.M)
        self.assertIsNotNone(m)
        self.assertEqual(__version__, m.group(1),
                         "pyproject version and __version__ drifted")

    def test_cli_help_does_not_overclaim(self):
        from complaint_to_eval.cli import build_parser
        desc = build_parser().description.lower()
        for phrase in BANNED:
            self.assertNotIn(phrase, desc)
        self.assertIn("not a runnable regression suite", desc)

    def test_taxonomy_versions_are_not_accidentally_bumped(self):
        # DEFECT_VERSION describes the taxonomy, not the package. Bumping the
        # package must not silently relabel every published number.
        from complaint_to_eval.defects import DEFECT_VERSION
        self.assertEqual("0.1.0-draft", DEFECT_VERSION)


if __name__ == "__main__":
    unittest.main()

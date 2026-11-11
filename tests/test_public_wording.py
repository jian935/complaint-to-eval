"""Locks on the project's public claims.

The v0.1 landing page said findings came with "a minimal reproducible input
for every finding". They do not: `input` is a quote, not a repro script. That
claim was fixed, but nothing stopped it (or the equally wrong
"regression-test candidates") from reappearing in `pip show`, the skill
description or `cte --help`. These tests are that stop.

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

#: Every surface a user sees before reading the code.
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

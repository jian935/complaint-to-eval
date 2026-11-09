"""Deterministic DEFECT-REPORT taxonomy for AI-tool issue trackers.

Pivot (2026-11-10). Measured across 191 real GitHub issues (aider 136, dify 47,
lobe 8): the eight LLM-behaviour modes in ``taxonomy.py`` fire essentially never
on that text — only 1 of 81 strong signals ever appeared, because those issues
are *software defect reports* (crashes, config, UI, i18n, data integrity,
security), not natural-language complaints about model behaviour.

This module classifies the text that actually occurs in issue trackers, so the
pipeline can turn real defect reports into regression-test candidates.

Discipline carried over unchanged (see ANNOTATION_GUIDE.md):
* No bare nouns; only specific multi-word signals.
* A negator immediately before the hit cancels it ("no crash" is not a crash).
* English is matched as a substring, deliberately without word boundaries.
* Evidence offsets refer to REDACTED text.

Status: DRAFT ``defect-0.1.0-draft``. The signals were read off aider/dify
issues and are measured on the same corpus (in-sample). They are NOT validated
on held-out data and claim NO precision/recall. Sorting this out properly needs
a labelled dev/hold-out split, which is the next step.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .redact import redact

DEFECT_VERSION = "0.1.0-draft"

DEFECT_MODES: dict[str, str] = {
    "crash_or_error": "Uncaught exception, traceback, crash, segfault",
    "data_integrity": "Lost, dropped, truncated, corrupted, or miscounted data",
    "config_or_env": "Env var / config ignored, not applied, or install broken",
    "ui_or_ux": "Layout, focus, alignment, hover, clipping in the interface",
    "i18n_or_locale": "Missing translations, wrong locale, fallback to English",
    "security": "Traversal, unauthorized action, bypass, arbitrary execution",
    "performance": "Slow, timeout, hang, leak, latency",
    "regression": "Worked before, stopped working, regressed since a version",
    "docs": "Missing documentation, README gap, undocumented setup step",
}


@dataclass(frozen=True)
class DefectRule:
    mode: str
    strong: tuple[str, ...]


RULES: tuple[DefectRule, ...] = (
    DefectRule(
        "crash_or_error",
        strong=(
            "uncaught", "traceback (most recent call last)", "segfault",
            "crashes", "crash when", "crash on", "throws a", "throw an",
            "typeerror", "importerror", "valueerror", "modulenotfounderror",
            "attributeerror", "isadirectoryerror", "notimplementederror",
            "unicodeencodeerror", "nameerror", "indexerror", "keyerror",
            "崩溃", "报错", "抛出异常", "闪退",
        ),
    ),
    DefectRule(
        "data_integrity",
        strong=(
            "truncat", "corrupt", "silently wraps", "silently truncat",
            "loses its", "lost data", "data loss", "disappear",
            "wrong count", "wrong page count", "drops the",
            "丢失", "截断", "错乱", "数据丢失", "数据损坏",
        ),
    ),
    DefectRule(
        "config_or_env",
        strong=(
            "env var", "environment variable", "not applied", "not honored",
            "not respected", "config not", "configuration is ignored",
            "环境变量", "配置不生效", "配置被忽略", "不生效",
        ),
    ),
    DefectRule(
        "ui_or_ux",
        strong=(
            "sidebar", "hover", "layout", "clips", "clipped", "misalign",
            "chevron", "tooltip", "drops keyboard focus", "covered by main content",
            "界面", "布局", "侧边栏", "样式", "遮挡",
        ),
    ),
    DefectRule(
        "i18n_or_locale",
        strong=(
            "locale", "translation", "zh-cn", "zh-hant", "i18n",
            "fall back to english", "falls back to english", "missing keys",
            "翻译", "多语言", "语言包", "繁中",
        ),
    ),
    DefectRule(
        "security",
        strong=(
            "security", "path traversal", "outside the repo",
            "outside the repository", "unauthorized", "bypass",
            "without confirmation", "arbitrary command", "command execution",
            "安全", "越权", "命令执行", "路径穿越", "未经确认",
        ),
    ),
    DefectRule(
        "performance",
        strong=(
            "slow", "timeout", "timed out", "hang", "hangs", "memory leak",
            "latency", "performance",
            "超时", "卡顿", "性能", "内存泄漏",
        ),
    ),
    DefectRule(
        "regression",
        strong=(
            "a regression", "regression bug", "caused a regression",
            "introduced a regression", "regressed", "used to work",
            "worked before", "since version", "stopped working",
            "no longer works",
            "回归缺陷", "之前正常", "以前的版本",
        ),
    ),
    DefectRule(
        "docs",
        strong=(
            "missing documentation", "no documentation", "documentation is missing",
            "update the documentation", "update the readme", "readme is missing",
            "readme lacks", "missing from the readme", "missing step",
            "undocumented",
            "文档缺失", "缺少文档", "说明缺失",
        ),
    ),
)

NEGATORS: tuple[str, ...] = (
    "没有", "并未", "未出现", "不存在", "不算", "不是", "无", "避免了",
    "已修复", "已解决", "修复了", "no", "not", "without", "never",
    "fixed", "resolved", "didn't", "doesn't",
)
_NEG_RE = re.compile(
    r"(?:" + "|".join(re.escape(n) for n in NEGATORS) + r")[\s，,、的]{0,3}$",
    re.IGNORECASE,
)
_CLAUSE_SPLIT = re.compile(r"[。！？；;\n]+|(?<=[.!?])\s+")
_NEG_WINDOW = 12


@dataclass(frozen=True)
class DefectHit:
    mode: str
    phrase: str
    start: int
    end: int
    quote: str


def _clauses(text: str):
    start = 0
    for match in _CLAUSE_SPLIT.finditer(text):
        segment = text[start:match.start()]
        if segment.strip():
            yield start, segment
        start = match.end()
    tail = text[start:]
    if tail.strip():
        yield start, tail


def _is_negated(clause: str, pos: int) -> bool:
    prefix = clause[max(0, pos - _NEG_WINDOW):pos]
    return bool(_NEG_RE.search(prefix))


def _ascii_only(text: str) -> bool:
    return all(ord(c) < 128 for c in text)


def _find_signal(lowered: str, phrase: str) -> int:
    """Position of ``phrase`` in ``lowered``, or -1.

    Latin signals match on whole-word boundaries, so 'hang' does not fire on
    'changes'. CJK signals match as plain substrings (no word delimiters).
    This deliberately differs from the LLM-behaviour taxonomy in taxonomy.py,
    whose feedback text concatenates words; defect reports are well-formed.
    """
    p = phrase.lower()
    if _ascii_only(p):
        m = re.search(r"(?<![a-z0-9])" + re.escape(p) + r"(?![a-z0-9])", lowered)
        return m.start() if m else -1
    return lowered.find(p)


def find_defect_hits(text: str) -> list[DefectHit]:
    """Return at most one hit per (defect mode, clause), ordered by offset."""
    hits: list[DefectHit] = []
    for base, clause in _clauses(text):
        lowered = clause.lower()
        for rule in RULES:
            for phrase in rule.strong:
                pos = _find_signal(lowered, phrase)
                if pos == -1 or _is_negated(clause, pos):
                    continue
                hits.append(
                    DefectHit(rule.mode, phrase, base + pos, base + pos + len(phrase), clause)
                )
                break  # one hit per mode per clause
    return sorted(hits, key=lambda h: (h.start, h.mode))


def modes() -> tuple[str, ...]:
    return tuple(DEFECT_MODES)


def validate_defect_taxonomy() -> list[str]:
    problems: list[str] = []
    seen: set[str] = set()
    for rule in RULES:
        if rule.mode not in DEFECT_MODES:
            problems.append(f"unknown mode: {rule.mode}")
        if rule.mode in seen:
            problems.append(f"duplicate rule: {rule.mode}")
        seen.add(rule.mode)
        if not rule.strong:
            problems.append(f"{rule.mode}: no strong signals")
        for phrase in rule.strong:
            ascii_only = all(ord(c) < 128 for c in phrase)
            min_len = 3 if ascii_only else 2
            if len(phrase) < min_len:
                problems.append(f"{rule.mode}: signal too short: {phrase!r}")
    for mode in DEFECT_MODES:
        if mode not in seen:
            problems.append(f"mode has no rule: {mode}")
    return problems


def analyze_defects(
    records,
    *,
    dataset_label: str = "unnamed",
    synthetic: bool | None = None,
) -> dict:
    """Classify records with the defect taxonomy. Same output shape as analyze()."""
    from collections import Counter

    findings: list[dict] = []
    cases: list[dict] = []
    counts: Counter[str] = Counter({mode: 0 for mode in modes()})
    redactions: Counter[str] = Counter()
    seen_record_mode: set[tuple[str, str]] = set()

    for record in records:
        clean_text, red = redact(record.text)
        for kind, n in red.items():
            redactions[kind] += n
        for hit in find_defect_hits(clean_text):
            key = (record.id, hit.mode)
            if key in seen_record_mode:
                continue  # one defect candidate per (record, mode)
            seen_record_mode.add(key)
            fid = f"d-{len(findings) + 1:04d}"
            cid = f"dcte-{len(cases) + 1:04d}"
            findings.append(
                {
                    "id": fid,
                    "record_id": record.id,
                    "source": record.source,
                    "product": record.product,
                    "defect_mode": hit.mode,
                    "matched_phrase": hit.phrase,
                    "evidence": {
                        "quote": hit.quote,
                        "start": hit.start,
                        "end": hit.end,
                        "offsets_refer_to": "redacted text",
                    },
                    "status": "candidate",
                }
            )
            counts[hit.mode] += 1
            cases.append(
                {
                    "id": cid,
                    "finding_id": fid,
                    "failure_mode": hit.mode,
                    "input": hit.quote,
                    "assertion": {
                        "type": "must_not_reproduce_defect",
                        "value": hit.mode,
                        "description": DEFECT_MODES[hit.mode],
                    },
                    "evidence_record_id": record.id,
                    "status": "candidate",
                    "human_review_required": True,
                    "review": None,
                }
            )

    if synthetic is True:
        provenance = "synthetic"
    elif synthetic is False:
        provenance = "declared-real"
    else:
        provenance = "unspecified"

    classified = {f["record_id"] for f in findings}
    return {
        "schema_version": "0.2",
        "tool": "complaint-to-eval/defects",
        "taxonomy_version": DEFECT_VERSION,
        "dataset": {
            "label": dataset_label,
            "provenance": provenance,
            "records": len(records),
        },
        "honesty": {
            "candidate_cases": len(cases),
            "accepted_cases": 0,
            "classified_records": len(classified),
            "unclassified_records": len(records) - len(classified),
            "note": "Defect candidates from deterministic rules, in-sample on the "
                    "corpus the signals were read from. Not validated; no "
                    "precision/recall is claimed. Human review required.",
        },
        "counts": dict(counts),
        "redactions": dict(redactions),
        "findings": findings,
        "cases": cases,
    }


def to_defect_markdown(report: dict) -> str:
    h = report["honesty"]
    lines = [
        "# defect-report classification",
        "",
        f"- Dataset: `{report['dataset']['label']}` ({report['dataset']['records']} records)",
        f"- Provenance: **{report['dataset']['provenance']}**",
        f"- Taxonomy: `{report['taxonomy_version']}` (DRAFT, unvalidated)",
        f"- Classified records: **{h['classified_records']}**",
        f"- Unclassified records: **{h['unclassified_records']}**",
        f"- Candidate cases: **{h['candidate_cases']}**  ·  accepted: **0**",
        "",
        "> In-sample on the corpus the signals were read from. No precision or",
        "> recall is claimed; human review is required. See DEFECT_TAXONOMY.md.",
        "",
        "## Per-mode counts",
        "",
        "| Mode | Candidates | Meaning |",
        "| --- | ---: | --- |",
    ]
    for mode, meaning in DEFECT_MODES.items():
        lines.append(f"| `{mode}` | {report['counts'].get(mode, 0)} | {meaning} |")
    lines.append("")
    lines.append("## Evidence samples")
    lines.append("")
    for f in report["findings"][:15]:
        quote = f["evidence"]["quote"].replace("\n", " ")
        lines.append(f"- **{f['defect_mode']}** · `{f['record_id']}` · `{f['matched_phrase']}` — {quote}")
    lines.append("")
    return "\n".join(lines)

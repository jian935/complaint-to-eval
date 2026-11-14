"""Deterministic failure-mode taxonomy for user complaints about AI agents.

NOTE: there are TWO taxonomies in this package and they are not interchangeable.
This file is the v0.1 **8 LLM-behaviour modes** for free-form feedback. Issue
tracker / defect reports use the separate **10 defect modes** in
``complaint_to_eval/defects.py`` documented in ``DEFECT_TAXONOMY.md``. English
signals here deliberately have NO word boundary (feedback concatenates words);
the defect taxonomy deliberately HAS one. Real issue corpora gave this taxonomy
near-zero recall, which is why the project moved to defects: see
``eval/defect_holdout/README.md``.

Design rules carried over from the author's earlier keyword work (career-loop),
re-targeted from job descriptions to user feedback:

* No bare nouns. A bare "数字" / "number" matches almost any sentence, so only
  compound phrases are used as signals.
* Generic phrases need a context companion on the SAME clause
  (CONTEXT_REQUIRED). Constraining a weak phrase beats replacing it with a
  fancier one: swapping the phrase loses precision, constraining it gains it.
* A context list must not contain one of its own weak phrases (locked by a test).
* Negation scope cancels a hit: "没有编造数据" is NOT a wrong_fact finding,
  and a negation in an earlier clause must not leak into the next one.
* English signals are matched as substrings, deliberately WITHOUT word
  boundaries: real feedback concatenates words ("hallucinatednumber").
* When human labels disagree with this file, fix the labels, not this file.
  The taxonomy is a measuring instrument; it may not define its own target.

v0.1 is a DRAFT, and **this taxonomy** still has no human-labelled set: the
human readers in this repository labelled the separate 10-mode defect path in
``complaint_to_eval/defects.py``, not these eight behaviour modes. The
precision / recall figures published in ``eval/defect_holdout/`` describe that
defect path only, mostly against model-generated labels; none validates this
file and none is a claim about human accuracy. Chinese signals are UNVERIFIED:
every evaluation split is English. See eval/ANNOTATION_GUIDE.md.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

TAXONOMY_VERSION = "0.1.0-draft"

FAILURE_MODES: dict[str, str] = {
    "wrong_fact": "Fabricated or wrong facts, numbers, sources",
    "tool_misuse": "Wrong tool, bad arguments, duplicate or failed calls",
    "instruction_drift": "Ignored instructions, format or language constraints",
    "context_loss": "Forgot earlier turns, contradicted itself, asked again",
    "boundary_gap": "Acted without approval, failed to refuse, leaked data",
    "incomplete_task": "Stopped halfway, skipped steps, partial answer",
    "loop_cost": "Infinite retry, repeated calls, latency or token burn",
    "ux_friction": "Cannot interrupt, no undo, no progress, frozen UI",
}


@dataclass(frozen=True)
class Rule:
    mode: str
    strong: tuple[str, ...] = ()
    weak: tuple[str, ...] = ()
    context: tuple[str, ...] = ()


RULES: tuple[Rule, ...] = (
    Rule(
        "wrong_fact",
        strong=(
            "编造数据", "虚构引用", "数字对不上", "瞎编的数据", "捏造事实", "幻觉数字",
            "伪造来源", "数据算错", "hallucinated number", "made-up citation",
            "fabricated source", "invented statistic", "wrong number", "fake citation",
        ),
        weak=("这个数字", "数据来源", "引用链接", "统计结果"),
        context=("回答里", "输出中", "生成的报告", "结果里", "写错",
                 "answer", "response", "output", "report"),
    ),
    Rule(
        "tool_misuse",
        strong=(
            "调错工具", "工具调用失败", "重复调用工具", "参数传错", "调用了不存在的工具",
            "tool call failed", "wrong tool", "duplicate tool call",
            "invalid arguments", "called nonexistent tool",
        ),
        weak=("工具调用", "接口调用", "函数调用"),
        context=("失败了", "报错", "卡住", "重试", "agent", "助手", "执行",
                 "failed", "error", "retry"),
    ),
    Rule(
        "instruction_drift",
        strong=(
            "没按要求输出", "不听指令", "格式不符合要求", "擅自改了需求", "忽略了我的要求",
            "ignored my instruction", "wrong output format",
            "did not follow the prompt", "ignored constraints",
        ),
        weak=("输出格式", "要求格式", "指定语言"),
        context=("提示词", "指令", "说明了", "写明了",
                 "prompt", "instruction", "specified", "asked"),
    ),
    Rule(
        "context_loss",
        strong=(
            "忘了前面说的", "上下文丢失", "跨轮矛盾", "记不住上一轮", "重复问我",
            "forgot earlier context", "lost context",
            "contradicts previous turn", "asked me again",
        ),
        weak=("上一轮", "前面的内容", "历史对话"),
        context=("忘了", "不记得", "矛盾", "重复",
                 "forgot", "lost", "again", "contradict"),
    ),
    Rule(
        "boundary_gap",
        strong=(
            "不该答却答了", "越权操作", "未经确认就执行", "没有拒答", "泄露了隐私",
            "should have refused", "acted without approval",
            "executed without confirmation", "leaked private data",
        ),
        weak=("权限", "确认步骤", "敏感信息"),
        context=("跳过", "绕过", "未经", "擅自",
                 "refused", "approval", "confirmation", "consent"),
    ),
    Rule(
        "incomplete_task",
        strong=(
            "只做了一半", "漏了步骤", "没有做完", "半截就停", "任务未完成",
            "stopped halfway", "incomplete output", "missed a step",
            "did not finish", "partial answer",
        ),
        weak=("执行步骤", "待办清单", "任务列表"),
        context=("漏", "少", "停", "没做完",
                 "incomplete", "missing", "stopped", "truncated"),
    ),
    Rule(
        "loop_cost",
        strong=(
            "死循环", "无限重试", "反复调用", "token 烧完", "卡了很久",
            "infinite loop", "endless retry", "burned tokens",
            "kept repeating", "very slow response",
        ),
        weak=("响应慢", "费用高", "耗时长"),
        context=("agent", "助手", "运行", "调用",
                 "response", "latency", "cost", "run"),
    ),
    Rule(
        "ux_friction",
        strong=(
            "打断不了", "无法撤销", "没有进度提示", "界面卡死", "不能中断",
            "cannot interrupt", "no undo", "no progress indicator",
            "frozen interface", "can't stop it",
        ),
        weak=("交互体验", "操作流程", "界面反馈"),
        context=("差", "难受", "卡", "慢", "烦",
                 "broken", "annoying", "clunky", "unusable"),
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
class Hit:
    mode: str
    phrase: str
    start: int
    end: int
    quote: str
    strength: str


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
    """Only a negator immediately BEFORE the hit cancels it.

    Checking the whole prefix would let "没有编造数据，但工具调用失败" wrongly
    cancel the tool_misuse hit in the following clause.
    """
    prefix = clause[max(0, pos - _NEG_WINDOW):pos]
    return bool(_NEG_RE.search(prefix))


def find_hits(text: str) -> list[Hit]:
    """Return at most one hit per (failure mode, clause), ordered by offset."""
    hits: list[Hit] = []
    for base, clause in _clauses(text):
        lowered = clause.lower()
        found: dict[str, Hit] = {}
        for rule in RULES:
            for phrase in rule.strong:
                pos = lowered.find(phrase.lower())
                if pos == -1 or _is_negated(clause, pos):
                    continue
                found[rule.mode] = Hit(
                    rule.mode, phrase, base + pos, base + pos + len(phrase),
                    clause, "strong",
                )
                break
            if rule.mode in found or not rule.weak:
                continue
            if not any(word.lower() in lowered for word in rule.context):
                continue
            for phrase in rule.weak:
                pos = lowered.find(phrase.lower())
                if pos == -1 or _is_negated(clause, pos):
                    continue
                found[rule.mode] = Hit(
                    rule.mode, phrase, base + pos, base + pos + len(phrase),
                    clause, "weak",
                )
                break
        hits.extend(found.values())
    return sorted(hits, key=lambda hit: (hit.start, hit.mode))


def modes() -> tuple[str, ...]:
    return tuple(FAILURE_MODES)


def validate_taxonomy() -> list[str]:
    """Return a list of invariant violations; empty means healthy."""
    problems: list[str] = []
    seen: set[str] = set()
    for rule in RULES:
        if rule.mode not in FAILURE_MODES:
            problems.append(f"unknown mode: {rule.mode}")
        if rule.mode in seen:
            problems.append(f"duplicate rule: {rule.mode}")
        seen.add(rule.mode)
        if not rule.strong:
            problems.append(f"{rule.mode}: no strong signals")
        if rule.weak and not rule.context:
            problems.append(f"{rule.mode}: weak signals need a context list")
        for weak in rule.weak:
            for context in rule.context:
                if weak in context or context in weak:
                    problems.append(
                        f"{rule.mode}: context '{context}' overlaps weak '{weak}'"
                    )
    for mode in FAILURE_MODES:
        if mode not in seen:
            problems.append(f"mode has no rule: {mode}")
    return problems

"""EXPERIMENTAL: a topic+fault co-occurrence probe for ``data_integrity``.

This module is deliberately NOT wired into ``cte defects``. The v0.1 phrase
list is at a plateau (four rounds, mode-level precision 0.71-0.77) and one
confirmed human reader on split H marked ten ``data_integrity`` rows that the
phrase list could not express: they all say "it ran, but the content is wrong".
See ``eval/defect_holdout/cooccurrence_design.md`` for the nine misses.

The change in kind: a **clause** is scored, not a word. A candidate is emitted
only when a data-bearing topic word and a fault expression occur in the same
clause. Neither list may fire on its own.

Two hard rules that come straight out of the H diagnosis:

* absence wording (``without restoring``, ``does not send``, ``returns
  nothing``) is a FAULT, not a negation. The v0.1 engine treats ``without``
  and ``doesn't`` as negators and deletes exactly those clauses.
* issue-template boilerplate ("I have searched for existing issues") is
  excluded; it contains both nouns and negation-shaped words and would
  otherwise fabricate hits.

Scope limits, stated up front: this is a SINGLE-MODE probe, not a replacement
engine. It emits ``data_integrity`` only. Its vocabulary was frozen before
split I was drawn -- ``vocabulary_fingerprint()`` is recorded in
``eval/defect_holdout/partitions_i.json`` and locked by a test, so the
validation split cannot silently become a tuning set.

All labels used to score it are MODEL-generated unless explicitly stated.
Nothing here is human accuracy. ``accepted_cases`` stays 0.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass

from .defects import blank_code
from .redact import redact

COOCCURRENCE_VERSION = "0.1.0-experimental"
PROBE_MODE = "data_integrity"

# Nouns that can actually carry content. Deliberately excludes bare "data",
# "issue", "bug" and "keyword": they appear in every template sentence and
# would make the co-occurrence constraint vacuous.
TOPIC_WORDS: tuple[str, ...] = (
    "token", "image", "file", "text", "index", "timestamp", "credential",
    "attachment", "candidate", "chunk", "record", "row", "email", "content",
    "output", "count", "cache", "message", "metadata", "page", "link",
    "query", "segment", "document", "field", "entry", "paragraph", "block",
    "payload", "response", "value", "dataset", "embedding", "annotation",
)

# Fault expressions grouped by what went wrong with the content. Absence
# phrases are matched first and are NEVER passed through negation checking --
# their absence IS the reported defect.
FAULT_FAMILIES: dict[str, tuple[str, ...]] = {
    "absence": (
        "without restoring", "does not send", "do not send", "never sends",
        "returns nothing", "returns empty", "returns no ", "not included",
        "not sent", "not passed", "not restored", "does not include",
        "missing from", "fails to include", "never included",
    ),
    "missing": (
        "discard", "drop", "lose", "lost", "missing", "absent", "omit",
        "exclude", "strip", "remove", "swallow", "skip", "disappear",
        "vanish", "wipe",
    ),
    "duplicated": (
        "twice", "double", "duplicate", "second time", "two times",
        "more than once", "re-decod", "decoded twice",
    ),
    "wrong_value": (
        "offset", "wrong", "incorrect", "mismatch", "stale", "out of date",
        "corrupt", "garbled", "swap", "misinterpret", "treated as",
        "interpreted as", "instead of", "coerc",
    ),
    "truncated": (
        "truncat", "cut off", "partial", "incomplete", "shorten",
    ),
}

# Issue-template boilerplate. A clause containing any of these is skipped
# wholesale rather than trimmed, so offsets stay exact.
_BOILERPLATE_RE = re.compile(
    r"self checks|i have (?:read|searched|confirm)|i confirm|contributing guide|"
    r"language policy|i am using english|i would like to ask|"
    r"this is only for bug report|search for existing issues|"
    r"i believe this is a legitimate bug|dify version|aider version|"
    r"please fill|steps to reproduce|expected behavior|actual behavior",
    re.I,
)

# Negation check for POSITIVE faults only. Unlike defects.NEGATORS this does
# NOT include "without" / "doesn't" / "does not": those are faults here.
_NEG_BEFORE = re.compile(r"\b(?:no|not|never|fixed|resolved|avoided|prevented)\s+$", re.I)
_CLAUSE_SPLIT = re.compile(r"[。！？；;\n]+|(?<=[.!?])\s+")


def vocabulary_fingerprint() -> str:
    """Hash of the frozen vocabulary, used to prove split I was drawn later."""
    payload = json.dumps(
        {"topics": sorted(TOPIC_WORDS),
         "faults": {k: sorted(v) for k, v in sorted(FAULT_FAMILIES.items())},
         "version": COOCCURRENCE_VERSION},
        ensure_ascii=False, sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class CoHit:
    mode: str
    topic: str
    fault: str
    family: str
    start: int
    end: int
    quote: str


def _clauses(text: str):
    """Identical segmentation to defects._clauses (kept duplicated on purpose:
    this probe must not be able to change the v0.1 engine's behaviour)."""
    start = 0
    for match in _CLAUSE_SPLIT.finditer(text):
        segment = text[start:match.start()]
        if segment.strip():
            yield start, segment
        start = match.end()
    tail = text[start:]
    if tail.strip():
        yield start, tail


def _find_word(lowered: str, word: str) -> int:
    """Start-of-word position, or -1. Prefixes catch inflections."""
    m = re.search(r"(?<![a-z0-9])" + re.escape(word.lower()), lowered)
    return m.start() if m else -1


def find_cooccurrence_hits(text: str) -> list[CoHit]:
    """Return at most one ``data_integrity`` candidate per clause.

    Matching runs on ``blank_code(text)``; evidence quotes come from ``text``
    (blanking preserves length, so offsets stay exact).
    """
    hits: list[CoHit] = []
    masked = blank_code(text)
    for base, clause in _clauses(masked):
        if _BOILERPLATE_RE.search(clause):
            continue
        lowered = clause.lower()

        topics: list[tuple[int, str]] = []
        for word in TOPIC_WORDS:
            pos = _find_word(lowered, word)
            if pos != -1:
                topics.append((pos, word))
        if not topics:
            continue

        for family, words in FAULT_FAMILIES.items():
            fired = False
            for word in words:
                pos = _find_word(lowered, word)
                if pos == -1:
                    continue
                if family != "absence" and _NEG_BEFORE.search(
                    clause[max(0, pos - 12):pos]
                ):
                    continue
                # The co-occurrence window is the clause itself, but require
                # the topic and fault to be reasonably local (<= 100 chars)
                # so a long clause cannot pair unrelated statements.
                _, tpos, topic = min((abs(p - pos), p, w) for p, w in topics)
                if abs(tpos - pos) > 100:
                    continue
                hits.append(
                    CoHit(
                        mode=PROBE_MODE,
                        topic=topic,
                        fault=word,
                        family=family,
                        start=base + pos,
                        end=base + pos + len(word),
                        quote=text[base:base + len(clause)],
                    )
                )
                fired = True
                break
            if fired:
                break
    return sorted(hits, key=lambda h: h.start)


def analyze_cooccurrence(records, *, dataset_label: str = "unnamed",
                         synthetic: bool | None = None) -> dict:
    """Same output shape as ``analyze_defects`` so both engines can be diffed."""
    findings: list[dict] = []
    seen: set[str] = set()
    for record in records:
        clean_text, _ = redact(record.text)
        for hit in find_cooccurrence_hits(clean_text):
            if record.id in seen:
                continue  # one candidate per record
            seen.add(record.id)
            findings.append({
                "id": f"co-{len(findings) + 1:04d}",
                "record_id": record.id,
                "source": record.source,
                "product": record.product,
                "defect_mode": hit.mode,
                "matched_phrase": f"{hit.topic} + {hit.fault}",
                "evidence": {
                    "quote": hit.quote,
                    "start": hit.start,
                    "end": hit.end,
                    "offsets_refer_to": "redacted text",
                    "topic": hit.topic,
                    "fault": hit.fault,
                    "fault_family": hit.family,
                },
                "status": "candidate",
            })
    return {
        "schema_version": "0.2",
        "tool": "complaint-to-eval/cooccurrence",
        "taxonomy_version": COOCCURRENCE_VERSION,
        "engine_kind": "experimental_single_mode_probe",
        "vocabulary_fingerprint": vocabulary_fingerprint(),
        "dataset": {
            "label": dataset_label,
            "provenance": "synthetic" if synthetic is True else
                          "declared-real" if synthetic is False else "unspecified",
            "records": len(records),
        },
        "honesty": {
            "candidate_cases": len(findings),
            "accepted_cases": 0,
            "classified_records": len(findings),
            "note": "EXPERIMENTAL single-mode probe. Not wired into cte defects. "
                    "Scored only on split I (model labels, not human accuracy). "
                    "Split H is the DESIGN set and must never be quoted as a "
                    "validation result. See eval/defect_holdout/cooccurrence_design.md.",
        },
        "counts": {PROBE_MODE: len(findings)},
        "findings": findings,
    }

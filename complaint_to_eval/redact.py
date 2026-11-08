"""Redact personal data before any text is logged, quoted, or shipped.

Redaction runs BEFORE classification. Evidence quotes therefore contain
placeholders such as ``[EMAIL]``, never raw identifiers. Character offsets
reported downstream refer to the REDACTED text, and the report says so.

Deliberately over-redacts (an IPv4-looking version string becomes ``[IPV4]``).
Losing a harmless string is cheaper than publishing a real identifier.
"""

from __future__ import annotations

import re

# Order matters: URLs go first so an @ inside a URL is not replaced as an email.
_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("URL", re.compile(r"https?://[^\s，。；、）)\]}>]+", re.IGNORECASE)),
    ("EMAIL", re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")),
    ("PHONE_CN", re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")),
    ("ID_CN", re.compile(r"(?<!\d)\d{17}[\dXx](?!\d)")),
    ("HANDLE", re.compile(r"(?<![\w@])@[A-Za-z0-9_-]{2,30}")),
    ("IPV4", re.compile(r"(?<!\d)(?:\d{1,3}\.){3}\d{1,3}(?!\d)")),
)


def redact(text: str) -> tuple[str, dict[str, int]]:
    """Return (redacted_text, {kind: replacement_count})."""
    out = text
    counts: dict[str, int] = {}
    for kind, pattern in _PATTERNS:
        out, n = pattern.subn(f"[{kind}]", out)
        if n:
            counts[kind] = counts.get(kind, 0) + n
    return out, counts


def has_personal_data(text: str) -> bool:
    """True if any pattern still matches. Used by the release privacy check."""
    return any(pattern.search(text) for _, pattern in _PATTERNS)

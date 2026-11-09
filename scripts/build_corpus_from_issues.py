"""Build a redacted feedback corpus from a public repo's GitHub issues.

This is the *reproduction recipe*, not the corpus itself. It fetches issues,
drops pull requests, keeps non-empty bodies, redacts personal data, and writes
a ``.jsonl`` file that ``cte run`` consumes. The raw snapshot is written under
``.local/`` (gitignored); only the script, the source metadata, and aggregate
numbers are meant to be published.

Examples
--------
Latest issues (exploration):
    python scripts/build_corpus_from_issues.py --repo Aider-AI/aider --pages 2 \
        --out .local/corpus/aider.jsonl

Reproducible, pinned to exact issue numbers (what a published SOURCE.md does):
    python scripts/build_corpus_from_issues.py --repo Aider-AI/aider \
        --numbers eval/model_pass/issue_numbers.txt --out .local/corpus/aider_pinned.jsonl

Set GITHUB_TOKEN to lift the 60 req/hour anonymous limit.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from complaint_to_eval.redact import redact  # noqa: E402

API = "https://api.github.com"


def _get(url: str, token: str | None) -> list | dict:
    req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json",
                                               "User-Agent": "complaint-to-eval-corpus"})
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310 (trusted host)
        return json.loads(resp.read().decode("utf-8"))


def _item_to_row(item: dict, repo: str, min_chars: int) -> dict | None:
    if item.get("pull_request"):
        return None  # issues endpoint also returns PRs
    title = (item.get("title") or "").strip()
    body = (item.get("body") or "").strip()
    text = f"{title}. {body}".strip()
    if len(text) < min_chars:
        return None
    clean, _ = redact(text)
    return {
        "id": f"{repo.split('/')[-1]}-{item['number']}",
        "text": clean,
        "source": "github-issues",
        "product": repo.split("/")[-1],
        "issue_number": item["number"],
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True, help="owner/name, e.g. Aider-AI/aider")
    ap.add_argument("--out", required=True)
    ap.add_argument("--pages", type=int, default=2)
    ap.add_argument("--per-page", type=int, default=100)
    ap.add_argument("--min-chars", type=int, default=80)
    ap.add_argument("--numbers", help="file with one issue number per line (pinned mode)")
    ap.add_argument(
        "--from-json",
        help="read an already-fetched JSON array of issue objects instead of calling the API "
        "(useful behind a TLS-inspecting proxy that Python's CA bundle rejects)",
    )
    args = ap.parse_args()

    token = os.environ.get("GITHUB_TOKEN")
    repo = args.repo
    rows: list[dict] = []
    seen: set[int] = set()

    if args.from_json:
        items = json.loads(Path(args.from_json).read_text(encoding="utf-8"))
        if isinstance(items, dict):
            items = [items]
        for item in items:
            if item["number"] in seen:
                continue
            row = _item_to_row(item, repo, args.min_chars)
            if row:
                rows.append(row)
                seen.add(item["number"])
    elif args.numbers:
        nums = [int(x) for x in Path(args.numbers).read_text(encoding="utf-8").split() if x.strip().isdigit()]
        for n in nums:
            if n in seen:
                continue
            try:
                item = _get(f"{API}/repos/{repo}/issues/{n}", token)
            except urllib.error.HTTPError as exc:
                print(f"skip #{n}: HTTP {exc.code}", file=sys.stderr)
                continue
            row = _item_to_row(item, repo, args.min_chars)
            if row:
                rows.append(row)
                seen.add(n)
    else:
        for page in range(1, args.pages + 1):
            url = f"{API}/repos/{repo}/issues?state=all&per_page={args.per_page}&page={page}&sort=created&direction=desc"
            try:
                items = _get(url, token)
            except urllib.error.HTTPError as exc:
                print(f"page {page}: HTTP {exc.code} — stopping", file=sys.stderr)
                break
            if not items:
                break
            for item in items:
                if item["number"] in seen:
                    continue
                row = _item_to_row(item, repo, args.min_chars)
                if row:
                    rows.append(row)
                    seen.add(item["number"])

    out = Path(args.out)
    if not out.is_absolute():
        out = ROOT / out
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")

    print(f"repo={repo} kept={len(rows)} -> {out}")
    print("issue_numbers=" + ",".join(str(r["issue_number"]) for r in rows))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

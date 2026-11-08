"""Command line entry point. All output is UTF-8; console messages stay ASCII."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from . import __version__
from .diff import compare
from .exporters import to_json, to_markdown, to_promptfoo_candidates
from .pipeline import analyze, load_records
from .redact import has_personal_data
from .taxonomy import FAILURE_MODES, RULES, TAXONOMY_VERSION, validate_taxonomy

_DEMO = Path(__file__).with_name("demo.jsonl")
_VALID_DECISIONS = {"accepted", "rejected", "unsure"}
_DATA_SUFFIXES = {".jsonl", ".csv", ".json"}


def _write_report(report: dict, out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    files = {
        "report.json": to_json(report),
        "report.md": to_markdown(report),
        "promptfoo-candidates.json": json.dumps(
            to_promptfoo_candidates(report), ensure_ascii=False, indent=2
        ),
    }
    written: list[Path] = []
    for name, content in files.items():
        target = out_dir / name
        target.write_text(content, encoding="utf-8")
        written.append(target)
    return written


def _cmd_demo(args: argparse.Namespace) -> int:
    records = load_records(_DEMO)
    report = analyze(
        records,
        dataset_label="built-in synthetic demo",
        synthetic=True,
        run_id="demo-run",
    )
    written = _write_report(report, Path(args.out))
    print(f"records={len(records)} candidates={report['total_findings']} "
          f"accepted={report['honesty']['accepted_cases']}")
    print("provenance=synthetic (FABRICATED; demo artefact only, never a metric)")
    for path in written:
        print(f"wrote {path}")
    return 0


def _cmd_run(args: argparse.Namespace) -> int:
    synthetic = True if args.synthetic else (False if args.real else None)
    records = load_records(args.input)
    report = analyze(
        records,
        dataset_label=args.label or Path(args.input).name,
        synthetic=synthetic,
    )
    written = _write_report(report, Path(args.out))
    print(f"records={len(records)} candidates={report['total_findings']} "
          f"accepted={report['honesty']['accepted_cases']} "
          f"provenance={report['dataset']['provenance']}")
    if synthetic is None:
        print("WARNING: provenance unspecified; declare --synthetic or --real")
    for path in written:
        print(f"wrote {path}")
    return 0


def _cmd_diff(args: argparse.Namespace) -> int:
    base = json.loads(Path(args.base).read_text(encoding="utf-8"))
    head = json.loads(Path(args.head).read_text(encoding="utf-8"))
    result = compare(base, head)
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.out:
        target = Path(args.out)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
        print(f"wrote {target}")
    summary = result["summary"]
    print(f"added={summary['added']} resolved_candidates={summary['resolved_candidates']} "
          f"persistent={summary['persistent']}")
    print("NOTE: diff of matched phrases on unreviewed candidates, NOT a fix rate")
    if not args.out:
        print(text)
    return 0


def _cmd_validate(args: argparse.Namespace) -> int:
    problems: list[str] = []
    seen: set[str] = set()
    count = 0
    path = Path(args.labels)
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("//"):
            continue
        count += 1
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            problems.append(f"line {line_no}: invalid JSON ({exc})")
            continue
        case_id = row.get("case_id")
        if not case_id:
            problems.append(f"line {line_no}: missing case_id")
        elif case_id in seen:
            problems.append(f"line {line_no}: duplicate case_id {case_id}")
        else:
            seen.add(case_id)
        if row.get("failure_mode") not in FAILURE_MODES:
            problems.append(f"line {line_no}: unknown failure_mode {row.get('failure_mode')!r}")
        if row.get("decision") not in _VALID_DECISIONS:
            problems.append(f"line {line_no}: decision must be one of {sorted(_VALID_DECISIONS)}")
        if not row.get("annotator"):
            problems.append(f"line {line_no}: missing annotator (anonymous is fine)")
    if problems:
        for problem in problems:
            print(f"INVALID {problem}")
        return 1
    print(f"OK: {count} labels, all fields valid")
    print("NOTE: this checks structure only. Inter-annotator agreement needs >= 2 annotators.")
    return 0


def _cmd_taxonomy(_args: argparse.Namespace) -> int:
    problems = validate_taxonomy()
    if problems:
        for problem in problems:
            print(f"INVALID {problem}")
        return 1
    print(f"taxonomy={TAXONOMY_VERSION} modes={len(FAILURE_MODES)} (DRAFT, unvalidated)")
    for rule in RULES:
        print(f"{rule.mode}: strong={len(rule.strong)} weak={len(rule.weak)} "
              f"context={len(rule.context)}")
    print("No precision or recall is claimed: no labelled set exists yet.")
    return 0


def _cmd_privacy(args: argparse.Namespace) -> int:
    targets: list[Path] = []
    root = Path(args.path)
    ignored = {".git", "out", ".local", "__pycache__", ".venv"}
    if root.is_dir():
        targets = [
            p for p in root.rglob("*")
            if p.suffix.lower() in _DATA_SUFFIXES
            and not any(part in ignored for part in p.parts)
        ]
    else:
        targets = [root]
    dirty: list[str] = []
    skipped: list[str] = []
    for path in targets:
        content = path.read_text(encoding="utf-8")
        lines = content.splitlines()
        head = "\n".join(lines[:3])
        if "FABRICATED" in head and not args.include_fabricated:
            skipped.append(str(path))
            continue
        for line_no, line in enumerate(lines, 1):
            if has_personal_data(line):
                dirty.append(f"{path}:{line_no}")
    if dirty:
        for item in dirty:
            print(f"POSSIBLE PII {item}")
        return 1
    print(f"OK: scanned {len(targets) - len(skipped)} data file(s), "
          "no personal-data pattern found")
    if skipped:
        print(f"skipped {len(skipped)} declared-fabricated file(s); "
              "use --include-fabricated to scan them anyway")
    print("NOTE: data files only; pattern-based, not a substitute for human review")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cte",
        description="Turn user complaints into UNREVIEWED agent regression-test candidates.",
    )
    parser.add_argument("--version", action="version", version=f"cte {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    demo = sub.add_parser("demo", help="run the built-in FABRICATED demo dataset")
    demo.add_argument("--out", default="out/demo", help="output directory")
    demo.set_defaults(func=_cmd_demo)

    run = sub.add_parser("run", help="analyse a .jsonl or .csv feedback file")
    run.add_argument("--input", required=True)
    run.add_argument("--out", default="out/report")
    run.add_argument("--label", default="")
    origin = run.add_mutually_exclusive_group()
    origin.add_argument("--synthetic", action="store_true", help="data is fabricated")
    origin.add_argument("--real", action="store_true", help="licence and consent checked")
    run.set_defaults(func=_cmd_run)

    diff = sub.add_parser("diff", help="compare two report.json files")
    diff.add_argument("--base", required=True)
    diff.add_argument("--head", required=True)
    diff.add_argument("--out", default="")
    diff.set_defaults(func=_cmd_diff)

    validate = sub.add_parser("validate", help="check the structure of a label file")
    validate.add_argument("--labels", required=True)
    validate.set_defaults(func=_cmd_validate)

    taxonomy = sub.add_parser("taxonomy", help="print the draft failure-mode taxonomy")
    taxonomy.set_defaults(func=_cmd_taxonomy)

    privacy = sub.add_parser("privacy", help="scan data files for residual personal data")
    privacy.add_argument("--path", required=True)
    privacy.add_argument(
        "--include-fabricated", action="store_true",
        help="also scan files whose header declares FABRICATED test data",
    )
    privacy.set_defaults(func=_cmd_privacy)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)

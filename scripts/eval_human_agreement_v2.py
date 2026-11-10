"""Score the v2 labelling rule: one primary mode per report, causes kept separate.

The v2 workbook has seven columns:

    A 编号 | B 来源 | C 原文 | D 是不是缺陷 | E 主类别（恰好一个）
    F 附带类别（最多两个） | G 理由

The v2 rule says the primary mode is decided by *symptom order*, ten questions,
stop at the first hit, and `logic_or_validation` is only a fallback. Scoring
compares the primary column only. The secondary column exists so the same
workbook can also be scored under the older "label everything you see" rule —
that comparison is the point, not an afterthought.

Usage (one reader):

    python scripts/eval_human_agreement_v2.py \
        --workbook ".local/human_labeling/H_r1.xlsx" \
        --holdout .local/corpus/holdoutH.jsonl \
        --out eval/defect_holdout/human_agreement_v2.json

Usage (several readers, adds reader-reader agreement):

    python scripts/eval_human_agreement_v2.py --workbook a.xlsx --workbook b.xlsx ...

Nothing here replaces a human. The engine is scored *against* the reader; the
reader is never scored against the engine as if the engine were gold.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

from openpyxl import load_workbook

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from complaint_to_eval.defects import DEFECT_MODES, analyze_defects  # noqa: E402
from complaint_to_eval.pipeline import load_records  # noqa: E402

HEADER = ["编号", "来源", "原文", "是不是缺陷", "主类别（只填一个）",
          "附带类别（选填，最多两个）", "理由（一句话）"]


def wilson(k: int, n: int) -> tuple[float, float]:
    if n == 0:
        return 0.0, 0.0
    z = 1.96
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    m = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5)
    return (c - m) / d, (c + m) / d


def cohen_kappa(pairs: list[tuple[str, str]]) -> tuple[float, float]:
    n = len(pairs)
    if not n:
        return 0.0, 0.0
    po = sum(1 for a, b in pairs if a == b) / n
    pe = 0.0
    for label in sorted({x for p in pairs for x in p}):
        pe += (sum(1 for a, _ in pairs if a == label) / n) * (
            sum(1 for _, b in pairs if b == label) / n
        )
    return po, ((po - pe) / (1 - pe) if pe < 1 else 0.0)


def fleiss_kappa(rows: list[list[str]], categories: list[str]) -> float:
    """rows = one list of labels per item, one label per rater."""
    n_items = len(rows)
    if not n_items:
        return 0.0
    n_raters = len(rows[0])
    counts = []
    for row in rows:
        c = Counter(row)
        counts.append([c.get(cat, 0) for cat in categories])
    p_i = []
    for c in counts:
        s = sum(x * x for x in c)
        p_i.append((s - n_raters) / (n_raters * (n_raters - 1)) if n_raters > 1 else 0.0)
    p_bar = sum(p_i) / n_items
    totals = [sum(c[j] for c in counts) for j in range(len(categories))]
    p_e = sum((t / (n_items * n_raters)) ** 2 for t in totals)
    return (p_bar - p_e) / (1 - p_e) if p_e < 1 else 0.0


def split_secondary(raw: str) -> list[str]:
    return [m.strip() for m in raw.replace("，", ",").replace("、", ",").split(",") if m.strip()]


def read_workbook(path: Path) -> dict[str, dict]:
    wb = load_workbook(path, data_only=True)
    if "待标注" not in wb.sheetnames:
        raise SystemExit(f"sheet '待标注' not found in {path}: {wb.sheetnames}")
    ws = wb["待标注"]
    header = [(ws.cell(row=1, column=i).value or "").strip() for i in range(1, 8)]
    if header[:3] != HEADER[:3]:
        raise SystemExit(f"{path.name}: unexpected header {header[:3]}")
    if not str(header[4]).startswith("主类别"):
        raise SystemExit(f"{path.name}: this is not a v2 workbook (E = {header[4]!r})")
    out: dict[str, dict] = {}
    problems: list[str] = []
    for r in range(2, ws.max_row + 1):
        rid = ws.cell(row=r, column=1).value
        if not rid or not str(rid).startswith("r"):
            continue
        rid = str(rid).strip()
        verdict = (ws.cell(row=r, column=4).value or "").strip()
        primary = (ws.cell(row=r, column=5).value or "").strip()
        secondary = split_secondary((ws.cell(row=r, column=6).value or "").strip())
        reason = (ws.cell(row=r, column=7).value or "").strip()
        if verdict not in {"是", "不是", "不确定"}:
            problems.append(f"{rid}: D={verdict!r}")
        if verdict == "是" and primary not in DEFECT_MODES:
            problems.append(f"{rid}: E={primary!r}")
        if verdict != "是" and primary:
            problems.append(f"{rid}: E filled but D={verdict}")
        if len(secondary) > 2:
            problems.append(f"{rid}: {len(secondary)} secondary modes")
        for m in secondary:
            if m not in DEFECT_MODES:
                problems.append(f"{rid}: F={m!r}")
        out[rid] = {"verdict": verdict, "primary": primary,
                    "secondary": secondary, "reason": reason}
    out["_problems"] = problems  # type: ignore[assignment]
    return out


def score(reader: dict[str, dict], order: list[str], engine: dict[str, set[str]],
          gold_secondary: bool) -> dict:
    """gold_secondary: count primary+secondary as the reader's label set."""
    scored = [rid for rid in order if reader[rid]["verdict"] in {"是", "不是"}]
    rows = []
    for rid in order:
        h = reader[rid]
        is_def = h["verdict"] == "是"
        gold = set()
        if is_def:
            gold = {h["primary"]} | (set(h["secondary"]) if gold_secondary else set())
        rows.append({"row": rid, "verdict": h["verdict"],
                     "primary": h["primary"] if is_def else "",
                     "secondary": h["secondary"], "gold": gold,
                     "engine": set(engine.get(rid, set())), "reason": h["reason"]})

    by_row = {r["row"]: r for r in rows}
    scored_rows = [by_row[rid] for rid in scored]

    # record level
    pairs = [("y" if r["verdict"] == "是" else "n",
              "y" if r["engine"] else "n") for r in scored_rows]
    agree, kappa = cohen_kappa(pairs)
    tp = sum(1 for a, b in pairs if a == "y" and b == "y")
    flagged = sum(1 for _, b in pairs if b == "y")
    positives = sum(1 for a, _ in pairs if a == "y")
    rec_p = tp / flagged if flagged else 0.0
    rec_r = tp / positives if positives else 0.0
    clean = len(scored_rows) - positives
    clean_wrong = [r["row"] for r in scored_rows if r["verdict"] == "不是" and r["engine"]]

    # mode level, micro over (record, mode)
    m_tp: Counter[str] = Counter()
    m_fp: Counter[str] = Counter()
    m_fn: Counter[str] = Counter()
    hit_any = 0
    zero_output = 0
    for r in scored_rows:
        gold, pred = r["gold"], r["engine"]
        for m in pred & gold:
            m_tp[m] += 1
        for m in pred - gold:
            m_fp[m] += 1
        for m in gold - pred:
            m_fn[m] += 1
        if gold and pred & gold:
            hit_any += 1
        if gold and not pred:
            zero_output += 1

    tot = (sum(m_tp.values()), sum(m_fp.values()), sum(m_fn.values()))
    micro_p = tot[0] / (tot[0] + tot[1]) if (tot[0] + tot[1]) else 0.0
    micro_r = tot[0] / (tot[0] + tot[2]) if (tot[0] + tot[2]) else 0.0

    # trivial baselines
    base_flag = {"precision": positives / len(scored_rows) if scored_rows else 0.0,
                 "recall": 1.0 if positives else 0.0}
    # per-mode precision if the engine always answered the most common human mode
    top_mode = Counter(r["primary"] for r in scored_rows if r["primary"]).most_common(1)
    base_top = None
    if top_mode:
        mode_name = top_mode[0][0]
        btp = sum(1 for r in scored_rows if mode_name in r["gold"] and mode_name in r["engine"])
        # a "always answer top mode" engine: predict {mode_name} on every row
        btp2 = sum(1 for r in scored_rows if mode_name in r["gold"])
        bfp2 = len(scored_rows) - btp2
        base_top = {"mode": mode_name,
                    "precision": btp2 / len(scored_rows) if scored_rows else 0.0,
                    "recall": btp2 / max(1, sum(1 for r in scored_rows if r["gold"])),
                    "_note": "predicts this mode on every record, never another"}

    return {
        "gold_definition": "primary+secondary" if gold_secondary else "primary only",
        "scored_rows": len(scored_rows),
        "record_level": {
            "agreement": agree, "kappa": kappa,
            "precision": rec_p, "precision_ci": list(wilson(tp, flagged)),
            "recall": rec_r, "recall_ci": list(wilson(tp, positives)),
            "tp": tp, "engine_flagged": flagged, "human_positive": positives,
            "clean_records": clean,
            "clean_wrongly_flagged": clean_wrong,
            "baseline_always_flag": base_flag,
        },
        "mode_level": {
            m: {"tp": m_tp[m], "fp": m_fp[m], "fn": m_fn[m],
                "precision": (m_tp[m] / (m_tp[m] + m_fp[m])) if (m_tp[m] + m_fp[m]) else None,
                "recall": (m_tp[m] / (m_tp[m] + m_fn[m])) if (m_tp[m] + m_fn[m]) else None}
            for m in DEFECT_MODES if (m_tp[m] or m_fp[m] or m_fn[m])
        },
        "micro": {"tp": tot[0], "fp": tot[1], "fn": tot[2],
                  "precision": micro_p, "recall": micro_r,
                  "precision_ci": list(wilson(tot[0], tot[0] + tot[1])),
                  "recall_ci": list(wilson(tot[0], tot[0] + tot[2]))},
        "partial_credit": {"records_with_any_hit": hit_any,
                           "defect_records": positives,
                           "rate": hit_any / positives if positives else 0.0,
                           "engine_silent_on_defect": zero_output},
        "baseline_top_mode": base_top,
        "rows": [dict(r, gold=sorted(r["gold"]), engine=sorted(r["engine"])) for r in rows],
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workbook", action="append", required=True)
    ap.add_argument("--holdout", default=str(ROOT / ".local/corpus/holdoutH.jsonl"))
    ap.add_argument("--out", default=str(ROOT / "eval/defect_holdout/human_agreement_v2.json"))
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    records = load_records(Path(args.holdout))
    order = [f"r{i:02d}" for i in range(1, len(records) + 1)]
    report = analyze_defects(records, dataset_label="v2", synthetic=False)
    engine: dict[str, set[str]] = defaultdict(set)
    for finding in report["findings"]:
        engine[finding["record_id"]].add(finding["defect_mode"])
    engine_by_row = {order[i]: engine.get(rec.id, set()) for i, rec in enumerate(records)}

    readers: dict[str, dict] = {}
    problems: dict[str, list[str]] = {}
    for wb_path in args.workbook:
        path = Path(wb_path)
        data = read_workbook(path)
        problems[path.stem] = data.pop("_problems")  # type: ignore[arg-type]
        readers[path.stem] = data

    payload: dict = {
        "annotator": "human",
        "rule": "v2 (one primary mode by symptom order; logic_or_validation is fallback)",
        "engine_note": "engine is scored against the reader, never treated as gold",
        "rows_in_split": len(order),
        "problems": problems,
        "readers": {},
    }

    primary = score(list(readers.values())[0], order, engine_by_row, gold_secondary=False)
    wide = score(list(readers.values())[0], order, engine_by_row, gold_secondary=True)
    payload["readers"][next(iter(readers))] = {
        "primary_only": primary, "with_secondary": wide,
    }

    # reader-reader agreement when more than one workbook is supplied
    if len(readers) > 1:
        names = list(readers)
        item_rows_bin, item_rows_mode = [], []
        per_pair = {}
        for rid in order:
            verdicts = [readers[n][rid]["verdict"] for n in names]
            if any(v == "不确定" for v in verdicts):
                continue
            item_rows_bin.append(["y" if v == "是" else "n" for v in verdicts])
            item_rows_mode.append([readers[n][rid]["primary"] or "none" for n in names])
        for i, a in enumerate(names):
            for b in names[i + 1:]:
                pairs_b = [(x[0], x[1]) for x in zip([r[i] for r in item_rows_bin],
                                                     [r[j] for j in
                                                      [names.index(b)] * len(item_rows_bin)])]
                agree_b, kappa_b = cohen_kappa(pairs_b)
                per_pair[f"{a} vs {b}"] = {"binary_agreement": agree_b, "binary_kappa": kappa_b}
        for name in names:
            bin_ = [readers[name][rid]["verdict"] for rid in order]
            payload["readers"][name] = payload["readers"].get(name) or {}
            payload["readers"][name]["label_counts"] = dict(Counter(bin_))
            payload["readers"][name]["score"] = score(readers[name], order, engine_by_row, False)
        modes_seen = sorted({m for r in item_rows_mode for m in r} | set(DEFECT_MODES))
        payload["reader_reader"] = {
            "n_items": len(item_rows_bin),
            "binary_fleiss_kappa": fleiss_kappa(item_rows_bin, ["y", "n"]),
            "primary_mode_fleiss_kappa": fleiss_kappa(item_rows_mode, modes_seen),
            "pairs": per_pair,
        }

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    if not args.quiet:
        p = primary
        rl = p["record_level"]
        print(f"split: {len(order)} rows  |  scored: {p['scored_rows']}  |  "
              f"readers: {len(readers)}")
        for name, probs in problems.items():
            if probs:
                print(f"!! {name}: {len(probs)} format problems -> {probs[:5]}")
        print()
        print("== record level (is this a defect report at all) ==")
        print(f"engine vs reader : agreement {rl['agreement']:.3f}  kappa {rl['kappa']:.3f}")
        print(f"                   precision {rl['precision']:.3f}"
              f" [{rl['precision_ci'][0]:.3f},{rl['precision_ci'][1]:.3f}]"
              f"  recall {rl['recall']:.3f}"
              f" [{rl['recall_ci'][0]:.3f},{rl['recall_ci'][1]:.3f}]  TP {rl['tp']}")
        print(f"always-flag base : precision {rl['baseline_always_flag']['precision']:.3f}"
              f"  recall {rl['baseline_always_flag']['recall']:.3f}")
        print(f"clean records wrongly flagged: {len(rl['clean_wrongly_flagged'])}"
              f"/{rl['clean_records']} {rl['clean_wrongly_flagged']}")
        print()
        print("== mode level, primary only (reader = reference) ==")
        print(f"{'mode':22}{'TP':>4}{'FP':>4}{'FN':>4}{'P':>8}{'R':>8}")
        for mode, c in p["mode_level"].items():
            pp = "-" if c["precision"] is None else f"{c['precision']:.2f}"
            rr = "-" if c["recall"] is None else f"{c['recall']:.2f}"
            print(f"{mode:22}{c['tp']:>4}{c['fp']:>4}{c['fn']:>4}{pp:>8}{rr:>8}")
        mi = p["micro"]
        print(f"{'micro':22}{mi['tp']:>4}{mi['fp']:>4}{mi['fn']:>4}"
              f"{mi['precision']:>8.2f}{mi['recall']:>8.2f}")
        pc = p["partial_credit"]
        print(f"at least one mode right: {pc['records_with_any_hit']}/{pc['defect_records']}"
              f" ({pc['rate']:.3f})  |  engine silent on {pc['engine_silent_on_defect']} defect rows")
        w = wide["micro"]
        print(f"same rows, gold = primary+secondary: micro P {w['precision']:.3f}  R {w['recall']:.3f}")
        if p["baseline_top_mode"]:
            b = p["baseline_top_mode"]
            print(f"baseline 'always {b['mode']}': precision {b['precision']:.3f}  recall {b['recall']:.3f}")
        if "reader_reader" in payload:
            rr = payload["reader_reader"]
            print()
            print(f"== reader vs reader (n={rr['n_items']}) ==")
            print(f"binary Fleiss kappa {rr['binary_fleiss_kappa']:.3f}  "
                  f"primary-mode Fleiss kappa {rr['primary_mode_fleiss_kappa']:.3f}")
            for k, v in rr["pairs"].items():
                print(f"  {k}: agreement {v['binary_agreement']:.3f}  kappa {v['binary_kappa']:.3f}")
        print()
        print("== disagreement table (every defect row where engine != reader primary) ==")
        for r in p["rows"]:
            if r["verdict"] == "是" and r["engine"] != [r["primary"]]:
                print(f"{r['row']}: reader={r['primary']}"
                      f" (+{','.join(r['secondary']) or '-'})"
                      f" | engine={','.join(sorted(r['engine'])) or 'none'}")
        print(f"\nwrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

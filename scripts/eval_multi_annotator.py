"""Multi-annotator agreement over the same split.

Run:
    python scripts/eval_multi_annotator.py \
        --workbook "E:/.../待标注_40条_甲_严格证据.xlsx" \
        --workbook "E:/.../待标注_40条_乙_宽松意图.xlsx" \
        --labels eval/defect_holdout/labels_holdout_g.jsonl \
        --holdout .local/corpus/holdoutG.jsonl \
        --out out/multi_annotator.json

Reports, in order:

1. Verdict distribution per annotator (is 是 / 不是 / 不确定).
2. Pairwise Cohen's kappa on the binary call, over rows where both annotators
   gave 是 or 不是. "不确定" is never coerced.
3. Fleiss' kappa across all annotators, both excluding indeterminate rows and
   treating 不确定 as a third category.
4. Each annotator against the engine, and against this project's own labels.
5. Mode level: the engine scored against each annotator as reference.
6. Rows with no consensus, with the full verdict vector.

The point of the exercise is not to find the "best" annotator. It is to find out
whether two careful readers can agree at all — if they cannot, the taxonomy's
boundaries are the defect, not the engine.
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

YES, NO, UNSURE = "是", "不是", "不确定"


def read_workbook(path: Path) -> dict[str, dict]:
    wb = load_workbook(path, data_only=True)
    if "待标注" not in wb.sheetnames:
        raise SystemExit(f"sheet '待标注' missing in {path}: {wb.sheetnames}")
    ws = wb["待标注"]
    out: dict[str, dict] = {}
    for r in range(2, ws.max_row + 1):
        rid = ws.cell(row=r, column=1).value
        if not rid or not str(rid).startswith("r"):
            continue
        modes_raw = (ws.cell(row=r, column=5).value or "").strip()
        out[str(rid)] = {
            "verdict": (ws.cell(row=r, column=4).value or "").strip(),
            "modes": [m.strip() for m in modes_raw.replace("，", ",").split(",") if m.strip()],
            "reason": (ws.cell(row=r, column=6).value or "").strip(),
        }
    return out


def cohen_kappa(pairs: list[tuple[bool, bool]]) -> tuple[float, float, int]:
    n = len(pairs)
    if not n:
        return float("nan"), float("nan"), 0
    po = sum(1 for a, b in pairs if a == b) / n
    pa = sum(1 for a, _ in pairs if a) / n
    pb = sum(1 for _, b in pairs if b) / n
    pe = pa * pb + (1 - pa) * (1 - pb)
    kappa = (po - pe) / (1 - pe) if pe < 1 else float("nan")
    return po, kappa, n


def fleiss_kappa(rows: list[list[str]], categories: list[str]) -> float:
    rows = [r for r in rows if r]
    if not rows:
        return float("nan")
    m = len(rows[0])
    if m < 2:
        return float("nan")
    n = len(rows)
    counts = [{c: r.count(c) for c in categories} for r in rows]
    p_i = sum((sum(v * v for v in c.values()) - m) / (m * (m - 1)) for c in counts) / n
    totals = {c: sum(c2[c] for c2 in counts) / (n * m) for c in categories}
    p_e = sum(v * v for v in totals.values())
    return (p_i - p_e) / (1 - p_e) if p_e < 1 else float("nan")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workbook", action="append", required=True,
                    help="repeatable; optional 'Name=path' to control the label")
    ap.add_argument("--labels", required=True, help="this project's own labels for the split")
    ap.add_argument("--holdout", required=True)
    ap.add_argument("--out", default="out/multi_annotator.json")
    args = ap.parse_args()

    annotators: list[tuple[str, dict[str, dict]]] = []
    for spec in args.workbook:
        if "=" in spec:
            name, path = spec.split("=", 1)
        else:
            name, path = Path(spec).stem.replace("待标注_40条_", ""), spec
        annotators.append((name, read_workbook(Path(path))))

    records = load_records(Path(args.holdout))
    row_ids = [f"r{i:02d}" for i in range(1, len(records) + 1)]
    rec_by_row = {rid: rec for rid, rec in zip(row_ids, records)}

    mine: dict[str, set[str]] = {}
    for line in Path(args.labels).read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            mine[row["record_id"]] = set(row["modes"])

    report = analyze_defects(records, dataset_label="multi", synthetic=False)
    engine: dict[str, set[str]] = defaultdict(set)
    for f in report["findings"]:
        engine[f["record_id"]].add(f["defect_mode"])

    names = [n for n, _ in annotators] + ["本项目标签", "引擎"]

    print("== verdict distribution ==")
    print(f"{'annotator':16}{'是':>5}{'不是':>6}{'不确定':>7}")
    dist: dict[str, Counter] = {}
    for name, data in annotators:
        c = Counter(data[r]["verdict"] for r in row_ids)
        dist[name] = c
        print(f"{name:16}{c.get(YES, 0):>5}{c.get(NO, 0):>6}{c.get(UNSURE, 0):>7}")
    mine_yes = sum(1 for r in row_ids if mine[rec_by_row[r].id])
    eng_yes = sum(1 for r in row_ids if engine[rec_by_row[r].id])
    print(f"{'本项目标签':14}{mine_yes:>5}{len(row_ids) - mine_yes:>6}{0:>7}")
    print(f"{'引擎':16}{eng_yes:>5}{len(row_ids) - eng_yes:>6}{0:>7}")

    def verdict_of(name: str, rid: str, rec_id: str) -> str:
        if name == "本项目标签":
            return YES if mine[rec_id] else NO
        if name == "引擎":
            return YES if engine[rec_id] else NO
        data = dict(annotators)[name]
        return data[rid]["verdict"]

    print()
    print("== pairwise agreement on the binary call (κ / n, indeterminate rows dropped) ==")
    header = f"{'':16}" + "".join(f"{n[:6]:>12}" for n in names)
    print(header)
    pair_kappa: dict[str, float] = {}
    for a in names:
        cells = []
        for b in names:
            if a == b:
                cells.append(f"{'—':>12}")
                continue
            pairs = []
            for rid in row_ids:
                va = verdict_of(a, rid, rec_by_row[rid].id)
                vb = verdict_of(b, rid, rec_by_row[rid].id)
                if va in (YES, NO) and vb in (YES, NO):
                    pairs.append((va == YES, vb == YES))
            _, k, n = cohen_kappa(pairs)
            pair_kappa[f"{a}|{b}"] = k
            cells.append(f"{k:>7.3f}({n:>2})"[:12].rjust(12))
        print(f"{a:16}" + "".join(cells))

    print()
    print("== Fleiss' kappa across the human annotators ==")
    human_names = [n for n, _ in annotators]
    strict_rows = [[dict(annotators)[n][r]["verdict"] for n in human_names] for r in row_ids]
    clean_rows = [[v for v in r if v in (YES, NO)] for r in strict_rows]
    clean_rows = [r for r in clean_rows if len(r) == len(human_names)]
    print(f"  two categories (不确定 rows dropped, n={len(clean_rows)} rows): "
          f"{fleiss_kappa(clean_rows, [YES, NO]):.3f}")
    print(f"  three categories (不确定 counted as its own, n={len(row_ids)} rows): "
          f"{fleiss_kappa(strict_rows, [YES, NO, UNSURE]):.3f}")
    with_mine = [r + [verdict_of("本项目标签", rid, rec_by_row[rid].id)] for r, rid in zip(strict_rows, row_ids)]
    with_engine = [r + [verdict_of("引擎", rid, rec_by_row[rid].id)] for r, rid in zip(strict_rows, row_ids)]
    n_plus = len(human_names) + 1
    print(f"  + this project's labels ({n_plus} raters): "
          f"{fleiss_kappa([r for r in with_mine if len(r) == n_plus], [YES, NO, UNSURE]):.3f}")
    print(f"  + engine ({n_plus} raters):               "
          f"{fleiss_kappa([r for r in with_engine if len(r) == n_plus], [YES, NO, UNSURE]):.3f}")

    print()
    print("== mode level: engine scored against each annotator as reference ==")
    print(f"{'reference':16}{'TP':>4}{'FP':>4}{'FN':>4}{'microP':>8}{'microR':>8}")
    mode_scores: dict[str, dict] = {}
    refs = [(n, dict(annotators)[n]) for n, _ in annotators]
    for name, data in refs + [("本项目标签", None), ("引擎", None)]:
        if name == "引擎":
            continue
        tp = fp = fn = 0
        per_mode = {m: {"tp": 0, "fp": 0, "fn": 0} for m in DEFECT_MODES}
        for rid in row_ids:
            rec = rec_by_row[rid]
            if name == "本项目标签":
                gold = mine[rec.id]
            else:
                v = data[rid]["verdict"]
                gold = set(data[rid]["modes"]) if v == YES else set()
            pred = engine[rec.id]
            for m in pred & gold:
                tp += 1
                per_mode[m]["tp"] += 1
            for m in pred - gold:
                fp += 1
                per_mode[m]["fp"] += 1
            for m in gold - pred:
                fn += 1
                per_mode[m]["fn"] += 1
        p = tp / (tp + fp) if (tp + fp) else float("nan")
        r = tp / (tp + fn) if (tp + fn) else float("nan")
        print(f"{name:16}{tp:>4}{fp:>4}{fn:>4}{p:>8.2f}{r:>8.2f}")
        mode_scores[name] = {"tp": tp, "fp": fp, "fn": fn, "precision": p, "recall": r,
                             "per_mode": per_mode}

    print()
    print("== mode labels: reader-to-reader, on rows both call a defect ==")
    print(f"{'pair':44}{'both 是':>8}{'same set':>10}{'mean Jaccard':>14}")

    def modes_of(name: str, rid: str) -> set[str]:
        if name == "本项目标签":
            return mine[rec_by_row[rid].id]
        return set(dict(annotators)[name][rid]["modes"])

    pairwise_mode: dict[str, dict] = {}
    compare_names = human_names + ["本项目标签"]
    for i, a in enumerate(compare_names):
        for b in compare_names[i + 1:]:
            both = [rid for rid in row_ids
                    if verdict_of(a, rid, rec_by_row[rid].id) == YES
                    and verdict_of(b, rid, rec_by_row[rid].id) == YES]
            exact = sum(1 for rid in both if modes_of(a, rid) == modes_of(b, rid))
            jac = []
            for rid in both:
                ma, mb = modes_of(a, rid), modes_of(b, rid)
                jac.append(len(ma & mb) / len(ma | mb) if (ma | mb) else 1.0)
            e_rate = exact / len(both) if both else float("nan")
            mean_j = sum(jac) / len(jac) if jac else float("nan")
            print(f"{a + ' vs ' + b:44}{len(both):>8}{e_rate:>10.2f}{mean_j:>14.2f}")
            pairwise_mode[f"{a}|{b}"] = {
                "both_yes": len(both), "exact_rate": e_rate, "mean_jaccard": mean_j,
            }

    print()
    print("== rows with no consensus (annotators do not all say the same thing) ==")
    no_consensus = []
    for rid in row_ids:
        vs = [dict(annotators)[n][rid]["verdict"] for n in human_names]
        if len(set(vs)) > 1:
            rec = rec_by_row[rid]
            no_consensus.append({
                "row": rid,
                "record_id": rec.id,
                "verdicts": dict(zip(human_names, vs)),
                "modes": {n: dict(annotators)[n][rid]["modes"] for n in human_names},
                "mine": sorted(mine[rec.id]),
                "engine": sorted(engine[rec.id]),
            })
    print(f"  {len(no_consensus)} of {len(row_ids)} rows")
    for item in no_consensus:
        spread = " ".join(f"{k}={v}" for k, v in item["verdicts"].items())
        print(f"  {item['row']} {item['record_id']}: {spread} | mine={'是' if item['mine'] else '不是'} | engine={'是' if item['engine'] else '不是'}")

    payload = {
        "annotators": human_names,
        "verdict_distribution": {n: dict(dist[n]) for n in human_names},
        "pairwise_kappa": pair_kappa,
        "fleiss": {
            "two_categories": fleiss_kappa(clean_rows, [YES, NO]),
            "two_categories_rows": len(clean_rows),
            "three_categories": fleiss_kappa(strict_rows, [YES, NO, UNSURE]),
            "with_project_labels": fleiss_kappa([r for r in with_mine if len(r) == 6], [YES, NO, UNSURE]),
            "with_engine": fleiss_kappa([r for r in with_engine if len(r) == 6], [YES, NO, UNSURE]),
        },
        "mode_level": mode_scores,
        "mode_pairwise": pairwise_mode,
        "no_consensus": no_consensus,
        "rows": [
            {
                "row": rid,
                "record_id": rec_by_row[rid].id,
                "verdicts": {n: dict(annotators)[n][rid]["verdict"] for n in human_names},
                "modes": {n: dict(annotators)[n][rid]["modes"] for n in human_names},
                "mine": sorted(mine[rec_by_row[rid].id]),
                "engine": sorted(engine[rec_by_row[rid].id]),
            }
            for rid in row_ids
        ],
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nwrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

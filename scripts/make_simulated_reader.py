"""Generate a SYNTHETIC second reader to exercise the multi-reader pipeline.

This is a testing tool, not a data source. Every workbook it writes is derived
from an existing reader by a deterministic perturbation, so any agreement
statistic computed from it is self-referential. It can prove that the scorer
runs; it can never prove that the v2 rule makes two people agree.

The output is written to .local/ (gitignored) and its 怎么填 sheet says
SIMULATED on the first line. Never hand it to a human annotator.

Usage:
    python scripts/make_simulated_reader.py --source .local/human_labeling/H_r1.xlsx \
        --out .local/human_labeling/sim_moderate.xlsx --variant moderate
"""

from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path

from openpyxl import Workbook, load_workbook

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from complaint_to_eval.defects import DEFECT_MODES  # noqa: E402

#: A plausible alternative reading for a mode — the boundaries real readers
#: actually disagreed on in split G. Used only to make the simulated
#: disagreements interpretable, never to claim they are correct.
BOUNDARY_SWAP = {
    "data_integrity": "logic_or_validation",
    "logic_or_validation": "data_integrity",
    "crash_or_error": "performance",
    "performance": "crash_or_error",
    "ui_or_ux": "config_or_env",
    "config_or_env": "ui_or_ux",
    "security": "config_or_env",
    "regression": "crash_or_error",
    "docs": "ui_or_ux",
    "i18n_or_locale": "ui_or_ux",
}

VARIANTS = {
    # variant -> (unclear rows, primary-mode swaps, secondary-column edits)
    "identical": (0, 0, 0),
    "moderate": (2, 6, 4),
    "divergent": (8, 16, 12),
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--variant", choices=sorted(VARIANTS), default="moderate")
    ap.add_argument("--seed", type=int, default=20261111)
    args = ap.parse_args()

    src = load_workbook(args.source, data_only=True)
    ws_src = src["待标注"]
    rows = [[ws_src.cell(row=r, column=c).value for c in range(1, 8)]
            for r in range(2, ws_src.max_row + 1)
            if str(ws_src.cell(row=r, column=1).value or "").startswith("r")]
    n_unclear, n_primary, n_secondary = VARIANTS[args.variant]
    rng = random.Random(args.seed)
    defect_ids = [i for i, row in enumerate(rows) if row[3] == "是"]

    # deterministic, disjoint perturbation sets
    pool = rng.sample(defect_ids, len(defect_ids))
    swap_primary = set(pool[:n_primary])
    edit_secondary = set(pool[n_primary:n_primary + n_secondary])
    to_unclear = set(rng.sample(
        [i for i in defect_ids if i not in swap_primary], min(n_unclear, len(defect_ids))))

    for i, row in enumerate(rows):
        rid = row[0]
        if i in to_unclear:
            row[3], row[4], row[5] = "不确定", None, None
            row[6] = f"模拟读者：这条卡在是不是故障报告，无法判定。"
            continue
        if i in swap_primary:
            old = row[4]
            new = BOUNDARY_SWAP.get(old, "logic_or_validation")
            if new in DEFECT_MODES and new != old:
                row[4] = new
        if i in edit_secondary:
            row[5] = BOUNDARY_SWAP.get(row[4] or "", "logic_or_validation")
        row[6] = (f"模拟读者（{args.variant}）：按症状顺序判为 "
                  f"{row[4] or '非缺陷'}；理由为模板文本，非真人书写。")

    wb = Workbook()
    ws_info = wb.active
    ws_info.title = "怎么填"
    ws_info["A1"] = ("SIMULATED / MODEL-GENERATED / NOT HUMAN / NOT FOR "
                     "PUBLICATION — pipeline test only")
    ws_info["A2"] = (f"variant={args.variant} seed={args.seed} "
                     f"unclear={n_unclear} primary_swaps={n_primary} "
                     f"secondary_edits={n_secondary}")
    ws_info["A3"] = "Derived from an existing reader; never independent."
    ws_data = wb.create_sheet("待标注")
    header = ["编号", "来源", "原文", "是不是缺陷", "主类别（只填一个）",
              "附带类别（选填，最多两个）", "理由（一句话）"]
    for c, value in enumerate(header, 1):
        ws_data.cell(row=1, column=c, value=value)
    for r, row in enumerate(rows, 2):
        for c, value in enumerate(row, 1):
            ws_data.cell(row=r, column=c, value=value)
    ws_data.cell(row=len(rows) + 2, column=1,
                 value="SIMULATED — do not submit as human labels")

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    wb.save(out)
    print(f"wrote {out}  variant={args.variant}  rows={len(rows)}  "
          f"unclear={len(to_unclear)} primary_swaps={len(swap_primary)} "
          f"secondary_edits={len(edit_secondary)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

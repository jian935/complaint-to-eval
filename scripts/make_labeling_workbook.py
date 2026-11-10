"""Build a blind labelling workbook from a hold-out split.

Run (v1, one free-form mode list):
    python scripts/make_labeling_workbook.py \
        --holdout .local/corpus/holdoutG.jsonl \
        --out .local/human_labeling/review.xlsx

Run (v2, one primary mode + optional causes, per eval/GRANULARITY_RULE.md):
    python scripts/make_labeling_workbook.py --spec v2 \
        --holdout .local/corpus/holdoutG.jsonl \
        --out .local/human_labeling/review_v2.xlsx

The workbook carries the issue text and nothing else: no predicted mode, no
existing label, no engine output. That is deliberate. A labeller who can see the
model's guess is not an independent reader, and the whole point of this exercise
is to get a second independent reader.

Requires openpyxl. This is a build-time dependency for generating the workbook
only; the engine itself stays standard-library-only.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

MODES = [
    ("crash_or_error", "进程/请求/命令直接失败：崩溃、未捕获异常、traceback、非 2xx、非零退出",
     "Uncaught ImportError in main.py"),
    ("data_integrity", "跑完了，但数据丢了/截断/重复/顺序错/内容不对",
     "rows silently truncated on export"),
    ("config_or_env", "环境变量或配置写了不生效、被忽略；依赖装不上",
     "ENV_VAR is ignored in STARTTLS mode"),
    ("ui_or_ux", "跑完了、数据也对，但界面错位/被遮挡/点不动/焦点丢/不刷新",
     "preview is covered by main content"),
    ("i18n_or_locale", "翻译缺失或错、回落到英文、区域/日期格式不对",
     "falls back to English for Arabic locales"),
    ("security", "越过了不该越过的边界：路径穿越、越权、绕过确认、密钥泄露",
     "path traversal outside the repository"),
    ("performance", "卡死、超时、内存泄漏、明显变慢（不是「有点慢」）",
     "the worker hangs and never returns"),
    ("regression", "「以前能用，某个版本之后不能用了」——带版本锚点",
     "this worked before v0.86"),
    ("docs", "文档缺步骤、README 写错、照着文档装不起来",
     "readme is missing the setup step"),
    ("logic_or_validation", "兜底类：判断/校验本身错，但没有更具体的表现形态",
     "accepts a trailing newline it should reject"),
]

DECISION_ORDER = [
    ("第 1 问", "进程、请求或命令直接失败了吗？（抛异常、崩溃、非 2xx、非零退出）", "crash_or_error"),
    ("第 2 问", "跑完了，但数据丢/截断/重复/顺序错/内容不对？", "data_integrity"),
    ("第 3 问", "跑完了、数据也对，但界面错位/点不动/不刷新？", "ui_or_ux"),
    ("第 4 问", "跑完了，但卡死、超时、泄漏、明显变慢？", "performance"),
    ("第 5 问", "越过了不该越过的边界（路径、权限、确认、密钥）？", "security"),
    ("第 6 问", "是否「以前能用、现在不能」并带版本锚点？", "regression"),
    ("第 7 问", "是不是说某个配置/环境变量不生效、装不上？", "config_or_env"),
    ("第 8 问", "是不是说文档缺了或写错了？", "docs"),
    ("第 9 问", "是不是说翻译/区域格式不对？", "i18n_or_locale"),
    ("都不命中", "是「判断/校验本身错」，但没有更具体的表现形态", "logic_or_validation"),
]

INSTRUCTIONS_V1: list[tuple[str, str]] = [
    ("title", "任务：给一批真实用户报告分类"),
    ("p", "下面是一批真实项目的用户反馈（来自两个开源 AI 工具的问题追踪器，已做脱敏处理，"
          "去掉了邮箱、链接里的个人信息）。我们需要独立的人来判断两件事：这条报告是不是在说"
          "某个东西坏了；如果是，属于哪一类。"),
    ("p", "这份表里只有原文，没有任何自动判断结果。请按你自己的理解填。"
          "你的判断会用来衡量一次独立复核的结果，所以「和多数人不一样」本身不是错误。"),
]

INSTRUCTIONS_V2: list[tuple[str, str]] = [
    ("title", "任务：给一批真实用户报告分类（v2 规则）"),
    ("p", "背景和上一版相同：一批真实的、已脱敏的用户报告，需要独立的人判断"
          "「是不是缺陷」和「属于哪一类」。"),
    ("p", "这一版改了一条规则，请先读它，它决定了怎么填。上一轮四个人标同一批数据时，"
          "大家对「是不是缺陷」高度一致，但类别填法不同：有人只填一个，有人把症状和根因都填上。"
          "结果两套填法没法比较。所以这一版要求："),
    ("p", "① 主类别（E 列）：恰好一个，必填。"),
    ("p", "② 附带类别（F 列）：选填，最多两个。放你另外看到的根因或次要问题。"),
    ("p", "③ 主类别按「故障的表现形态」定，不按「用户感受」，也不按「技术根因」。"
          "一条请求返回 400，表现形态是「请求失败」，主类别就是 crash_or_error；"
          "它为什么失败（校验太严）写进附带类别。"),
    ("p", "④ 下面的问题请按顺序问，命中就停。顺序本身就是规则——同一件事先被前面某问命中，"
          "就归那一类，不要再往下问。"),
    ("p", "⑤ logic_or_validation 是兜底类：只有前面九问都不命中时才用它。"
          "它现在被用得太多了，很多其实是 crash 或 data。"),
    ("p", "填法：D 列选「是/不是/不确定」；选「是」的必须填 E 列且只填一个；"
          "F 列可选；G 列写一句理由，填「不确定」的必须写清卡在哪。"),
]

SHARED_RULES: list[tuple[str, str]] = [
    ("", ""),
    ("h2", "怎么判定「是不是缺陷」"),
    ("p", "只问一件事：这条报告有没有在主张「某个功能坏了 / 行为和预期不符 / 环境里出了错」。"),
    ("p", "算缺陷：报错、崩溃、数据不对、界面坏、配置不生效、以前能用现在不能用、"
          "某个操作得到错误结果。"),
    ("p", "不算缺陷：功能请求（「希望支持……」「能不能加……」）、提问（「怎么才能……」）、"
          "纯讨论、经验分享、赞助推广、只有标题没有内容。"),
    ("p", "边界：主线在报问题、末尾顺带提功能请求 → 算缺陷；"
          "问「怎么配置」但实际是说「配了没用」→ 算缺陷。"),
    ("", ""),
    ("h2", "交付"),
    ("p", "保存原 .xlsx，文件名不变，直接发回。不要删行、不要改 A/B/C 列、不要新增 sheet。"
          "可以分几次做，随时保存。整批约 40–50 分钟。"),
    ("p", "只看原文，不要上网搜这个 issue。搜到后来的讨论会看到结论，判断就不独立了。"),
    ("p", "你的判断只用于统计一致性，不会被用来评价你的能力，对外只报聚合数字，不公开姓名。"),
]


HEADERS_V1 = ["编号", "来源", "原文", "是不是缺陷", "缺陷类别（逗号分隔）", "理由（一句话）"]
WIDTHS_V1 = [8, 9, 96, 12, 34, 44]

HEADERS_V2 = ["编号", "来源", "原文", "是不是缺陷", "主类别（只填一个）",
              "附带类别（选填，最多两个）", "理由（一句话）"]
WIDTHS_V2 = [8, 9, 84, 12, 26, 28, 40]

HEADER_FILL = PatternFill("solid", fgColor="E6F1FB")
SECTION_FILL = PatternFill("solid", fgColor="F1EFE8")
THIN = Side(style="thin", color="B4B2A9")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
MODES_CSV = ",".join(m[0] for m in MODES)


def _visual_width(text: str) -> int:
    """CJK glyphs occupy roughly two Latin character cells."""
    return sum(2 if ord(ch) > 127 else 1 for ch in text)


def _write_paragraphs(ws, start_row: int, items: list[tuple[str, str]]) -> int:
    r = start_row
    for kind, text in items:
        cell = ws.cell(row=r, column=1, value=text)
        if kind == "title":
            cell.font = Font(size=15, bold=True)
            ws.row_dimensions[r].height = 26
        elif kind == "h2":
            cell.font = Font(size=13, bold=True)
            cell.fill = SECTION_FILL
            ws.row_dimensions[r].height = 24
        elif text:
            cell.font = Font(size=11)
            cell.alignment = Alignment(wrap_text=True, vertical="top")
            lines = max(1, -(-_visual_width(text) // 108))
            ws.row_dimensions[r].height = 17 * lines + 6
        r += 1
    return r


def build_mode_table(ws, start_row: int) -> int:
    headers = ["类名（填这个）", "什么时候算这一类", "例子"]
    widths = [22, 58, 38]
    for i, (h, w) in enumerate(zip(headers, widths), start=1):
        c = ws.cell(row=start_row, column=i, value=h)
        c.font = Font(size=11, bold=True)
        c.fill = HEADER_FILL
        c.border = BORDER
        cur = ws.column_dimensions[get_column_letter(i)].width or 0
        ws.column_dimensions[get_column_letter(i)].width = max(cur, w)
    r = start_row + 1
    for name, when, example in MODES:
        ws.cell(row=r, column=1, value=name).font = Font(size=10, name="Consolas")
        ws.cell(row=r, column=2, value=when).font = Font(size=10)
        ws.cell(row=r, column=3, value=example).font = Font(
            size=10, name="Consolas", italic=True)
        for col in range(1, 4):
            ws.cell(row=r, column=col).alignment = Alignment(wrap_text=True, vertical="top")
            ws.cell(row=r, column=col).border = BORDER
        ws.row_dimensions[r].height = 34
        r += 1
    return r


def build_decision_table(ws, start_row: int) -> int:
    headers = ["顺序", "问什么（命中就停）", "归到哪一类"]
    widths = [10, 74, 30]
    for i, (h, w) in enumerate(zip(headers, widths), start=1):
        c = ws.cell(row=start_row, column=i, value=h)
        c.font = Font(size=11, bold=True)
        c.fill = HEADER_FILL
        c.border = BORDER
        cur = ws.column_dimensions[get_column_letter(i)].width or 0
        ws.column_dimensions[get_column_letter(i)].width = max(cur, w)
    r = start_row + 1
    for step, question, mode in DECISION_ORDER:
        ws.cell(row=r, column=1, value=step).font = Font(size=10)
        ws.cell(row=r, column=2, value=question).font = Font(size=10)
        ws.cell(row=r, column=3, value=mode).font = Font(size=10, name="Consolas")
        for col in range(1, 4):
            ws.cell(row=r, column=col).alignment = Alignment(wrap_text=True, vertical="top")
            ws.cell(row=r, column=col).border = BORDER
        ws.row_dimensions[r].height = 30
        r += 1
    return r


def build_sheet(ws, records: list[dict], spec: str) -> None:
    headers = HEADERS_V2 if spec == "v2" else HEADERS_V1
    widths = WIDTHS_V2 if spec == "v2" else WIDTHS_V1
    ws.sheet_view.showGridLines = False
    for i, (h, w) in enumerate(zip(headers, widths), start=1):
        c = ws.cell(row=1, column=i, value=h)
        c.font = Font(size=11, bold=True)
        c.fill = HEADER_FILL
        c.border = BORDER
        c.alignment = Alignment(vertical="center", horizontal="center", wrap_text=True)
        ws.column_dimensions[get_column_letter(i)].width = w
    ws.row_dimensions[1].height = 32
    ws.freeze_panes = "A2"

    for idx, rec in enumerate(records, start=1):
        row = idx + 1
        ws.cell(row=row, column=1, value=f"r{idx:02d}")
        ws.cell(row=row, column=2, value=rec["id"].split("-")[0])
        ws.cell(row=row, column=3, value=rec["text"].strip())
        ws.cell(row=row, column=1).font = Font(size=10, name="Consolas")
        ws.cell(row=row, column=2).font = Font(size=10)
        ws.cell(row=row, column=3).font = Font(size=10)
        for col in range(1, len(headers) + 1):
            ws.cell(row=row, column=col).alignment = Alignment(vertical="top", wrap_text=True)
            ws.cell(row=row, column=col).border = BORDER
        ws.row_dimensions[row].height = 92

    last = len(records) + 1
    dv = DataValidation(type="list", formula1='"是,不是,不确定"', allow_blank=True,
                        showDropDown=False)
    dv.error = "请从下拉里选：是 / 不是 / 不确定"
    dv.errorTitle = "只能选这三项"
    ws.add_data_validation(dv)
    dv.add(f"D2:D{last}")

    if spec == "v2":
        dv_mode = DataValidation(type="list", formula1=f'"{MODES_CSV}"', allow_blank=True,
                                 showDropDown=False)
        dv_mode.error = "请从下拉里选一个类名，只能选一个"
        dv_mode.errorTitle = "主类别只能一个"
        ws.add_data_validation(dv_mode)
        dv_mode.add(f"E2:E{last}")

    note = ws.cell(row=last + 2, column=1,
                   value="填完保存这个文件发回即可。不要新增/删除行。")
    note.font = Font(size=10, italic=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--holdout", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--limit", type=int, default=0, help="cap rows (0 = all)")
    ap.add_argument("--spec", choices=["v1", "v2"], default="v1")
    args = ap.parse_args()

    records = [json.loads(line) for line in Path(args.holdout).read_text(
        encoding="utf-8").splitlines() if line.strip()]
    if args.limit:
        records = records[: args.limit]

    wb = Workbook()
    ws_readme = wb.active
    ws_readme.title = "怎么填"
    ws_readme.column_dimensions["A"].width = 118
    ws_readme.sheet_view.showGridLines = False

    intro = INSTRUCTIONS_V2 if args.spec == "v2" else INSTRUCTIONS_V1
    r = _write_paragraphs(ws_readme, 1, intro)

    if args.spec == "v2":
        r += 1
        ws_readme.cell(row=r, column=1, value="决策顺序（问完命中就停）").font = Font(
            size=13, bold=True)
        r = build_decision_table(ws_readme, r + 1)

    r += 1
    ws_readme.cell(row=r, column=1, value="十类速查").font = Font(size=13, bold=True)
    r = build_mode_table(ws_readme, r + 1)

    r = _write_paragraphs(ws_readme, r + 1, SHARED_RULES)

    ws_data = wb.create_sheet("待标注")
    build_sheet(ws_data, records, args.spec)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    wb.save(out)
    print(f"wrote {out}  spec={args.spec}  rows={len(records)}  "
          f"size={out.stat().st_size} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

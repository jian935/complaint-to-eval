"""Build a blind labelling workbook from a hold-out split.

Run:  python scripts/make_labeling_workbook.py \
          --holdout .local/corpus/holdoutG.jsonl \
          --out .local/human_labeling/review.xlsx

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
    ("crash_or_error", "程序崩溃、抛未捕获异常、报 traceback、段错误", "Uncaught ImportError in main.py"),
    ("data_integrity", "数据丢失、截断、损坏、重复、计数错、导出内容不对", "rows silently truncated on export"),
    ("config_or_env", "环境变量/配置写了不生效、被忽略、安装依赖坏掉", "ENV_VAR is ignored in STARTTLS mode"),
    ("ui_or_ux", "界面错位、被遮挡、点击无响应、焦点丢失、渲染不刷新", "preview is covered by main content"),
    ("i18n_or_locale", "翻译缺失或错、语言回落到英文、区域格式不对", "falls back to English for Arabic locales"),
    ("security", "路径穿越、越权执行、绕过确认、任意命令执行、凭证泄露", "path traversal outside the repository"),
    ("performance", "卡死、超时、内存泄漏、明显变慢（不是「有点慢」）", "the worker hangs and never returns"),
    ("regression", "以前能用现在不能用、某版本之后坏掉", "this worked before v0.86"),
    ("docs", "文档缺步骤、README 写错、装不起来因为没写清", "readme is missing the setup step"),
    ("logic_or_validation", "逻辑判断错、类型转换错、非法输入被接受、重复执行、校验缺失",
     "accepts a trailing newline and stores it"),
]

INSTRUCTIONS: list[tuple[str, str, bool]] = [
    ("title", "任务：给一批真实用户报告分类", False),
    ("", "", False),
    ("p", "背景", True),
    ("p", "下面是一批真实项目的用户反馈（来自两个开源 AI 工具的问题追踪器，已做脱敏处理，"
          "去掉了邮箱、链接里的个人信息）。我们需要独立的人来判断两件事：这条报告是不是在说"
          "某个东西坏了；如果是，属于哪一类。", False),
    ("p", "这份表里只有原文，没有任何自动判断结果。请按你自己的理解填，不需要猜别人怎么想。"
          "你的判断会用来衡量一次独立复核的结果，所以「和多数人不一样」本身不是错误，"
          "不一致的地方反而是最有价值的。", False),
    ("", "", False),
    ("p", "怎么判定「是不是缺陷」", True),
    ("p", "只问一件事：这条报告有没有在主张「某个功能坏了 / 行为和预期不符 / 环境里出了错」。", False),
    ("p", "算缺陷：报错、崩溃、数据不对、界面坏、配置不生效、以前能用现在不能用、"
          "某个操作得到错误结果。", False),
    ("p", "不算缺陷：功能请求（「希望支持……」「能不能加……」）、提问（「怎么才能……」）、"
          "纯讨论、经验分享、赞助/推广、只贴了一个版本号或一句无内容的描述。", False),
    ("p", "边界情况：报告里夹着功能请求但主线是在说坏了 → 算缺陷；"
          "报告说「有个小问题，顺便能不能加个功能」→ 算缺陷，类别按主问题填。", False),
    ("", "", False),
    ("p", "填写要求", True),
    ("p", "1. 只看原文。不要去网上搜这个 issue 后来的讨论，那会让你看到答案而不是判断。", False),
    ("p", "2. D 列「是不是缺陷」必填：是 / 不是 / 不确定。", False),
    ("p", "3. E 列「缺陷类别」只在 D 列填「是」时填。可以多选，用英文逗号隔开，"
          "比如 crash_or_error, data_integrity。只能填速查表里的类名，不要自己造词。", False),
    ("p", "4. F 列「理由」写一句话。填了「不确定」的必须写清卡在哪里——这一列比答案更有用。", False),
    ("p", "5. 不确定就填不确定，不要硬猜。猜出来的答案会污染统计。", False),
    ("p", "6. 不要删行、不要改 A/B/C 列。可以分几次做，随时保存。", False),
    ("p", "7. 一条报告同时有多个问题时，把主要问题填在前面。", False),
    ("", "", False),
    ("p", "大约用时", True),
    ("p", "40 条，一条 30–60 秒读加判断，整体 40–50 分钟。", False),
    ("", "", False),
    ("p", "关于原文", True),
    ("p", "原文里如果出现代码块、日志、traceback，那通常说明这是一条真实的错误报告，"
          "但代码本身不属于「类别」，你要判断的是这段代码/日志在说明什么问题。", False),
    ("p", "原文没有经过改写，可能有拼写错误、语法不通、中英混杂——这正是真实工单的样子。", False),
]

HEADER = ["编号", "来源", "原文", "是不是缺陷", "缺陷类别（逗号分隔）", "理由（一句话）"]
WIDTHS = [8, 9, 96, 12, 34, 44]

HEADER_FILL = PatternFill("solid", fgColor="E6F1FB")
SECTION_FILL = PatternFill("solid", fgColor="F1EFE8")
THIN = Side(style="thin", color="B4B2A9")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)


def _visual_width(text: str) -> int:
    """CJK glyphs occupy roughly two Latin character cells."""
    return sum(2 if ord(ch) > 127 else 1 for ch in text)


def build_instructions(ws) -> None:
    ws.column_dimensions["A"].width = 118
    ws.sheet_view.showGridLines = False
    r = 1
    for kind, text, _ in INSTRUCTIONS:
        cell = ws.cell(row=r, column=1, value=text)
        if kind == "title":
            cell.font = Font(size=15, bold=True)
            ws.row_dimensions[r].height = 26
        elif kind == "p" and text:
            cell.font = Font(size=13, bold=True) if text in {
                "背景", "怎么判定「是不是缺陷」", "填写要求", "大约用时", "关于原文"
            } else Font(size=11)
            cell.fill = SECTION_FILL if cell.font.bold else PatternFill()
            cell.alignment = Alignment(wrap_text=True, vertical="top")
            lines = max(1, -(-_visual_width(text) // 108))
            ws.row_dimensions[r].height = 17 * lines + 6
        r += 1


def build_mode_table(ws, start_row: int) -> int:
    headers = ["类名（填这个）", "什么时候算这一类", "例子"]
    widths = [22, 52, 40]
    for i, (h, w) in enumerate(zip(headers, widths), start=1):
        c = ws.cell(row=start_row, column=i, value=h)
        c.font = Font(size=11, bold=True)
        c.fill = HEADER_FILL
        c.border = BORDER
        ws.column_dimensions[get_column_letter(i)].width = w
    r = start_row + 1
    for name, when, example in MODES:
        ws.cell(row=r, column=1, value=name).font = Font(size=10, name="Consolas")
        ws.cell(row=r, column=2, value=when).font = Font(size=10)
        ws.cell(row=r, column=3, value=example).font = Font(size=10, name="Consolas", italic=True)
        for col in range(1, 4):
            ws.cell(row=r, column=col).alignment = Alignment(wrap_text=True, vertical="top")
            ws.cell(row=r, column=col).border = BORDER
        ws.row_dimensions[r].height = 32
        r += 1
    return r


def build_sheet(ws, records: list[dict], issues: dict[str, int]) -> None:
    ws.sheet_view.showGridLines = False
    for i, (h, w) in enumerate(zip(HEADER, WIDTHS), start=1):
        c = ws.cell(row=1, column=i, value=h)
        c.font = Font(size=11, bold=True)
        c.fill = HEADER_FILL
        c.border = BORDER
        c.alignment = Alignment(vertical="center", horizontal="center")
        ws.column_dimensions[get_column_letter(i)].width = w
    ws.row_dimensions[1].height = 28
    ws.freeze_panes = "A2"

    for idx, rec in enumerate(records, start=1):
        row = idx + 1
        ws.cell(row=row, column=1, value=f"r{idx:02d}")
        ws.cell(row=row, column=2, value=rec["id"].split("-")[0])
        text = rec["text"].strip()
        ws.cell(row=row, column=3, value=text)
        for col in (1, 2, 4, 5, 6):
            ws.cell(row=row, column=col).alignment = Alignment(vertical="top", wrap_text=True)
        ws.cell(row=row, column=3).alignment = Alignment(vertical="top", wrap_text=True)
        ws.cell(row=row, column=1).font = Font(size=10, name="Consolas")
        ws.cell(row=row, column=2).font = Font(size=10)
        ws.cell(row=row, column=3).font = Font(size=10)
        for col in range(1, 7):
            ws.cell(row=row, column=col).border = BORDER
        ws.row_dimensions[row].height = 92

    dv = DataValidation(type="list", formula1='"是,不是,不确定"', allow_blank=True,
                        showDropDown=False)
    dv.error = "请从下拉里选：是 / 不是 / 不确定"
    dv.errorTitle = "只能选这三项"
    ws.add_data_validation(dv)
    dv.add(f"D2:D{len(records) + 1}")

    review_note = ws.cell(row=len(records) + 3, column=1,
                          value="填完保存这个文件发回即可。不要新增/删除行。")
    review_note.font = Font(size=10, italic=True)

    issues["data_rows"] = len(records)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--holdout", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--limit", type=int, default=0, help="cap rows (0 = all)")
    args = ap.parse_args()

    records = [json.loads(line) for line in Path(args.holdout).read_text(
        encoding="utf-8").splitlines() if line.strip()]
    if args.limit:
        records = records[: args.limit]

    wb = Workbook()
    ws_readme = wb.active
    ws_readme.title = "怎么填"

    issues: dict[str, int] = {}
    build_instructions(ws_readme)
    start = ws_readme.max_row + 2
    title = ws_readme.cell(row=start, column=1, value="十类速查（E 列只能填第一列的名字）")
    title.font = Font(size=13, bold=True)
    build_mode_table(ws_readme, start + 1)

    ws_data = wb.create_sheet("待标注")
    build_sheet(ws_data, records, issues)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    wb.save(out)
    print(f"wrote {out}  rows={issues['data_rows']}  size={out.stat().st_size} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

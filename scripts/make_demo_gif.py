"""Render a short terminal demo GIF from the *real* CLI output.

Run:  python scripts/make_demo_gif.py --out assets/demo.gif

Nothing here is hand-drawn prose: the typed command is executed, and the lines
shown are parsed from the actual stdout / Markdown report produced by that run.
If the engine output changes, the GIF changes with it.

The demo runs `cte defects` on the committed fixture, so anyone who clones the
repo can reproduce every number in the image. It deliberately does NOT run on the
local issue corpus: that file is gitignored, so its counts would be unverifiable.

Line width is auto-fitted — a long command shrinks to fit instead of running off
the canvas (an earlier version rendered text past the right edge).
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent

W, H = 1000, 660
HEADER = 36
PAD = 26
FONT_SIZE = 18
LINE_H = 26
MIN_FONT = 12
HEAD_N = 13

BG = (13, 17, 23)
BAR = (22, 27, 34)
FG = (201, 209, 217)
GREEN = (126, 231, 135)
ORANGE = (255, 166, 87)
DIM = (139, 148, 158)
DOT_RED = (255, 95, 86)
DOT_YELLOW = (255, 189, 46)
DOT_GREEN = (39, 201, 63)

FONT = ImageFont.truetype("C:/Windows/Fonts/consola.ttf", FONT_SIZE)
FONT_B = ImageFont.truetype("C:/Windows/Fonts/consolab.ttf", FONT_SIZE)
FONT_T = ImageFont.truetype("C:/Windows/Fonts/consola.ttf", 15)

FIXTURE = "tests/fixtures/defect_input.jsonl"
COMMAND = f"python -m complaint_to_eval defects --input {FIXTURE} --synthetic --out out/defects"


def capture() -> tuple[list[str], list[str]]:
    """Run the CLI on the committed fixture; return (stdout_lines, report_lines)."""
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "gifdemo"
        proc = subprocess.run(
            [sys.executable, "-m", "complaint_to_eval", "defects",
             "--input", FIXTURE, "--synthetic", "--out", str(out)],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if proc.returncode != 0:
            raise SystemExit(f"defects run failed:\n{proc.stdout}\n{proc.stderr}")
        stdout = [(ln or "").rstrip() for ln in (proc.stdout or "").splitlines()]
        md = (out / "defects.md").read_text(encoding="utf-8").splitlines()
        return stdout, md


def build_lines() -> list[dict]:
    stdout, md = capture()
    counts = stdout[0] if stdout else "records=0 classified=0 candidates=0"
    note = next((l for l in stdout if l.startswith("NOTE:")), "")
    # Show `head -n HEAD_N` verbatim, then remove markdown emphasis so the
    # terminal view matches what the file actually says without ** markers.
    shown = [ln.replace("**", "").replace("`", "") for ln in md[:HEAD_N]]
    if not shown:
        shown = ["# defect-report classification"]

    lines = [
        {"k": "run", "text": COMMAND, "color": GREEN},
        {"k": "out", "text": "", "color": FG},
        {"k": "out", "text": counts, "color": FG},
        {"k": "out", "text": note, "color": DIM},
        {"k": "out", "text": "wrote out/defects/defects.json", "color": FG},
        {"k": "out", "text": "wrote out/defects/defects.md", "color": FG},
        {"k": "gap", "text": "", "color": FG},
        {"k": "run", "text": f"head -n {HEAD_N} out/defects/defects.md", "color": GREEN},
    ]
    for s in shown:
        lines.append({"k": "out", "text": s, "color": FG,
                      "bold": "Candidate cases" in s})
    return lines


def _fit_font(text: str, base: ImageFont.FreeTypeFont, bold: bool, width: int):
    """Shrink until the text fits; never let a line run off the canvas."""
    path = "C:/Windows/Fonts/consolab.ttf" if bold else "C:/Windows/Fonts/consola.ttf"
    size = base.size
    while size > MIN_FONT:
        f = ImageFont.truetype(path, size)
        if f.getlength(text) <= width:
            return f, size
        size -= 1
    return ImageFont.truetype(path, MIN_FONT), MIN_FONT


def draw_frame(visible: list[tuple[str, str, bool]], cursor_on: bool) -> Image.Image:
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, W, HEADER], radius=0, fill=BAR)
    for i, c in enumerate((DOT_RED, DOT_YELLOW, DOT_GREEN)):
        cx = 18 + i * 20
        d.ellipse([cx, 13, cx + 10, 23], fill=c)
    d.text((W / 2 - 70, 9), "complaint-to-eval", font=FONT_T, fill=DIM)

    inner = W - 2 * PAD
    y = HEADER + PAD
    for text, color, bold in visible:
        base = FONT_B if bold else FONT
        f, _size = _fit_font(text, base, bold, inner)
        d.text((PAD, y), text, font=f, fill=color)
        y += LINE_H
    if cursor_on:
        d.rectangle([PAD, y + 2, PAD + 10, y + 2 + FONT_SIZE], fill=FG)
    return img


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="assets/demo.gif")
    ap.add_argument("--fps", type=int, default=20)
    args = ap.parse_args()

    lines = build_lines()
    visible: list[tuple[str, str, bool]] = []
    frames: list[Image.Image] = []
    durations: list[int] = []
    base = int(1000 / args.fps)

    def snap(dur: int, cursor_on=True, pause_ms: int = 0):
        frames.append(draw_frame(visible, cursor_on))
        durations.append(dur + pause_ms)

    # start empty, cursor on
    visible = []
    snap(base, cursor_on=True)

    # type the first command (two characters per frame keeps the loop short)
    cmd = lines[0]["text"]
    for i in range(2, len(cmd) + 1, 2):
        partial = [("$ " + cmd[:i], GREEN, False)]
        frames.append(draw_frame(partial, cursor_on=True))
        durations.append(base)
    visible = [("$ " + cmd, GREEN, False)]
    snap(200)

    # reveal remaining lines one at a time
    for ln in lines[1:]:
        if ln["k"] == "gap":
            visible.append(("", FG, False))
            snap(120)
            continue
        if ln["k"] == "run":
            # type the second command as a new line
            cmd2 = ln["text"]
            base_visible = list(visible)
            for i in range(2, len(cmd2) + 1, 2):
                frames.append(
                    draw_frame(base_visible + [("$ " + cmd2[:i], GREEN, False)], cursor_on=True)
                )
                durations.append(base)
            visible = base_visible + [("$ " + cmd2, GREEN, False)]
            snap(240)
            continue
        color = ln["color"]
        if ln.get("bold"):
            color = ORANGE
        visible.append((ln["text"], color, ln.get("bold", False)))
        snap(420)

    # final hold + pause
    snap(1400, cursor_on=False)
    snap(2500, cursor_on=True)

    out = Path(args.out)
    if not out.is_absolute():
        out = ROOT / out
    out.parent.mkdir(parents=True, exist_ok=True)
    pal = [f.convert("P", palette=Image.ADAPTIVE, colors=64) for f in frames]
    pal[0].save(
        out,
        save_all=True,
        append_images=pal[1:],
        duration=durations,
        loop=0,
        optimize=True,
        disposal=2,
    )
    size_kb = out.stat().st_size / 1024
    print(f"wrote {out} ({size_kb:.0f} KB, {len(pal)} frames)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

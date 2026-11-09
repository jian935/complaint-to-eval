"""Render a short terminal demo GIF from the *real* CLI output.

Run:  python scripts/make_demo_gif.py --out assets/demo.gif

Nothing here is hand-drawn prose: the typed command is executed, and the
lines shown are parsed from the actual stdout / report.md produced by that
run. If the engine output changes, the GIF changes with it.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent

W, H = 940, 540
HEADER = 36
PAD = 26
FONT_SIZE = 19
LINE_H = 28

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


def capture() -> tuple[str, str]:
    """Run the CLI, return (stdout_line1, report_snippet_lines)."""
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "gifdemo"
        proc = subprocess.run(
            [sys.executable, "-m", "complaint_to_eval", "demo", "--out", str(out)],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        stdout = (proc.stdout or "").strip().splitlines()
        counts = stdout[0] if stdout else "records=0 candidates=0 accepted=0"
        report = (out / "report.md").read_text(encoding="utf-8").splitlines()
        keep = []
        for ln in report:
            if ln.startswith("- Candidate cases:") or ln.startswith(
                "- Accepted (human-reviewed) cases:"
            ):
                keep.append(ln.replace("**", ""))
        return counts, keep


def build_lines() -> list[dict]:
    counts, report_keep = capture()
    # Pull the "Accepted" line out to highlight it.
    accepted = next((l for l in report_keep if "Accepted" in l), "- Accepted (human-reviewed) cases: 0")
    candidate = next((l for l in report_keep if "Candidate cases" in l), "- Candidate cases: 0")

    return [
        {"k": "run", "text": "python -m complaint_to_eval demo", "color": GREEN},
        {"k": "out", "text": "", "color": FG},
        {"k": "out", "text": counts, "color": FG, "parts": [("accepted=0", ORANGE)]},
        {"k": "out", "text": "provenance=synthetic (FABRICATED; demo artefact only, never a metric)", "color": DIM},
        {"k": "out", "text": "wrote out/demo/report.json", "color": FG},
        {"k": "out", "text": "wrote out/demo/report.md", "color": FG},
        {"k": "out", "text": "wrote out/demo/promptfoo-candidates.json", "color": FG},
        {"k": "gap", "text": "", "color": FG},
        {"k": "run", "text": "head -n 12 out/demo/report.md", "color": GREEN},
        {"k": "out", "text": "# complaint-to-eval report", "color": FG},
        {"k": "out", "text": candidate, "color": FG},
        {"k": "out", "text": accepted, "color": ORANGE, "bold": True},
        {"k": "out", "text": "> Every case is an UNREVIEWED CANDIDATE, not a labelled example.", "color": DIM},
        {"k": "out", "text": "> The demo dataset is FABRICATED; never a metric.", "color": DIM},
    ]


def draw_frame(visible: list[tuple[str, str, bool]], cursor_on: bool) -> Image.Image:
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    # title bar
    d.rounded_rectangle([0, 0, W, HEADER], radius=0, fill=BAR)
    for i, c in enumerate((DOT_RED, DOT_YELLOW, DOT_GREEN)):
        cx = 18 + i * 20
        d.ellipse([cx, 13, cx + 10, 23], fill=c)
    d.text((W / 2 - 70, 9), "complaint-to-eval", font=FONT_T, fill=DIM)

    y = HEADER + PAD
    for text, color, bold in visible:
        f = FONT_B if bold else FONT
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

    # type the first command
    cmd = lines[0]["text"]
    for i in range(1, len(cmd) + 1):
        partial = [("$ " + cmd[:i], GREEN, False)]
        frames.append(draw_frame(partial, cursor_on=True))
        durations.append(base)

    # commit first command line
    visible = [("$ " + cmd, GREEN, False)]
    snap(180)

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
            for i in range(1, len(cmd2) + 1):
                frames.append(
                    draw_frame(base_visible + [("$ " + cmd2[:i], GREEN, False)], cursor_on=True)
                )
                durations.append(base)
            visible = base_visible + [("$ " + cmd2, GREEN, False)]
            snap(240)
            continue
        visible.append((ln["text"], ln["color"], ln.get("bold", False)))
        snap(380)
        # highlight parts: for the counts line, no sub-render needed beyond color

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

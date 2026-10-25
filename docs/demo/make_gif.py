#!/usr/bin/env python3
"""Render docs/demo/review.gif, the README demo: one review from the benchmark, replayed.

The change is the `pagination` case in bench/review_cases (a planted off-by-one). Deputy's
findings, time and cost, the repro output and the test result come from real runs; Claude's
lines are condensed. The end card shows the benchmark numbers in STATS.

    pip install pillow
    python docs/demo/make_gif.py
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = Path(__file__).resolve().parent
ICON = HERE.parent.parent / ".claude-plugin" / "icon.png"
OUT = HERE / "review.gif"

# From bench/results/2026-10-24-review-low-cap180 (bench/review_eval.py --repeats 5).
STATS = [("30/30", "planted bugs caught"), ("30/40", "clean diffs with no major flag"),
         ("28 s", "median review of a bug")]

W, H = 1200, 780
MARGIN, RADIUS, TITLE_H = 28, 16, 46
PAD_X, PAD_Y, LINE_H = 30, 22, 29
ROWS = (H - 2 * MARGIN - TITLE_H - 2 * PAD_Y) // LINE_H

BACKDROP = (242, 242, 245)
WINDOW = (255, 255, 255)
TEXT = (29, 29, 31)
DIM = (110, 110, 115)
FAINT = (174, 174, 178)
BLUE = (0, 113, 227)
GOLD = (176, 112, 0)
RED = (215, 0, 21)
GREEN = (36, 138, 61)
CODE_BG = (245, 245, 247)


def font(names: list[str], size: int) -> ImageFont.FreeTypeFont:
    for name in names:
        for folder in ("C:/Windows/Fonts", "/System/Library/Fonts", "/usr/share/fonts/truetype/dejavu"):
            path = Path(folder) / name
            if path.exists():
                return ImageFont.truetype(str(path), size)
    raise SystemExit(f"none of these fonts is installed: {names}")


MONO = font(["consola.ttf", "Menlo.ttc", "DejaVuSansMono.ttf"], 20)
MONO_BOLD = font(["consolab.ttf", "Menlo.ttc", "DejaVuSansMono-Bold.ttf"], 20)
UI = font(["segoeui.ttf", "SFNS.ttf", "DejaVuSans.ttf"], 16)
UI_BIG = font(["seguisb.ttf", "SFNS.ttf", "DejaVuSans-Bold.ttf"], 60)
UI_MID = font(["segoeui.ttf", "SFNS.ttf", "DejaVuSans.ttf"], 26)
UI_NUM = font(["seguisb.ttf", "SFNS.ttf", "DejaVuSans-Bold.ttf"], 34)
UI_SMALL = font(["segoeui.ttf", "SFNS.ttf", "DejaVuSans.ttf"], 18)


def window() -> Image.Image:
    """The empty terminal window on its backdrop, drawn once."""
    canvas = Image.new("RGB", (W, H), BACKDROP)
    box = (MARGIN, MARGIN, W - MARGIN, H - MARGIN)
    shadow = Image.new("L", (W, H), 0)
    ImageDraw.Draw(shadow).rounded_rectangle((box[0], box[1] + 8, box[2], box[3] + 8), RADIUS, 70)
    canvas.paste((205, 205, 212), mask=shadow.filter(ImageFilter.GaussianBlur(14)))
    draw = ImageDraw.Draw(canvas)
    draw.rounded_rectangle(box, RADIUS, WINDOW, outline=(222, 222, 226))
    draw.line((box[0], box[1] + TITLE_H, box[2], box[1] + TITLE_H), (232, 232, 236))
    for i, color in enumerate([(255, 95, 87), (254, 188, 46), (40, 200, 64)]):
        cx, cy = box[0] + 24 + i * 22, box[1] + TITLE_H // 2
        draw.ellipse((cx - 7, cy - 7, cx + 7, cy + 7), color)
    title = "claude  —  ~/shop-api"
    draw.text((W / 2 - draw.textlength(title, font=UI) / 2, box[1] + 13), title, DIM, font=UI)
    return canvas


BASE = window()


def screen(lines: list[list[tuple]], cursor: bool = False) -> Image.Image:
    image = BASE.copy()
    draw = ImageDraw.Draw(image)
    top = MARGIN + TITLE_H + PAD_Y
    for row, spans in enumerate(lines[-ROWS:]):
        x, y = MARGIN + PAD_X, top + row * LINE_H
        for text, color, *bold in spans:
            face = MONO_BOLD if bold else MONO
            draw.text((x, y), text, color, font=face)
            x += draw.textlength(text, font=face)
        if cursor and row == len(lines[-ROWS:]) - 1:
            draw.rectangle((x + 2, y + 2, x + 12, y + 23), TEXT)
    return image


def end_card() -> Image.Image:
    image = BASE.copy()
    draw = ImageDraw.Draw(image)
    icon = Image.open(ICON).convert("RGBA").resize((120, 120), Image.LANCZOS)
    image.paste(icon, (W // 2 - 60, 110), icon)

    def center(y: int, text: str, face, color) -> None:
        draw.text((W / 2 - draw.textlength(text, font=face) / 2, y), text, color, font=face)

    center(240, "Deputy", UI_BIG, TEXT)
    center(325, "A cheap second reviewer for Claude Code", UI_MID, DIM)
    column = (W - 2 * MARGIN) / len(STATS)
    for i, (number, label) in enumerate(STATS):
        mid = MARGIN + column * (i + 0.5)
        draw.text((mid - draw.textlength(number, font=UI_NUM) / 2, 410), number, BLUE, font=UI_NUM)
        draw.text((mid - draw.textlength(label, font=UI_SMALL) / 2, 458), label, DIM, font=UI_SMALL)
    command = "claude plugin install deputy@deputy"
    width = draw.textlength(command, font=MONO)
    box = (W / 2 - width / 2 - 22, 545, W / 2 + width / 2 + 22, 595)
    draw.rounded_rectangle(box, 10, CODE_BG, outline=(226, 226, 230))
    draw.text((box[0] + 22, 558), command, TEXT, font=MONO)
    center(640, "github.com/alimohammadiamirhossein/deputy", UI_SMALL, FAINT)
    return image


def build() -> list[tuple[Image.Image, int]]:
    frames: list[tuple[Image.Image, int]] = []
    lines: list[list[tuple]] = []

    def show(ms: int, cursor: bool = False) -> None:
        frames.append((screen(lines, cursor), ms))

    def add(*spans: tuple, ms: int = 220) -> None:
        lines.append(list(spans))
        show(ms)

    prompt = "/deputy:review page_count(): a partial last page counts, 0 items is 0 pages"
    lines.append([("> ", DIM)])
    show(500, cursor=True)
    for end in range(3, len(prompt) + 3, 3):
        lines[-1] = [("> ", DIM), (prompt[:end], TEXT)]
        show(35, cursor=True)
    show(500)

    lines.append([])
    add(("● ", TEXT), ("Reviewing the uncommitted change", TEXT), ("  pager.py +8", DIM), ms=300)
    add(("  + def page_count(total, per_page=20):", GREEN), ms=120)
    add(("  +     ...", GREEN), ms=120)
    add(("  +     return total // per_page + 1", GREEN), ms=400)
    lines.append([])
    header = [("● ", GOLD), ("deputy · review", GOLD, True),
              ("  2 reviewers in parallel · DeepSeek V4.1 Flash", DIM)]
    lines.append(header)
    for seconds in (1, 4, 8, 12, 17, 21, 24, 26):
        lines.append([("  └ reviewing", DIM), ("." * (seconds % 3 + 1), DIM), (f"  {seconds} s", FAINT)])
        show(140)
        lines.pop()
    add(("  └ correctness  ", DIM), ("major", RED, True), ("     pager.py:20", BLUE), ms=260)
    add(("      page_count(20) == 2 and page_count(0) == 1; the spec says 1 and 0", TEXT), ms=200)
    add(("      repro ", DIM), ('python -c "...print(page_count(0), page_count(20), page_count(40))"', TEXT),
        ms=180)
    add(("      fix   ", DIM), ("return (total + per_page - 1) // per_page", TEXT), ms=260)
    add(("  └ edge cases   ", DIM), ("critical", RED, True), ("  pager.py:20", BLUE),
        ("   same bug, found on its own", DIM), ms=260)
    add(("    26 s · ", DIM), ("$0.0010", TEXT, True), (" for both reviewers", DIM), ms=900)

    lines.append([])
    add(("● ", TEXT), ("Both reviewers point at line 20. Checking it before changing anything.", TEXT),
        ms=500)
    add(("● ", BLUE), ("Bash", BLUE, True), ("  python -c \"...print(page_count(0), page_count(20), "
                                             "page_count(40))\"", DIM), ms=450)
    add(("  └ ", DIM), ("1 2 3", TEXT, True), ("    expected 0 1 2: confirmed", DIM), ms=800)
    add(("● ", BLUE), ("Update", BLUE, True), ("  pager.py, test_pager.py: ceiling division, tests for 0"
                                               " and exact pages", DIM), ms=450)
    add(("● ", BLUE), ("Bash", BLUE, True), ("  python -m pytest -q", DIM), ms=350)
    add(("  └ ", DIM), ("4 passed in 0.01s", GREEN, True), ms=600)
    lines.append([])
    add(("● ", TEXT), ("Fixed. Deputy caught it for a tenth of a cent; I confirmed it first.", TEXT),
        ms=2600)
    frames.append((end_card(), 4200))
    return frames


def main() -> None:
    frames = build()
    # One shared palette keeps colors stable from frame to frame and avoids dithering noise.
    sample = Image.new("RGB", (W, H * 2))
    sample.paste(frames[-2][0], (0, 0))
    sample.paste(frames[-1][0], (0, H))
    palette = sample.quantize(colors=128, method=Image.Quantize.MEDIANCUT)
    images = [image.quantize(palette=palette, dither=Image.Dither.NONE) for image, _ in frames]
    images[0].save(OUT, save_all=True, append_images=images[1:], loop=0, optimize=True,
                   duration=[ms for _, ms in frames])
    seconds = sum(ms for _, ms in frames) / 1000
    print(f"{OUT}: {len(frames)} frames, {seconds:.1f} s, {OUT.stat().st_size / 1e6:.2f} MB")


if __name__ == "__main__":
    main()

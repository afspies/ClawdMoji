#!/usr/bin/env python3
"""Render the recovered 12x8 Clawd pixel grid as a crisp Slack emoji.

Slack emoji target: 128x128 PNG, transparent background, integer-pixel cells
so the pixel-art stays razor sharp at any display size.
"""
import sys
from pathlib import Path
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from shared.clawd import ART, GX, GY, CLAWD_RGB, EYE_RGB

OUT = Path(__file__).resolve().parent; OUT.mkdir(exist_ok=True)

ORANGE = CLAWD_RGB + (255,)    # #DA7758  (sampled from source)
EYE    = EYE_RGB + (255,)
TRANSP = (0, 0, 0, 0)

CANVAS = 128
CELL = min(CANVAS // GX, CANVAS // GY)   # = 10 -> art 120x80
artw, arth = GX * CELL, GY * CELL
ox, oy = (CANVAS - artw) // 2, (CANVAS - arth) // 2

img = Image.new("RGBA", (CANVAS, CANVAS), TRANSP)
px = img.load()
for j, row in enumerate(ART):
    for i, ch in enumerate(row):
        color = {"#": ORANGE, "O": EYE}.get(ch)
        if not color:
            continue
        for dy in range(CELL):
            for dx in range(CELL):
                px[ox + i*CELL + dx, oy + j*CELL + dy] = color

img.save(OUT / "clawd_emoji.png")
print(f"wrote {OUT.name}/clawd_emoji.png  {CANVAS}x{CANVAS}  cell={CELL}px  art={artw}x{arth}")

# also a tight, exactly-proportioned version (no padding) for reference
tight = Image.new("RGBA", (artw, arth), TRANSP)
tp = tight.load()
for j, row in enumerate(ART):
    for i, ch in enumerate(row):
        color = {"#": ORANGE, "O": EYE}.get(ch)
        if color:
            for dy in range(CELL):
                for dx in range(CELL):
                    tp[i*CELL+dx, j*CELL+dy] = color
tight.save(OUT / "clawd_emoji_tight.png")
print(f"wrote {OUT.name}/clawd_emoji_tight.png  {artw}x{arth}")

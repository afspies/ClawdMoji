#!/usr/bin/env python3
"""Render assets/social-preview.png (1280x640) — GitHub's link-card image.

Dark card, big title, and the full cast in a row (GIF first-frames /
PNGs upscaled with nearest-neighbour so the pixels stay chunky).
Upload by hand: repo Settings -> General -> Social preview (no API for it).
"""
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "social-preview.png"
W, H = 1280, 640
BG = (22, 20, 31)          # docs-site background
CARD = (32, 29, 43)
CLAWD = (218, 119, 88)
INK = (240, 236, 228)
DIM = (155, 147, 169)


def font(size, bold=False):
    for cand in [
        "/System/Library/Fonts/Menlo.ttc",
        "/System/Library/Fonts/Monaco.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"
        if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    ]:
        try:
            return ImageFont.truetype(cand, size, index=1 if bold and cand.endswith(".ttc") else 0)
        except OSError:
            continue
    return ImageFont.load_default(size)


metas = []
for meta_path in sorted((ROOT / "emoji").glob("*/meta.json")):
    if meta_path.parent.name.startswith("_"):
        continue
    m = json.loads(meta_path.read_text())
    m["path"] = meta_path.parent / m["file"]
    metas.append(m)
metas.sort(key=lambda m: m["order"])

img = Image.new("RGB", (W, H), BG)
d = ImageDraw.Draw(img)

d.text((W // 2, 96), "ClawdMoji", font=font(88, bold=True), fill=CLAWD, anchor="mm")
d.text((W // 2, 172), "pixel-art Slack emoji of Clawd — generated with Python + math",
       font=font(30), fill=INK, anchor="mm")
d.text((W // 2, 218), "no image editor involved", font=font(26), fill=DIM, anchor="mm")

# the cast: 8 sprites at 128 px in a centred row on a soft card
n = len(metas)
cell, gap = 128, 14
row_w = n * cell + (n - 1) * gap
x0, y0 = (W - row_w) // 2, 300
d.rounded_rectangle([x0 - 28, y0 - 28, x0 + row_w + 28, y0 + cell + 28],
                    radius=24, fill=CARD)
for i, m in enumerate(metas):
    im = Image.open(m["path"])
    im.seek(0)
    im = im.convert("RGBA")
    if im.size != (cell, cell):
        im = im.resize((cell, cell), Image.NEAREST)
    img.paste(im, (x0 + i * (cell + gap), y0), im)

d.text((W // 2, y0 + cell + 84), "github.com/afspies/ClawdMoji  ·  add your own — one folder, one render.py",
       font=font(26), fill=DIM, anchor="mm")

OUT.parent.mkdir(exist_ok=True)
img.save(OUT)
print(f"wrote {OUT.relative_to(ROOT)} ({OUT.stat().st_size / 1024:.0f} KB)")

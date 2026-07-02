#!/usr/bin/env python3
"""Starter template for a new Clawd variant.

Copy this folder, rename it, and start hacking:

    cp -r emoji/_template emoji/myidea
    python3 emoji/myidea/render.py     # -> a bobbing Clawd, ready to mutate

It renders the authentic Clawd sprite on the full 128 grid with a gentle
(seamlessly looping) bob — the smallest thing that is already a valid emoji.
Everything you'd customise is marked with `EDIT ME`.

House rules (CI enforces the first two):
  * 128x128, GIF <= 128 KB (Slack's cap).
  * the loop must be seamless: drive motion with sin/cos of 2*pi*f/F so
    frame 0 and frame F match exactly.
  * stay authentic to Clawd — build ON the shared ART grid, don't reshape him.
"""
import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from shared.clawd import ART, CLAWD_RGB, EYE_RGB, WHITE_RGB, border_mask, pen_disk

OUT = Path(__file__).resolve().parent
NAME = "clawd_template"          # EDIT ME: output filename stem

N = 128                          # canvas (fixed: Slack emoji size)
F = 16                           # frames per loop
DUR = 90                         # ms per frame
SCALE = 9                        # sprite cell size -> 12*9 x 8*9 = 108x72 px

# ---- palette (P-mode GIF: index 0 is transparent) --------------------------
COLORS = [
    (0, 0, 0),                   # 0: transparent slot
    WHITE_RGB,                   # 1: outline
    CLAWD_RGB,                   # 2: body
    EYE_RGB,                     # 3: eyes
    # EDIT ME: append your colours here and name their indices below
]
T, OUTLINE, BODY, EYE = 0, 1, 2, 3
PAL = bytes([c for rgb in COLORS for c in rgb] + [0] * (768 - 3 * len(COLORS)))


def sprite():
    """Rasterise the shared ART grid -> index grid (one int per pixel)."""
    h, w = len(ART) * SCALE, len(ART[0]) * SCALE
    g = np.zeros((h, w), dtype=np.uint8)
    for r, row in enumerate(ART):
        for c, ch in enumerate(row):
            if ch == ".":
                continue
            g[r * SCALE:(r + 1) * SCALE, c * SCALE:(c + 1) * SCALE] = (
                EYE if ch == "O" else BODY
            )
    return g


SPRITE = sprite()


def compose(f):
    """One frame. EDIT ME: this is where your idea lives."""
    g = np.zeros((N, N), dtype=np.uint8)

    # seamless motion: any sin/cos of 2*pi*f/F loops perfectly
    ph = 2 * np.pi * f / F
    bob = round(2 * np.sin(ph))                       # EDIT ME: motion

    sh, sw = SPRITE.shape
    y0 = (N - sh) // 2 + bob
    x0 = (N - sw) // 2
    region = g[y0:y0 + sh, x0:x0 + sw]
    region[SPRITE != 0] = SPRITE[SPRITE != 0]

    # Clawd's trademark 2 px white outline
    body = g != 0
    g[border_mask(body, pen_disk(2))] = OUTLINE
    return g


def save():
    frames = []
    for f in range(F):
        g = compose(f)
        im = Image.frombytes("P", (N, N), g.tobytes())
        im.putpalette(PAL)
        frames.append(im)

    still = OUT / f"{NAME}_still.png"
    frames[0].convert("RGBA").save(still)

    gif = OUT / f"{NAME}.gif"
    frames[0].save(
        gif, save_all=True, append_images=frames[1:], duration=DUR, loop=0,
        transparency=T, disposal=2, optimize=False,
    )
    kb = gif.stat().st_size / 1024
    assert kb <= 128, f"{gif.name} is {kb:.0f} KB — over Slack's 128 KB cap"
    print(f"{NAME}: {F} frames @ {DUR}ms, gif={kb:.0f} KB")


if __name__ == "__main__":
    save()

#!/usr/bin/env python3
"""'Clawd Life' -- the classic Deal With It, starring Clawd.

Pixel sunglasses gravity-drop from off-screen, slam onto Clawd's eyes (one
frame of camera shake on impact), and GTA-style 'CLAWD LIFE' text stamps in
underneath. He holds the pose while a glint sweeps across the lenses, then the
shades yoink back up off-screen and the loop breathes for a beat before the
next drop.

Timeline (F = 36 @ 100 ms):
  f0-1    empty beat -- deadpan Clawd, nothing suspects a thing
  f2-12   shades fall with quadratic ease-in (gravity), landing at f12
  f12     impact: whole sprite shakes down 1 px
  f13-14  1-px bounce and settle
  f15-16  'CLAWD LIFE' stamps in (4 px overshoot, 1 px rebound)
  f15-30  the hold; glint sweeps the lenses f20-27
  f31-33  anticipation dip, then the shades rocket back off-screen
  f34-35  empty again -- wraps seamlessly to f0

The text is a hand-drawn Pricedown-ish slab font (5x8 cells, doubled to
10x16 px): white fill, 1 px black outline, 2 px drop shadow -- the GTA logo
treatment. It's drawn after the white-outline pass so Clawd's sacred 2 px
outline never bleeds onto the letters.
"""
import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from shared.clawd import ART, CLAWD_RGB, EYE_RGB, WHITE_RGB, border_mask, pen_disk, pen_square

OUT = Path(__file__).resolve().parent
NAME = "clawd_dealwithit"

N = 128                          # canvas (fixed: Slack emoji size)
F = 36                           # frames per loop
DUR = 100                        # ms per frame
SCALE = 10                       # 12x8 art -> 120x80: full canvas width

# ---- palette (P-mode GIF: index 0 is transparent) --------------------------
COLORS = [
    (0, 0, 0),                   # 0 transparent slot
    WHITE_RGB,                   # 1 outline
    CLAWD_RGB,                   # 2 body
    EYE_RGB,                     # 3 eyes
    (22, 22, 26),                # 4 shades (near-black, reads vs the eyes)
    (208, 224, 240),             # 5 lens glint
    (255, 255, 255),             # 6 text fill
    (0, 0, 0),                   # 7 text outline + drop shadow
]
T, OUTLINE, BODY, EYE, SHADES, GLINT, TEXT, TEXT_DK = range(8)
PAL = bytes([c for rgb in COLORS for c in rgb] + [0] * (768 - 3 * len(COLORS)))

# ---- layout ----------------------------------------------------------------
SH, SW = 8 * SCALE, 12 * SCALE           # sprite 80 x 120
Y0, X0 = (N - SH) // 2, (N - SW) // 2    # 24, 4

BAR_X0, BAR_X1 = 25, 102                 # top bar spans the head, ear to ear
LENSES = [(30, 48), (80, 98)]            # x-ranges; centred on the eye cells
BAR_H = 3                                # bar rows gy .. gy+2
LENS_H = 10                              # lens rows gy+3 .. gy+12
REST = 31                                # gy at rest: lenses cover the eyes exactly

# glasses y per frame (None = off-screen); gravity in, rocket out
GY = [None, None]                                        # f0-1  empty beat
GY += [-17 + round(48 * ((f / 10) ** 2)) for f in range(11)]  # f2-12 fall -17 -> 31
GY += [REST - 2, REST]                                   # f13-14 bounce, settle
GY += [REST] * 16                                        # f15-30 the hold
GY += [REST + 2, 16, -6, None, None]                     # f31-35 dip, yoink, gone
assert len(GY) == F and GY[0] is None                    # wraps to f0 exactly

SHAKE = {12: 1}                          # impact frame: everything jolts down 1 px
TEXT_ON = range(15, 31)                  # frames with 'CLAWD LIFE' visible
TEXT_DY = {15: -4, 16: 1}                # stamp overshoot, rebound
GLINT_F0, GLINT_STEP = 20, 4             # glint sweep start frame / px per frame

# ---- Pricedown-ish slab font: 5x8 cells (W is 7), doubled to 10x16 px ------
FONT = {
    "C": [".XXXX",
          "XXXXX",
          "XX...",
          "XX...",
          "XX...",
          "XX...",
          "XXXXX",
          ".XXXX"],
    "L": ["XX...",
          "XX...",
          "XX...",
          "XX...",
          "XX...",
          "XX...",
          "XXXXX",
          "XXXXX"],
    "A": [".XXX.",
          "XXXXX",
          "XX.XX",
          "XX.XX",
          "XXXXX",
          "XXXXX",
          "XX.XX",
          "XX.XX"],
    "W": ["XX...XX",
          "XX...XX",
          "XX...XX",
          "XX.X.XX",
          "XX.X.XX",
          "XX.X.XX",
          "XXXXXXX",
          ".XX.XX."],
    "D": ["XXXX.",
          "XXXXX",
          "XX.XX",
          "XX.XX",
          "XX.XX",
          "XX.XX",
          "XXXXX",
          "XXXX."],
    "I": ["XXX"] * 8,
    "F": ["XXXXX",
          "XXXXX",
          "XX...",
          "XXXX.",
          "XXXX.",
          "XX...",
          "XX...",
          "XX..."],
    "E": ["XXXXX",
          "XXXXX",
          "XX...",
          "XXXX.",
          "XXXX.",
          "XX...",
          "XXXXX",
          "XXXXX"],
    " ": ["..."] * 8,
}


def text_mask(s, scale=2):
    """Render `s` into a bool mask, `scale`x the 8-row font, 1-cell tracking."""
    rows = ["".join(FONT[ch][r] + "." for ch in s)[:-1] for r in range(8)]
    base = np.array([[c == "X" for c in row] for row in rows])
    return np.kron(base, np.ones((scale, scale), dtype=bool))


BANNER = text_mask("CLAWD LIFE")                    # 16 x 110
TY, TX = 108, (N - BANNER.shape[1]) // 2            # sits just under his legs


def put_mask(g, mask, y0, x0, color):
    """Stamp a bool mask at (y0, x0), clipped to the canvas."""
    h, w = mask.shape
    ys, xs = max(0, -y0), max(0, -x0)
    ye, xe = min(h, N - y0), min(w, N - x0)
    if ys >= ye or xs >= xe:
        return
    view = g[y0 + ys:y0 + ye, x0 + xs:x0 + xe]
    view[mask[ys:ye, xs:xe]] = color


def sprite():
    g = np.zeros((SH, SW), dtype=np.uint8)
    for r, row in enumerate(ART):
        for c, ch in enumerate(row):
            if ch != ".":
                g[r * SCALE:(r + 1) * SCALE, c * SCALE:(c + 1) * SCALE] = (
                    EYE if ch == "O" else BODY
                )
    return g


SPRITE = sprite()


def paint_glasses(g, gy):
    """Bar + two lenses with a stepped pixel-shade bottom edge, clipped."""
    def rect(y0, y1, x0, x1):
        g[max(0, y0):max(0, y1 + 1), x0:x1 + 1] = SHADES

    rect(gy, gy + BAR_H - 1, BAR_X0, BAR_X1)
    for x0, x1 in LENSES:
        rect(gy + BAR_H, gy + BAR_H + LENS_H - 3, x0, x1)          # body
        rect(gy + BAR_H + LENS_H - 2, gy + BAR_H + LENS_H - 2, x0 + 2, x1 - 2)
        rect(gy + BAR_H + LENS_H - 1, gy + BAR_H + LENS_H - 1, x0 + 4, x1 - 4)


def paint_glint(g, gy, p):
    """A '/' light stripe at diagonal offset p, only over lens pixels."""
    for x0, x1 in LENSES:
        for dy in range(LENS_H):
            y = gy + BAR_H + dy
            x = x0 + p - dy
            for dx in (0, 1):
                if 0 <= y < N and x0 <= x + dx <= x1 and g[y, x + dx] == SHADES:
                    g[y, x + dx] = GLINT


def paint_banner(g, dy):
    """GTA logo treatment: 2 px drop shadow, 1 px black outline, white fill."""
    shadow = np.zeros((N, N), dtype=bool)
    put_mask(shadow, BANNER, TY + dy + 2, TX + 2, True)
    body = np.zeros((N, N), dtype=bool)
    put_mask(body, BANNER, TY + dy, TX, True)
    g[shadow & ~body] = TEXT_DK
    g[border_mask(body, pen_square(1))] = TEXT_DK
    g[body] = TEXT


def compose(f):
    g = np.zeros((N, N), dtype=np.uint8)
    jolt = SHAKE.get(f, 0)

    region = g[Y0 + jolt:Y0 + jolt + SH, X0:X0 + SW]
    region[SPRITE != 0] = SPRITE[SPRITE != 0]

    if GY[f] is not None:
        gy = GY[f] + jolt
        paint_glasses(g, gy)
        if GLINT_F0 <= f < GLINT_F0 + 8:
            paint_glint(g, gy, -2 + GLINT_STEP * (f - GLINT_F0))

    g[border_mask(g != 0, pen_disk(2))] = OUTLINE                  # sacred 2 px

    if f in TEXT_ON:
        paint_banner(g, TEXT_DY.get(f, 0))
    return g


def save():
    frames = []
    for f in range(F):
        im = Image.frombytes("P", (N, N), compose(f).tobytes())
        im.putpalette(PAL)
        frames.append(im)

    frames[24].convert("RGBA").save(OUT / f"{NAME}_still.png")     # mid-hold
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

#!/usr/bin/env python3
"""'Definitely Not Clawd' -- Clawd in the classic novelty disguise: round black
glasses, a silly semi-realistic flesh nose hanging off the bridge, and a bushy
moustache. Nobody suspects a thing.

The disguise itself is a static overlay on the authentic sprite; what animates
is the *acting*:

  pupils     : Clawd's eyes dart left, hold, dart right, hold -- the shifty
               glance of someone who is definitely not who you think. The eyes
               are drawn as pupils inside the lenses (the 'O' cells become face
               so the lenses have something to sit on).
  eyebrows   : big bushy brows above the frames do the Groucho waggle (two
               bounces per loop).
  moustache  : slides one pixel with the gaze, like a nervous sniff.

Rendered on the full 128 grid at SCALE=10 — Clawd spans the full canvas width
(120 px of sprite + the 2 px outline each side). Seamless by construction: the
dart schedule is a hand-authored list of length F that starts and ends at 0,
and the brow waggle is a cos of 4*pi*f/F.
"""
import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from shared.clawd import ART, CLAWD_RGB, WHITE_RGB, border_mask, pen_disk

OUT = Path(__file__).resolve().parent
NAME = "clawd_notclawd"

N = 128                          # canvas (fixed: Slack emoji size)
F = 24                           # frames per loop
DUR = 100                        # ms per frame
SCALE = 10                       # 12x8 art -> 120x80: full canvas width

# ---- palette (P-mode GIF: index 0 is transparent) --------------------------
COLORS = [
    (0, 0, 0),                   # 0  transparent slot
    WHITE_RGB,                   # 1  outline
    CLAWD_RGB,                   # 2  body
    (0, 0, 0),                   # 3  pupils
    (32, 30, 36),                # 4  glasses frame (near-black)
    (245, 190, 158),             # 5  nose flesh (paler than Clawd: it's plastic)
    (206, 136, 106),             # 6  nose shading
    (255, 222, 196),             # 7  nose highlight
    (96, 50, 40),                # 8  nostrils
    (46, 32, 26),                # 9  moustache / brows (dark)
    (94, 66, 46),                # 10 moustache strands (light)
    (225, 232, 240),             # 11 lens glint
]
(T, OUTLINE, BODY, PUPIL, FRAME, NOSE, NOSE_S, NOSE_H,
 NOSTRIL, MUST, MUST_H, GLINT) = range(12)
PAL = bytes([c for rgb in COLORS for c in rgb] + [0] * (768 - 3 * len(COLORS)))

# ---- layout ----------------------------------------------------------------
SH, SW = 8 * SCALE, 12 * SCALE   # sprite 72 x 108
Y0, X0 = (N - SH) // 2, (N - SW) // 2

EY = Y0 + 1 * SCALE + SCALE / 2          # eye row centre (ART row 1)
EXL = X0 + 3 * SCALE + SCALE / 2         # left eye centre  (ART col 3)
EXR = X0 + 8 * SCALE + SCALE / 2         # right eye centre (ART col 8)
NCX = (EXL + EXR) / 2                    # nose centreline

LENS_R = 12                      # lens outer radius
LENS_IN = 8.5                    # lens inner radius (thick ring reads at 32 px)
BULB = (int(EY) + 20, NCX)       # nose-bulb centre
BULB_R = 10.5

# ---- acting schedules (length F, wrap to frame 0 exactly) -------------------
# shifty glance: centre .. dart left, hold .. sweep right, hold .. back
DART = [0, 0, 0, -1, -3, -4, -4, -4, -4, -4, -3, -1,
        0, 1, 3, 4, 4, 4, 4, 4, 3, 1, 0, 0]
assert len(DART) == F and DART[0] == 0
LIFT = [round(1.5 * (1 - math.cos(4 * math.pi * f / F))) for f in range(F)]
MDX  = [d // 3 if d >= 0 else -((-d) // 3) for d in DART]   # sniff: -1/0/+1


def fill_disk(g, cy, cx, r, color, only_on=None):
    """Paint every integer pixel inside the circle. Iterating pixels (not
    offsets) matters: rounding a fractional centre per-offset skips columns
    whenever cx lands on .5 (banker's rounding), leaving striped disks."""
    for y in range(int(math.floor(cy - r)), int(math.ceil(cy + r)) + 1):
        for x in range(int(math.floor(cx - r)), int(math.ceil(cx + r)) + 1):
            if (y - cy) ** 2 + (x - cx) ** 2 <= r * r:
                if 0 <= y < N and 0 <= x < N and (only_on is None or g[y, x] in only_on):
                    g[y, x] = color


# =============================================================================
# static base: body + nose + glasses (pupils / brows / moustache move)
# =============================================================================
def build_base():
    g = np.zeros((N, N), dtype=np.uint8)

    # authentic sprite; the eye cells become face so the lenses sit on skin
    for r, row in enumerate(ART):
        for c, ch in enumerate(row):
            if ch != ".":
                g[Y0 + r * SCALE:Y0 + (r + 1) * SCALE,
                  X0 + c * SCALE:X0 + (c + 1) * SCALE] = BODY

    # --- the silly semi-realistic nose --------------------------------------
    # tapering wedge from the glasses bridge down into a big round bulb
    for y in range(int(EY) + 1, BULB[0] + 1):
        t = (y - EY - 1) / (BULB[0] - EY - 1)
        hw = 4 + 5.5 * t
        for x in range(int(round(NCX - hw)), int(round(NCX + hw)) + 1):
            g[y, x] = NOSE
    fill_disk(g, BULB[0], BULB[1], BULB_R, NOSE)
    fill_disk(g, BULB[0] + 3, BULB[1] - BULB_R, 3, NOSE)           # nose wings
    fill_disk(g, BULB[0] + 3, BULB[1] + BULB_R, 3, NOSE)
    # shading: the bulb's lower-right catches the shadow
    ys, xs = np.nonzero(g == NOSE)
    for y, x in zip(ys, xs):
        if y > EY + 11 and (x - BULB[1]) + 0.8 * (y - BULB[0]) > 8.5:
            g[y, x] = NOSE_S
    for y in range(int(EY) + 3, int(EY) + 15):                     # glossy ridge
        for x in (int(NCX) - 2, int(NCX) - 1):
            g[y, x] = NOSE_H
    fill_disk(g, BULB[0] - 4.5, BULB[1] - 4, 2.4, NOSE_H)          # bulb shine
    for s in (-1, 1):                                              # nostrils
        bx = int(round(BULB[1] + s * 5.5))                         # anchor once
        for dx in (-1, 0, 1):
            for dy in (0, 1):
                g[BULB[0] + 4 + dy, bx + dx] = NOSTRIL

    # --- glasses: two rings + a bridge, drawn over the nose root -------------
    for ex in (EXL, EXR):
        y0, y1 = int(EY - LENS_R) - 1, int(EY + LENS_R) + 2
        x0, x1 = int(ex - LENS_R) - 1, int(ex + LENS_R) + 2
        for y in range(y0, y1):
            for x in range(x0, x1):
                d2 = (y - EY) ** 2 + (x - ex) ** 2
                if LENS_IN ** 2 <= d2 <= LENS_R ** 2:
                    g[y, x] = FRAME
        for gy, gx in ((-6, -4), (-5, -5), (-4, -6)):              # lens glint
            g[int(EY + gy), int(ex + gx)] = GLINT
    for y in range(int(EY) - 1, int(EY) + 2):                      # bridge bar
        for x in range(int(EXL + LENS_IN), int(EXR - LENS_IN) + 1):
            if g[y, x] != NOSE:                                    # nose root wins
                g[y, x] = FRAME
    return g


BASE = build_base()


# =============================================================================
# the moving parts
# =============================================================================
def draw_pupils(g, dx):
    """Square-ish pupils (clipped corners) darting inside the lenses; painted
    only over face pixels so they can never spill onto the frames."""
    for ex in (EXL, EXR):
        cy, cx = int(EY), int(round(ex + dx))
        for py in range(cy - 3, cy + 4):
            for px in range(cx - 3, cx + 4):
                if abs(py - cy) + abs(px - cx) <= 5 and g[py, px] == BODY:
                    g[py, px] = PUPIL


def draw_brows(g, lift):
    """Big bushy brows arched above the frames, doing the Groucho waggle."""
    base_y = int(EY - LENS_R - 2) - lift
    for ex in (EXL, EXR):
        for dx in range(-12, 13):
            arch = round(3 * (1 - (dx / 12) ** 2))
            top = base_y - arch
            depth = 5 + (1 if dx % 3 == 0 else 0)                  # ragged edge
            for k in range(depth):
                y, x = top + k, int(ex) + dx
                if 0 <= y < N and 0 <= x < N:
                    g[y, x] = MUST


def draw_moustache(g, mdx):
    """A bushy moustache drooping from under the nose bulb; slides a pixel
    with the gaze like a nervous sniff."""
    cx = NCX + mdx
    for s in (-1, 1):
        for i in range(22):
            u = i / 21
            y = BULB[0] + 12 + 4 * u ** 2
            x = cx + s * (1 + 24 * u)
            fill_disk(g, y, x, 6 - 2.7 * u, MUST)
    for s in (-1, 1):                                              # lit strands
        for i in range(3, 17, 4):
            u = i / 21
            y = int(round(BULB[0] + 7 + 4 * u ** 2))
            x = int(round(cx + s * (1 + 24 * u)))
            if g[y + 1, x] == MUST:
                g[y + 1, x] = MUST_H


def compose(f):
    g = BASE.copy()
    draw_moustache(g, MDX[f])
    draw_pupils(g, DART[f])
    draw_brows(g, LIFT[f])
    g[border_mask(g != 0, pen_disk(2))] = OUTLINE                  # sacred 2 px
    return g


def save():
    frames = []
    for f in range(F):
        im = Image.frombytes("P", (N, N), compose(f).tobytes())
        im.putpalette(PAL)
        frames.append(im)

    frames[7].convert("RGBA").save(OUT / f"{NAME}_still.png")      # mid-glance
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

#!/usr/bin/env python3
"""'Down Under' Clawd -- Clawd in the Southern Hemisphere, so of course he's
upside down: dangling legs-up under a night sky while the Southern Cross
twinkles behind him. A full opaque scene (like bugcatcher) so the stars read
on any Slack theme:

  sky    : deep navy with a scatter of small twinkling background stars.
  crux   : the five stars of the Southern Cross (as on the Australian flag --
           alpha at the bottom, beta left, gamma top, delta right, little
           epsilon off-centre), drawn as 4-pointed stars that twinkle.
  Clawd  : the authentic sprite rotated 180 degrees (full 2px white outline),
           swaying like a slow pendulum about his leg-tips with a tiny bob.

Seamless by construction: the sway is sin(2*pi*f/F), the bob is
cos(2*pi*f/F), and every star's twinkle is sin(2*pi*k*f/F + phase) with
integer k -- all equal at f=0 and f=F. Outputs the still + gif.
"""
import math
import sys
from pathlib import Path
import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from shared.clawd import ART, border_mask, pen_disk

OUT = Path(__file__).resolve().parent; OUT.mkdir(exist_ok=True)

N = 128

# ---- palette ----------------------------------------------------------
COLORS = [
    (0, 0, 0),          # 0  unused (kept so index 0 stays "nothing" while drawing)
    (218, 119, 88),     # 1  CLAWD body  #DA7758
    (0, 0, 0),          # 2  eye
    (255, 255, 255),    # 3  white outline / bright star
    (16, 24, 58),       # 4  night sky
    (10, 16, 42),       # 5  sky, darker top band
    (96, 110, 160),     # 6  dim star
    (170, 184, 226),    # 7  mid star
    (247, 199, 72),     # 8  gold star core sparkle
]
T, CLAWD, EYE, WHITE, SKY, SKY_D, STAR_DIM, STAR_MID, GOLD = range(9)
pal_bytes = bytes([c for rgb in COLORS for c in rgb] + [0]*(768 - 3*len(COLORS)))

# ---- timing / motion --------------------------------------------------
F    = 16          # frames in the loop
DUR  = 100         # ms/frame
SWAY = 3.0         # pendulum sway amplitude (degrees)
BOB  = 1.5         # vertical bob (px)

# ---- the Southern Cross (flag layout, roughly to proportion) -----------
# (y, x, size, twinkle-phase) -- size is the cross-arm length in px
CRUX = [
    (14, 22, 4, 0.0),    # gamma  (top)
    (56, 20, 5, 1.3),    # alpha  (bottom, the brightest)
    (32, 8, 4, 2.6),     # beta   (left)
    (28, 40, 4, 3.9),    # delta  (right)
    (44, 26, 2, 5.2),    # epsilon (the little fifth star)
]
# background twinkle scatter: (y, x, phase)
BGSTARS = [
    (8, 60, 0.4), (20, 118, 1.7), (46, 122, 3.1), (6, 100, 2.2),
    (74, 6, 4.4), (58, 44, 0.9), (108, 10, 3.8), (72, 120, 1.2),
    (30, 104, 5.5), (72, 14, 2.9), (124, 12, 1.9), (34, 62, 4.9),
]

# ---- Clawd, rotated 180 -----------------------------------------------
SCALE = 9                                   # 12x8 art -> 108x72
SX, SY = 12*SCALE, 8*SCALE


def build_body():
    """The sprite rotated 180 degrees (legs up), with the white outline."""
    pad = 4
    A = np.zeros((SY + 2*pad, SX + 2*pad), dtype=np.uint8)
    for j, row in enumerate(ART):
        for i, ch in enumerate(row):
            if ch == ".":
                continue
            A[pad+j*SCALE:pad+(j+1)*SCALE, pad+i*SCALE:pad+(i+1)*SCALE] = \
                EYE if ch == "O" else CLAWD
    A = A[::-1, ::-1].copy()                # 180-degree rotation
    A[border_mask(A > 0, pen_disk(2))] = WHITE
    return A


BODY = build_body()
# pendulum pivot: between the (now upward) leg tips, top-centre of the sprite
PIVOT = (4, BODY.shape[1]//2)
# world position of the pivot -- body hanging low and right of centre; only
# his narrow leg-half rises past mid-frame, so the Cross keeps clear sky on
# the upper-left
WPY, WPX = 50, 68


def _center_on(A, cy, cx):
    H, W = A.shape
    py, px = max(cy, H-1-cy), max(cx, W-1-cx)
    out = np.zeros((2*py+1, 2*px+1), dtype=np.uint8)
    out[py-cy:py-cy+H, px-cx:px-cx+W] = A
    return out


CEN_BODY = _center_on(BODY, *PIVOT)


def rot(arr, angle):
    im = Image.new("P", (arr.shape[1], arr.shape[0]))
    im.putpalette(pal_bytes)
    im.frombytes(arr.tobytes())
    r = im.rotate(angle, resample=Image.NEAREST, expand=True, fillcolor=0)
    return np.asarray(r)


def blit(g, arr, y0, x0):
    ys, xs = np.nonzero(arr)
    for ry, rx in zip(ys, xs):
        wy, wx = y0 + ry, x0 + rx
        if 0 <= wy < N and 0 <= wx < N:
            g[wy, wx] = arr[ry, rx]


def draw_star(g, cy, cx, arm, color, core=None):
    """A little 4-pointed star: a plus of `arm` px with a bright core."""
    for d in range(-arm, arm + 1):
        for (y, x) in ((cy + d, cx), (cy, cx + d)):
            if 0 <= y < N and 0 <= x < N:
                g[y, x] = color
    if arm >= 3:                            # short diagonals for the big ones
        for d in (-1, 1):
            for (y, x) in ((cy + d, cx + d), (cy + d, cx - d)):
                if 0 <= y < N and 0 <= x < N:
                    g[y, x] = color
    if core is not None and 0 <= cy < N and 0 <= cx < N:
        g[cy, cx] = core


def compose(f):
    ph = 2*math.pi * f / F

    g = np.full((N, N), SKY, dtype=np.uint8)
    g[:22, :] = SKY_D                       # darker band up where the legs are
    for y in (22, 23, 24, 25):              # checker-dither the band edge
        g[y, (y % 2)::2] = SKY_D if y < 24 else SKY
        g[y, ((y + 1) % 2)::2] = SKY if y < 24 else SKY_D

    for (y, x, phase) in BGSTARS:           # faint scatter, winking in phase
        tw = math.sin(ph + phase)
        g[y, x] = STAR_MID if tw > 0.3 else STAR_DIM

    for (y, x, size, phase) in CRUX:        # the Cross twinkles star by star
        tw = math.sin(ph + phase)
        arm = size + (1 if tw > 0.45 else 0)
        color = WHITE if tw > -0.5 else STAR_MID
        core = GOLD if tw > 0.7 else WHITE
        draw_star(g, y, x, arm, color, core)

    sway = SWAY * math.sin(ph)              # slow pendulum about the leg tips
    bob = round(BOB * math.cos(ph))
    R = rot(CEN_BODY, sway)
    blit(g, R, WPY + bob - R.shape[0]//2, WPX - R.shape[1]//2)

    im = Image.frombytes("P", (N, N), g.tobytes())
    im.putpalette(pal_bytes)
    return im


frames = [compose(f) for f in range(F)]
frames[0].save(OUT / "clawd_downunder_still.png")
# full opaque frames (like bugcatcher): disposal=1, no transparency
frames[0].save(OUT / "clawd_downunder.gif", save_all=True,
               append_images=frames[1:], duration=DUR, loop=0,
               disposal=1, optimize=False)
import os
print(f"downunder: {F} frames @ {DUR}ms, "
      f"gif={os.path.getsize(OUT / 'clawd_downunder.gif')//1024} KB")

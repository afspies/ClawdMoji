#!/usr/bin/env python3
"""'Cork Hat' Clawd -- Clawd in the classic Aussie swagman's cork hat: a brown
bush hat with corks dangling from the brim on strings, swinging as he does a
little side-step while a couple of flies buzz figure-eights around him
(that's what the corks are for).

  body + hat : Clawd (full 2px white outline) + a wide-brimmed felt bush hat
               (rounded crown, dark hatband, gently up-curled brim), one rigid
               piece that steps left<->right with a little bounce (mariachi's
               dance).
  corks      : five corks hang from the brim on thin strings; each swings like
               a pendulum with its own phase, so they never move in lockstep.
  flies      : two little flies loop evasive figure-eights around the hat.

Seamless by construction: the side-step is sin(2*pi*f/F), the bounce is
|sin(2*pi*f/F)|, each cork swings with sin(2*pi*f/F + phase) and each fly's
path is sin / sin(2*) of 2*pi*f/F -- all equal at f=0 and f=F.
Outputs the still + gif.
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
    (0, 0, 0),          # 0  transparent
    (218, 119, 88),     # 1  CLAWD body  #DA7758
    (0, 0, 0),          # 2  eye
    (255, 255, 255),    # 3  white outline
    (163, 84, 60),      # 4  body shade (brim shadow on the face)
    (139, 94, 60),      # 5  felt light
    (110, 72, 44),      # 6  felt mid
    (82, 52, 30),       # 7  felt dark / hatband
    (222, 189, 140),    # 8  cork light
    (188, 148, 96),     # 9  cork shade
    (58, 44, 32),       # 10 string / fly body
]
(T, CLAWD, EYE, WHITE, SHADE, FELT_L, FELT_M, FELT_D,
 CORK_L, CORK_D, DARK) = range(11)
pal_bytes = bytes([c for rgb in COLORS for c in rgb] + [0]*(768 - 3*len(COLORS)))

# ---- timing / motion --------------------------------------------------
F     = 16         # frames in the loop
DUR   = 90         # ms/frame
STEP  = 5.0        # left<->right travel (px)
HOP   = 2.0        # bounce (px, two hops/loop)
SWING = 4.0        # cork swing amplitude (px at the cork)

# ---- body + hat layout (in the padded body canvas) ---------------------
SCALE = 8                          # 12x8 art -> 96x64 body
SX, SY = 12*SCALE, 8*SCALE
AW, AH = 110, 100                  # body canvas
BX, BY = (AW - SX)//2, 28          # body top-left
CX0    = BX + SX//2                # body centre column

BRIM_Y  = BY - 2                   # brim line sits just over the head
BRIM_HW = 44                       # brim half-width
BRIM_TH = 5
CROWN_H = 21
CROWN_TW, CROWN_BW = 16, 23        # crown half-width, top and base

# corks: (anchor dx from centre, string length px, swing phase)
# anchors avoid the eye columns (dx ~ +-20) so no string crosses an eye
CORKS = [
    (-40, 12, 0.0),
    (-28, 20, 1.9),
    (0,   15, 3.5),
    (28,  21, 5.0),
    (40,  13, 2.7),
]
CORK_W, CORK_H = 6, 8              # cork size (they're little barrels)

# flies: (centre y, centre x, x-amplitude, y-amplitude, phase, direction)
FLIES = [
    (44, 22, 11, 9, 0.0, 1),
    (54, 106, 10, 8, math.pi, -1),
]

# world placement of the body-canvas origin (before the step/hop)
WY0, WX0 = 29, (N - AW)//2


def draw_hat(A):
    """A wide-brimmed brown bush hat sitting on Clawd's head."""
    H, W = A.shape
    cx = CX0
    crown_top = BRIM_Y - CROWN_H
    for ry in range(crown_top, BRIM_Y + 1):
        t = (ry - crown_top) / CROWN_H
        hw = CROWN_TW + (CROWN_BW - CROWN_TW) * t
        if t < 0.35:                        # round the crown's shoulders
            hw *= math.sqrt(t / 0.35) if t > 0 else 0.35
        hw = max(3, int(round(hw)))
        for dx in range(-hw, hw + 1):
            x = cx + dx
            if not (0 <= x < W):
                continue
            frac = dx / max(hw, 1)
            c = FELT_M
            if frac < -0.4:   c = FELT_L
            elif frac > 0.5:  c = FELT_D
            A[ry, x] = c

    band_top = BRIM_Y - 7                   # dark hatband above the brim
    for ry in range(band_top, BRIM_Y - 1):
        for dx in range(-CROWN_BW, CROWN_BW + 1):
            x = cx + dx
            if 0 <= x < W and A[ry, x] != 0:
                A[ry, x] = FELT_D

    for dx in range(-BRIM_HW, BRIM_HW + 1):   # the brim, tips curled up a bit
        x = cx + dx
        if not (0 <= x < W):
            continue
        tt = dx / BRIM_HW
        mid = BRIM_Y + 2.0 * (1 - tt*tt) - 4.0 * (tt*tt)
        for k in range(BRIM_TH + 1):
            y = int(round(mid - BRIM_TH/2 + k))
            if 0 <= y < H:
                if k == 0:              c = FELT_L
                elif k >= BRIM_TH - 1:  c = FELT_D
                else:                   c = FELT_M
                A[y, x] = c

    for dx in range(-CROWN_BW - 7, CROWN_BW + 8):   # brim shadow on the face
        x = cx + dx
        y = BRIM_Y + BRIM_TH
        if 0 <= y < H and 0 <= x < W and A[y, x] == CLAWD:
            A[y, x] = SHADE


def build_body():
    A = np.zeros((AH, AW), dtype=np.uint8)
    for j, row in enumerate(ART):
        for i, ch in enumerate(row):
            if ch == ".":
                continue
            A[BY+j*SCALE:BY+(j+1)*SCALE, BX+i*SCALE:BX+(i+1)*SCALE] = \
                EYE if ch == "O" else CLAWD
    draw_hat(A)
    A[border_mask(A > 0, pen_disk(2))] = WHITE
    return A


BODY = build_body()


def blit(g, arr, y0, x0):
    ys, xs = np.nonzero(arr)
    for ry, rx in zip(ys, xs):
        wy, wx = y0 + ry, x0 + rx
        if 0 <= wy < N and 0 <= wx < N:
            g[wy, wx] = arr[ry, rx]


def draw_cork(g, ay, ax, length, sway):
    """One cork: a thin string from the brim anchor down to a little barrel,
    the barrel displaced sideways by `sway` (the string leans with it)."""
    ty, tx = ay + length, ax + sway                     # cork top-centre
    steps = max(length, 1)
    for s in range(steps + 1):                          # the string
        t = s / steps
        y = int(round(ay + (ty - ay) * t))
        x = int(round(ax + (tx - ax) * t))
        if 0 <= y < N and 0 <= x < N:
            g[y, x] = DARK
    x0, y0 = int(round(tx)) - CORK_W//2, int(round(ty))
    cork = np.zeros((CORK_H + 4, CORK_W + 4), dtype=np.uint8)
    cork[2:2+CORK_H, 2:2+CORK_W] = CORK_L
    cork[2:2+CORK_H, 2+CORK_W-2:2+CORK_W] = CORK_D      # shaded right edge
    cork[2, 2:2+CORK_W] = CORK_D                        # dark top rim
    cork[border_mask(cork > 0, pen_disk(1))] = WHITE    # thin outline
    blit(g, cork, y0 - 2, x0 - 2)


def draw_fly(g, f, cy, cx, ax_, ay_, phase, direction):
    """A little buzzing fly on a figure-eight, wings flickering."""
    ph = 2*math.pi * f / F
    x = int(round(cx + direction * ax_ * math.sin(ph + phase)))
    y = int(round(cy + ay_ * math.sin(2*(ph + phase))))
    body = np.zeros((6, 6), dtype=np.uint8)
    body[2:4, 2:4] = DARK                               # 2x2 body
    if math.cos(2*math.pi * 4 * f / F + phase) > 0:     # wing flicker (4x/loop)
        body[1, 1] = body[1, 4] = WHITE
    else:
        body[1, 2] = body[1, 3] = WHITE
    blit(g, body, y - 2, x - 2)


def compose(f):
    g = np.zeros((N, N), dtype=np.uint8)
    ph = 2*math.pi * f / F
    step = STEP * math.sin(ph)
    hop  = HOP * abs(math.sin(ph))
    by0 = int(round(WY0 - hop))
    bx0 = int(round(WX0 + step))

    blit(g, BODY, by0, bx0)                             # body + hat

    brim_world_y = by0 + BRIM_Y + BRIM_TH               # corks hang off the brim
    for (dx, length, phase) in CORKS:
        ax = bx0 + CX0 + dx
        tt = dx / BRIM_HW
        ay = int(round(brim_world_y + 2.0 * (1 - tt*tt) - 4.0 * (tt*tt)))
        sway = SWING * math.sin(ph + phase)
        draw_cork(g, ay, ax, length, sway)

    for (cy, cx, ax_, ay_, phase, d) in FLIES:          # flies on top
        draw_fly(g, f, cy, cx, ax_, ay_, phase, d)

    im = Image.frombytes("P", (N, N), g.tobytes())
    im.putpalette(pal_bytes)
    return im


frames = [compose(f) for f in range(F)]
frames[0].save(OUT / "clawd_corkhat_still.png")
frames[0].save(OUT / "clawd_corkhat.gif", save_all=True, append_images=frames[1:],
               duration=DUR, loop=0, transparency=0, disposal=2, optimize=False)
import os
print(f"corkhat: {F} frames @ {DUR}ms, "
      f"gif={os.path.getsize(OUT / 'clawd_corkhat.gif')//1024} KB")

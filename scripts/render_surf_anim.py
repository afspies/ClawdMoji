#!/usr/bin/env python3
"""'Surfing' Clawd -- layered, composited at 128px:

  ocean       : a big cresting wave; a raised swell peaks on the right and
                slopes down to a flatter sea on the left (the face Clawd rides).
                Filled with depth-banded blues + a scrolling sparkle texture.
  board       : a tilted red surfboard (nose up on the downhill side).
  Clawd       : sprite + thin 2px white border, bobbing on the wave.
  foam / spray: white crest foam along the steep lip + flickering flecks and a
                spray burst off the wave lip.

Seamless by construction: everything periodic in `f` over F frames --
the swell ripple and sparkle scroll use phase 2*pi*(... - k*f/F) with integer
k, the bob is sin(2*pi*f/F), and foam/spray are pure functions of `f mod F`.
Outputs clawd_surf_still.png and clawd_surf.gif.
"""
import math
import random
from pathlib import Path
import numpy as np
from PIL import Image

OUT = Path(__file__).resolve().parent.parent / "emoji"; OUT.mkdir(exist_ok=True)

N, CELL = 64, 2
CANVAS = N * CELL   # 128

# ---- palette ----------------------------------------------------------
COLORS = [
    (0, 0, 0),          # 0 transparent (reserved)
    (120, 205, 225),    # 1 water light / crest teal
    (54, 141, 199),     # 2 water mid
    (28, 84, 152),      # 3 water deep
    (255, 255, 255),    # 4 foam / spray white
    (218, 119, 88),     # 5 Clawd  #DA7758
    (0, 0, 0),          # 6 eye
    (255, 255, 255),    # 7 white border (== foam, kept distinct for clarity)
    (228, 74, 62),      # 8 surfboard red
    (255, 214, 92),     # 9 board stripe / nose accent
]
T, W_L, W_M, W_D, FOAM, CLAWD, EYE, WHITE, BOARD, STRIPE = range(10)
pal_bytes = bytes([c for rgb in COLORS for c in rgb] + [0]*(768 - 3*len(COLORS)))

# ---- timing / motion --------------------------------------------------
F      = 12         # frames in the loop
DUR    = 90         # ms/frame
BOB    = 1.6        # Clawd vertical bob amplitude (cells)
LAMBDA = 22.0       # swell ripple wavelength (cells)
RIPPLE = 1.4        # swell ripple amplitude (cells)
RIPK   = 1          # ripple cycles advanced over the loop (seamless)
SPARKK = 2          # sparkle-scroll cycles over the loop (seamless)

# ---- wave geometry ----------------------------------------------------
# Water surface row as a function of column x (rows: 0 top .. N-1 bottom).
# A raised swell peaks near PEAK_X and slopes down to a flatter sea on the
# left; to the right of the peak it breaks steeply back down.
SEA_BASE = 48       # flat-sea surface row on the far left
PEAK_X   = 47       # column of the crest
PEAK_TOP = 11       # crest row (smaller = higher)
BACK_END = 24       # surface row at the far-right edge (the broken back)

def base_surface(x):
    if x <= PEAK_X:
        t = (x / PEAK_X) ** 1.7                       # gentle then steep face
        return SEA_BASE + (PEAK_TOP - SEA_BASE) * t
    t = (x - PEAK_X) / (N - 1 - PEAK_X)               # steep break behind peak
    return PEAK_TOP + (BACK_END - PEAK_TOP) * (t ** 0.7)

def surface_row(x, f):
    ripple = RIPPLE * math.sin(2*math.pi * (x / LAMBDA - RIPK * f / F))
    return base_surface(x) + ripple

# ---- Clawd + thin white border ---------------------------------------
ART = [
    "..########..", "..#O####O#..", "############", "############",
    "..########..", "..########..", "..#.#..#.#..", "..#.#..#.#..",
]
SCALE = 3
SX, SY = 12*SCALE, 8*SCALE       # 36 x 24
RIDE_X = 29                      # Clawd centre column (on the left face)

sprite = np.zeros((SY, SX), dtype=np.uint8)
for j, row in enumerate(ART):
    for i, ch in enumerate(row):
        if ch == ".":
            continue
        sprite[j*SCALE:(j+1)*SCALE, i*SCALE:(i+1)*SCALE] = EYE if ch == "O" else CLAWD
sbody = sprite > 0
sborder = np.zeros_like(sbody)
for dy in (-1, 0, 1):
    for dx in (-1, 0, 1):
        sh = np.zeros_like(sbody)
        ys = slice(max(0, dy), SY+min(0, dy)); xs = slice(max(0, dx), SX+min(0, dx))
        yt = slice(max(0, -dy), SY+min(0, -dy)); xt = slice(max(0, -dx), SX+min(0, -dx))
        sh[ys, xs] = sbody[yt, xt]; sborder |= sh
sborder &= ~sbody
sprite[sborder] = WHITE
SPR_MASK = sprite > 0
FEET_DX = SX // 2                 # sprite-local x of Clawd's centre

def paint_ocean(g, f):
    for x in range(N):
        s = int(round(surface_row(x, f)))
        for y in range(max(0, s), N):
            d = y - s
            if d <= 1:      c = W_L               # bright lip just under surface
            elif d <= 6:    c = W_M
            else:           c = W_D
            # scrolling sparkle: sparse glints drifting along the swell
            ph = (math.sin(2*math.pi * (x / 5.0 - SPARKK * f / F))
                  * math.sin(x * 1.7 + y * 2.3))
            if d >= 3 and ph > 0.88:
                c = W_L
            g[y, x] = c

def crest_foam(g, f):
    """White foam capping the breaking wave: a band along the steep lip."""
    for x in range(1, N):
        s0 = surface_row(x - 1, f); s1 = surface_row(x, f)
        slope = abs(s1 - s0)
        s = int(round(s1))
        near_peak = abs(x - PEAK_X) <= 6
        if (slope > 0.6 or near_peak) and 0 <= s < N:
            depth = 3 if slope > 1.1 else 2         # thicker foam on the steepest part
            for y in range(max(0, s), min(N, s + depth)):
                g[y, x] = FOAM

def place_clawd(g, f):
    bob = BOB * math.sin(2*math.pi * f / F)
    # board rides the surface under Clawd's centre column; Clawd's feet sit
    # on the board's deck (board top overlaps the very bottom of the legs).
    board_cy = int(round(surface_row(RIDE_X, f) + bob))
    top = board_cy - SY
    ox = RIDE_X - FEET_DX
    # --- surfboard: fat tilted lozenge, nose (left/downhill) raised ---
    half = FEET_DX + 4
    for dx in range(-half, half + 1):
        frac = dx / half
        tilt = int(round(-2.4 * frac))              # left end up, right end down
        x = RIDE_X + dx
        if not (0 <= x < N):
            continue
        base_y = board_cy + tilt
        # thickness tapers to points at nose and tail
        thick = 3 if abs(frac) < 0.55 else (2 if abs(frac) < 0.82 else 1)
        # a foamy wake spits off the tail (right/downhill end)
        if frac > 0.6 and 0 <= base_y + 2 < N:
            g[base_y + 2, x] = FOAM
        for t in range(thick):
            yy = base_y + t
            if 0 <= yy < N:
                g[yy, x] = STRIPE if (t == 1 and abs(frac) < 0.62) else BOARD
    # --- Clawd on top ---
    for j in range(SY):
        yy = top + j
        if not (0 <= yy < N):
            continue
        for i in range(SX):
            if SPR_MASK[j, i]:
                xx = ox + i
                if 0 <= xx < N:
                    g[yy, xx] = sprite[j, i]

# ---- spray burst off the breaking lip --------------------------------
_srng = random.Random(71)
# anchors near the crest lip; each fleck has a launch angle + phase in the loop
SPRAY = []
for _ in range(26):
    ang = _srng.uniform(-2.5, -0.6)                 # up-and-outward
    spd = _srng.uniform(0.7, 1.8)
    SPRAY.append((math.cos(ang) * spd, math.sin(ang) * spd, _srng.randrange(F)))
SPRAY_LIFE = 5

def paint_spray(g, f):
    lipx = PEAK_X + 1
    lipy = surface_row(lipx, f)
    for vx, vy, start in SPRAY:
        t = (f - start) % F
        if t >= SPRAY_LIFE:
            continue
        x = int(round(lipx + vx * t))
        y = int(round(lipy + vy * t + 0.12 * t * t))   # gravity arc
        if 0 <= x < N and 0 <= y < N:
            g[y, x] = FOAM

# ---- compose one frame ----------------------------------------------
def compose(f):
    g = np.zeros((N, N), dtype=np.uint8)
    paint_ocean(g, f)
    crest_foam(g, f)
    place_clawd(g, f)
    paint_spray(g, f)
    big = np.kron(g, np.ones((CELL, CELL), dtype=np.uint8))
    im = Image.frombytes("P", (CANVAS, CANVAS), big.tobytes())
    im.putpalette(pal_bytes)
    return im

frames = [compose(f) for f in range(F)]
frames[0].save(OUT / "clawd_surf_still.png")
frames[0].save(OUT / "clawd_surf.gif", save_all=True, append_images=frames[1:],
               duration=DUR, loop=0, transparency=0, disposal=2, optimize=False)
import os
print(f"surf: {F} frames @ {DUR}ms, "
      f"gif={os.path.getsize(OUT / 'clawd_surf.gif')//1024} KB")

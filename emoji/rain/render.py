#!/usr/bin/env python3
"""'Rainy day' Clawd -- layered, composited at 128px:

  cloud       : big full-width band of dynamic gray that scrolls/churns at top
  rain (back) : many fat drops, fast, BEHIND Clawd
  Clawd       : sprite + thin 2px white border
  rain (front): few fat drops, faster (parallax), IN FRONT of Clawd

Seamless by construction: rain wraps on a vertical tile (V*F multiple of TILE)
and the cloud texture scrolls on a horizontal tile (S*F multiple of P).
Outputs clawd_rain_still.png and clawd_rain.gif.
"""
import math
import random
import sys
from pathlib import Path
import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from shared.clawd import ART, border_mask, pen_square

OUT = Path(__file__).resolve().parent; OUT.mkdir(exist_ok=True)
random.seed(5)

N, CELL = 64, 2
CANVAS = N * CELL   # 128

# ---- palette ----------------------------------------------------------
COLORS = [
    (0, 0, 0),          # 0 transparent (reserved)
    (206, 214, 221),    # 1 cloud light
    (165, 176, 187),    # 2 cloud mid
    (120, 133, 147),    # 3 cloud dark
    (120, 158, 196),    # 4 rain back (muted)
    (165, 200, 230),    # 5 rain front (lighter, closer)
    (218, 119, 88),     # 6 Clawd  #DA7758
    (0, 0, 0),          # 7 eye
    (255, 255, 255),    # 8 white border
]
T, CL_L, CL_M, CL_D, R_B, R_F, CLAWD, EYE, WHITE = range(9)
pal_bytes = bytes([c for rgb in COLORS for c in rgb] + [0]*(768 - 3*len(COLORS)))

# ---- timing / motion (seamless: see header) --------------------------
F        = 8        # frames in the loop
TILE     = 32       # rain vertical repeat (cells)
V_BACK   = 4        # back rain fall speed (cells/frame)  -> fast
V_FRONT  = 8        # front rain faster (parallax)
P        = 16       # cloud texture horizontal repeat (cells)
S        = 2        # cloud scroll (cells/frame)
DUR      = 70       # ms/frame
SLANT    = 0.18     # rain shear (cells right per cell down) -> slight wind angle

# ---- big dynamic-gray cloud band -------------------------------------
CLOUD_BASE = 17                                   # mean cloud-bottom row
_edge = random.Random(13)
cloud_bottom = np.array([
    CLOUD_BASE + int(round(2.4*math.sin(x*0.42) + 1.5*math.sin(x*0.21+1.3)
                           + 1.3*math.sin(x*0.95+0.5)))                 # ragged
    + _edge.choice([-2, -1, 0, 0, 1, 1, 2])                            # + noise
    for x in range(N)])
MAXB = int(cloud_bottom.max())

# texture tile (P wide): row-biased gray + noise, scrolled each frame
rng = random.Random(7)
cloud_tex = np.full((MAXB + 1, P), CL_M, dtype=np.uint8)
for y in range(MAXB + 1):
    for xx in range(P):
        r = rng.random()
        if y <= 2:                 base = CL_L
        elif y >= MAXB - 2:        base = CL_D
        else:                      base = CL_M
        if r < 0.18:   base = CL_L
        elif r > 0.82: base = CL_D
        cloud_tex[y, xx] = base

def paint_cloud(g, f):
    shift = (f * S) % P
    for x in range(N):
        b = cloud_bottom[x]
        for y in range(0, b + 1):
            g[y, x] = cloud_tex[y, (x - shift) % P]

# ---- Clawd + thin white border ---------------------------------------
SCALE = 4
SX, SY = 12*SCALE, 8*SCALE
OX, OY = (N - SX)//2, N - SY - 2
clawd = np.zeros((N, N), dtype=np.uint8)
for j, row in enumerate(ART):
    for i, ch in enumerate(row):
        if ch == ".":
            continue
        clawd[OY+j*SCALE:OY+(j+1)*SCALE, OX+i*SCALE:OX+(i+1)*SCALE] = \
            EYE if ch == "O" else CLAWD
body = clawd > 0
clawd[border_mask(body, pen_square(1))] = WHITE
CLAWD_MASK = clawd > 0

# ---- fat rain drops --------------------------------------------------
W_DROP = 2          # drop width (cells) = 4px

CMARGIN = int(SLANT * N) + 1                       # extra anchors so shear covers edges

def make_rain(prob, drop_len, color, seed):
    rng = random.Random(seed)
    cols = {}
    for c in range(-CMARGIN, N, W_DROP):           # step by width so drops don't merge
        if rng.random() < prob:
            cols[c] = rng.randrange(TILE)
    return {"cols": cols, "len": drop_len, "color": color}

back  = make_rain(0.45, 6, R_B, 101)   # many fat drops behind
front = make_rain(0.20, 9, R_F, 202)   # few fat drops in front (len >= V_FRONT)

def paint_rain(g, rain, phase, over_clawd):
    for c, off in rain["cols"].items():
        for y in range(0, N):
            if (y - phase - off) % TILE < rain["len"]:
                sx = c + int(round(SLANT * y))      # shear -> slanted, diagonal fall
                for w in range(W_DROP):
                    xx = sx + w
                    if 0 <= xx < N and y > cloud_bottom[xx] \
                            and (over_clawd or not CLAWD_MASK[y, xx]):
                        g[y, xx] = rain["color"]

# ---- subtle splashes along the bottom --------------------------------
FLOOR = N - 1
SPLASH = [                                          # 3-frame pop, then gone
    [(0, 0)],                                        # impact
    [(-1, 0), (1, 0), (0, -1)],                      # small spread + up-tick
    [(-2, 0), (2, 0)],                               # droplets fan out, fading
]
_srng = random.Random(303)
SPLASH_ANCHORS = [(_srng.randrange(3, N-3), _srng.randrange(F)) for _ in range(9)]

def paint_splash(g, f):
    for ax, start in SPLASH_ANCHORS:
        t = (f - start) % F
        if t < len(SPLASH):
            for dx, dy in SPLASH[t]:
                x, y = ax + dx, FLOOR + dy
                if 0 <= x < N and 0 <= y < N and not CLAWD_MASK[y, x]:
                    g[y, x] = R_F

# ---- compose one frame ----------------------------------------------
def compose(f):
    g = np.zeros((N, N), dtype=np.uint8)
    paint_cloud(g, f)
    paint_rain(g, back, (f*V_BACK) % TILE, over_clawd=False)
    g[CLAWD_MASK] = clawd[CLAWD_MASK]
    paint_rain(g, front, (f*V_FRONT) % TILE, over_clawd=True)
    paint_splash(g, f)
    big = np.kron(g, np.ones((CELL, CELL), dtype=np.uint8))
    im = Image.frombytes("P", (CANVAS, CANVAS), big.tobytes())
    im.putpalette(pal_bytes)
    return im

frames = [compose(f) for f in range(F)]
frames[0].save(OUT / "clawd_rain_still.png")
frames[0].save(OUT / "clawd_rain.gif", save_all=True, append_images=frames[1:],
               duration=DUR, loop=0, transparency=0, disposal=2, optimize=False)
import os
print(f"cloud bottom {int(cloud_bottom.min())}..{MAXB}; "
      f"back={len(back['cols'])} front={len(front['cols'])} drop-cols; "
      f"{F} frames @ {DUR}ms, gif={os.path.getsize(OUT / 'clawd_rain.gif')//1024} KB")

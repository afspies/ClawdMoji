#!/usr/bin/env python3
"""'This is fine' Clawd, built as programmatic layers composited at 128px:

  layer 0 (back) : procedural animated flames  -- coarse 32-grid (cell=4px),
                   chunky full flames, triangular taper, seamless loop
  layer 1 (front): Clawd sprite -- fine 64-grid (cell=2px) so the white
                   border is a thin 2px outline

Outputs clawd_fire_still.png and clawd_fire.gif.
"""
import random
import sys
from pathlib import Path
import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from shared.clawd import ART, border_mask, pen_square

OUT = Path(__file__).resolve().parent; OUT.mkdir(exist_ok=True)
random.seed(11)

CANVAS = 128

# ---- Doom-fire palette (dark -> red -> orange -> yellow -> white) ------
FIRE = [
    (0x07,0x07,0x07),(0x1F,0x07,0x07),(0x2F,0x0F,0x07),(0x47,0x0F,0x07),
    (0x57,0x17,0x07),(0x67,0x1F,0x07),(0x77,0x1F,0x07),(0x8F,0x27,0x07),
    (0x9F,0x2F,0x07),(0xAF,0x3F,0x07),(0xBF,0x47,0x07),(0xC7,0x47,0x07),
    (0xDF,0x4F,0x07),(0xDF,0x57,0x07),(0xDF,0x57,0x07),(0xD7,0x5F,0x07),
    (0xD7,0x5F,0x07),(0xD7,0x67,0x0F),(0xCF,0x6F,0x0F),(0xCF,0x77,0x0F),
    (0xCF,0x7F,0x0F),(0xCF,0x87,0x17),(0xC7,0x87,0x17),(0xC7,0x8F,0x17),
    (0xC7,0x97,0x1F),(0xBF,0x9F,0x1F),(0xBF,0x9F,0x1F),(0xBF,0xA7,0x27),
    (0xBF,0xA7,0x27),(0xBF,0xAF,0x2F),(0xB7,0xAF,0x2F),(0xB7,0xB7,0x2F),
    (0xCF,0xCF,0x6F),(0xDF,0xDF,0x9F),(0xEF,0xEF,0xC7),(0xFF,0xFF,0xFF),
]
MAX = len(FIRE) - 1            # 35
SRC = 34                       # heat-source intensity -> drives flame HEIGHT (tall)
CAP = 28                       # max color index -> warm orange-yellow base, never white

WHITE, CLAWD, EYE = (255,255,255), (218,119,88), (0,0,0)
I_WHITE, I_CLAWD, I_EYE = MAX + 1, MAX + 2, MAX + 3
palette = [(0,0,0)] + FIRE[1:] + [WHITE, CLAWD, EYE]    # index0 = transparent
pal_bytes = bytes([c for rgb in palette for c in rgb] + [0]*(768 - 3*len(palette)))

# ====================  layer 1: Clawd on a fine 64-grid  ===============
NC, CELLC = 64, 2
SCALE = 4                              # Clawd pixel -> 4 cells = 8px
SX, SY = 12*SCALE, 8*SCALE             # 48 x 32 cells
OX, OY = (NC - SX)//2, NC - SY - 6

clawd = np.zeros((NC, NC), dtype=np.uint8)
for j, row in enumerate(ART):
    for i, ch in enumerate(row):
        if ch == ".":
            continue
        val = I_EYE if ch == "O" else I_CLAWD
        clawd[OY+j*SCALE:OY+(j+1)*SCALE, OX+i*SCALE:OX+(i+1)*SCALE] = val

body = clawd > 0                        # thin (1 cell = 2px) white border
clawd[border_mask(body, pen_square(1))] = I_WHITE
clawd128 = np.kron(clawd, np.ones((CELLC, CELLC), dtype=np.uint8))   # 128x128
FG = clawd128 > 0

# ====================  layer 0: fire on a coarse 32-grid  ==============
NF, CELLF = 32, 4
center, half = (NF-1)/2, NF/2          # triangular taper across columns
src_col = np.array([max(0, 1 - (abs(x-center)/half)**2.0) for x in range(NF)])
src_col = np.round(SRC * src_col).astype(np.int16)

SUB = [0, 1, 1, 2]                     # per-row decay (avg 1.0) -> full chunky flames
fire = np.zeros((NF, NF), dtype=np.int16)
fire[NF-1, :] = src_col

def spread():
    for x in range(NF):
        for y in range(1, NF):
            pix = fire[y, x]
            if pix <= 0:
                fire[y-1, x] = 0
            else:
                decay = SUB[random.randint(0, 3)]
                nx = min(NF-1, max(0, x + random.randint(-1, 1)))   # symmetric wind
                fire[y-1, nx] = max(0, pix - decay)
    fire[NF-1, :] = src_col

# ---- compose a fire grid + Clawd -> PIL 'P' image --------------------
THRESH = 9
def compose(grid):
    idx = np.clip(grid, 0, MAX).astype(np.uint8)
    idx[idx < THRESH] = 0
    idx = np.minimum(idx, CAP)                                       # cap out white
    big = np.kron(idx, np.ones((CELLF, CELLF), dtype=np.uint8))      # 128x128
    big[FG] = clawd128[FG]                                           # Clawd on top
    im = Image.frombytes("P", (CANVAS, CANVAS), big.tobytes())
    im.putpalette(pal_bytes)
    return im

# ---- run: warm up, capture a pool, cut a seamless loop ---------------
for _ in range(120):
    spread()
POOL = 90
grids = []
for _ in range(POOL):
    spread()
    grids.append(fire.copy())

base = grids[0].astype(np.int32)
MINL, MAXL = 18, 48
L = min(range(MINL, MAXL),
        key=lambda k: int(np.sum((grids[k].astype(np.int32) - base) ** 2)))
frames = [compose(grids[k]) for k in range(L)]

frames[0].save(OUT / "clawd_fire_still.png")
frames[0].save(OUT / "clawd_fire.gif", save_all=True, append_images=frames[1:],
               duration=90, loop=0, transparency=0, disposal=2, optimize=False)
import os
seam = int(np.sum((grids[L].astype(np.int32) - base) ** 2))
print(f"loop={L} frames, seam diff={seam}, "
      f"gif={os.path.getsize(OUT / 'clawd_fire.gif')//1024} KB")

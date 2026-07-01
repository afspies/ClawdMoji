#!/usr/bin/env python3
"""'Surfing' Clawd -- layered, composited at 128px (full 128 grid, CELL=1, so
edges/rotation are half the block size of the other emoji -> less pixelated):

  ocean       : a raised swell peaks on the right and slopes down to a flatter
                sea on the left (the face Clawd rides). Depth-banded blues +
                a scrolling sparkle, capped by white foam along the breaking lip.
  Clawd+board : Clawd (full 2px white outline) on a red surfboard, built as ONE
                assembly and rotated together so they drop down the face.
  spray       : white water cresting the board's underside, plus a rooster-tail
                fanning off the tail over the crest.

Seamless by construction: everything periodic in `f` over F frames -- the swell
ripple and sparkle scroll use phase 2*pi*(... - k*f/F) with integer k, the bob
and rock are sin(2*pi*f/F), and all foam/spray are pure functions of `f mod F`.
Outputs clawd_surf_still.png and clawd_surf.gif.
"""
import math
import random
import sys
from pathlib import Path
import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from shared.clawd import ART, border_mask, pen_disk

OUT = Path(__file__).resolve().parent; OUT.mkdir(exist_ok=True)

N, CELL = 128, 1
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
BOB    = 2.6        # Clawd vertical bob amplitude (cells)
LAMBDA = 46.0       # swell ripple wavelength (cells)
RIPPLE = 2.4        # swell ripple amplitude (cells)
RIPK   = 1          # ripple cycles advanced over the loop (seamless)
SPARKK = 2          # sparkle-scroll cycles over the loop (seamless)

# ---- wave geometry ----------------------------------------------------
# Water surface row as a function of column x (rows: 0 top .. N-1 bottom).
# A gentle raised swell peaks near PEAK_X and slopes down to a flatter sea on
# the left; to the right of the peak it breaks back down. Kept short so the
# crest doesn't tower over Clawd.
SEA_BASE = 108      # flat-sea surface row on the far left
PEAK_X   = 98       # column of the crest (before the WAVE_DX shift)
PEAK_TOP = 60       # crest row (smaller = higher) -- ~mid-canvas, a low swell
BACK_END = 92       # surface row at the far-right edge (the broken back)
WAVE_DX  = 9        # shift the whole swell right (keeps room on the left)

def base_surface(x):
    xe = x - WAVE_DX
    if xe <= 0:
        return SEA_BASE                               # flat sea to the left
    if xe <= PEAK_X:
        t = (xe / PEAK_X) ** 1.7                      # gentle then steeper face
        return SEA_BASE + (PEAK_TOP - SEA_BASE) * t
    t = (xe - PEAK_X) / (N - 1 - PEAK_X)              # break behind the peak
    return PEAK_TOP + (BACK_END - PEAK_TOP) * (t ** 0.7)

def surface_row(x, f):
    ripple = RIPPLE * math.sin(2*math.pi * (x / LAMBDA - RIPK * f / F))
    return base_surface(x) + ripple

# ---- Clawd + surfboard, built as one rotatable assembly --------------
SCALE = 7                        # art-cell size in grid cells (12x8 -> 84x56)
SX, SY = 12*SCALE, 8*SCALE
RIDE_X = 64                      # board water-contact column (shifted right)
ANGLE  = 26                      # base lean, ~matched to the wave-face slope
ROCK   = 3.0                     # gentle rocking amplitude (degrees, seamless)
SINK   = 1                       # nudge the board down so its underside cuts the water


def build_assembly():
    """Clawd (with a full 2px white outline) standing on a fat surfboard, laid
    out flat in a padded local canvas. Returns the index array plus the board's
    underside-centre cell -- the point that rides the water and that the whole
    assembly rotates about."""
    PAD, BOARD_TH = 12, 5        # PAD leaves room for outline + board overhang
    W = SX + 2*PAD
    H = SY + BOARD_TH + 2*PAD
    A = np.zeros((H, W), dtype=np.uint8)
    ox, oy = PAD, PAD
    for j, row in enumerate(ART):
        for i, ch in enumerate(row):
            if ch == ".":
                continue
            A[oy+j*SCALE:oy+(j+1)*SCALE, ox+i*SCALE:ox+(i+1)*SCALE] = \
                EYE if ch == "O" else CLAWD
    # white outline -- 2px thick; PAD gives the dilation room on every side
    body = (A == CLAWD) | (A == EYE)
    A[border_mask(body, pen_disk(2))] = WHITE          # roughly circular 2px pen
    # surfboard: a fat lozenge just under Clawd's feet
    feet_row = oy + SY - 1
    bcx = ox + SX // 2
    deck = feet_row + 1
    half = SX // 2 + 6
    for dx in range(-half, half + 1):
        frac = dx / half
        x = bcx + dx
        if not (0 <= x < W):
            continue
        thick = BOARD_TH if abs(frac) < 0.62 else (3 if abs(frac) < 0.86 else 1)
        for t in range(thick):
            yy = deck + t
            if 0 <= yy < H:
                # bright stripe down the middle of the deck so the board reads
                A[yy, x] = STRIPE if (t in (2, 3) and abs(frac) < 0.7) else BOARD
    return A, (deck + BOARD_TH - 1, bcx)     # contact = board underside centre


ASSEMBLY, (CY, CX) = build_assembly()


def _center_on(A, cy, cx):
    """Pad A so (cy,cx) sits at the exact centre -> rotation pivots there."""
    H, W = A.shape
    py, px = max(cy, H-1-cy), max(cx, W-1-cx)
    out = np.zeros((2*py+1, 2*px+1), dtype=np.uint8)
    out[py-cy:py-cy+H, px-cx:px-cx+W] = A
    return out                               # centre index = (py, px)


CENTERED = _center_on(ASSEMBLY, CY, CX)


def rotated(angle_deg):
    im = Image.new("P", (CENTERED.shape[1], CENTERED.shape[0]))
    im.putpalette(pal_bytes)
    im.frombytes(CENTERED.tobytes())
    r = im.rotate(angle_deg, resample=Image.NEAREST, expand=True, fillcolor=0)
    return np.asarray(r)                      # expand keeps the pivot at centre


def paint_ocean(g, f):
    for x in range(N):
        s = int(round(surface_row(x, f)))
        for y in range(max(0, s), N):
            d = y - s
            if d <= 2:      c = W_L               # bright lip just under surface
            elif d <= 13:   c = W_M
            else:           c = W_D
            # scrolling sparkle: sparse glints drifting along the swell
            ph = (math.sin(2*math.pi * (x / 9.0 - SPARKK * f / F))
                  * math.sin(x * 0.9 + y * 1.2))
            if d >= 5 and ph > 0.9:
                c = W_L
            g[y, x] = c

CREST_X = PEAK_X + WAVE_DX                            # screen column of the crest

def crest_foam(g, f):
    """White foam capping the breaking wave: a band along the steep lip."""
    for x in range(1, N):
        s0 = surface_row(x - 1, f); s1 = surface_row(x, f)
        slope = abs(s1 - s0)
        s = int(round(s1))
        near_peak = abs(x - CREST_X) <= 12
        if (slope > 0.35 or near_peak) and 0 <= s < N:
            depth = 5 if slope > 0.7 else 3          # thicker foam on the steepest part
            for y in range(max(0, s), min(N, s + depth)):
                g[y, x] = FOAM

# spray flicking off the top of the wave -- fans up off the lip into the open
# air above the crest, arcing back down under gravity.
_srng = random.Random(71)
CREST_SPRAY = []                                     # (launch-dx, vx, vy, start)
for _ in range(52):
    lox = _srng.uniform(-7, 7)                       # spread along the lip
    vx  = _srng.uniform(-1.8, 1.6)                   # fan out both ways
    vy  = -_srng.uniform(2.4, 5.6)                   # strong upward launch
    CREST_SPRAY.append((lox, vx, vy, _srng.randrange(F)))
CREST_LIFE = 8
CREST_G = 0.24                                       # gravity on the arc

def paint_crest_spray(g, f):
    """Rooster-tail off the wave lip. Drawn *behind* Clawd (before he's placed)
    so it reads as spray coming off the crest behind the surfer."""
    ly = surface_row(CREST_X, f) - 1
    for lox, vx, vy, start in CREST_SPRAY:
        t = (f - start) % F
        if t >= CREST_LIFE:
            continue
        x = int(round(CREST_X + lox + vx * t))
        y = int(round(ly + vy * t + CREST_G * t * t))
        dabs = [(0, 0)] if t >= 4 else [(0, 0), (1, 0), (0, 1)]  # dense base, fine tips
        for dx, dy in dabs:
            xx, yy = x + dx, y + dy
            if 0 <= xx < N and 0 <= yy < N:
                g[yy, xx] = FOAM


def contact_point(f):
    """World cell the board rides this frame: surface at RIDE_X, plus bob, plus
    SINK so the board digs into the wave rather than floating over it."""
    bob = BOB * math.sin(2*math.pi * f / F)
    return RIDE_X, surface_row(RIDE_X, f) + bob + SINK

def place_clawd(g, f):
    # rotate the whole Clawd+board assembly down the face, with a gentle rock
    ang = ANGLE + ROCK * math.sin(2*math.pi * f / F)
    R = rotated(ang)
    rh, rw = R.shape
    ax, ay = contact_point(f)
    y0 = int(round(ay)) - rh // 2
    x0 = int(round(ax)) - rw // 2
    # draw the assembly, remembering which world columns the board covers
    board_cols = set()
    ys, xs = np.nonzero(R)
    for ry, rx in zip(ys, xs):
        wy, wx = y0 + ry, x0 + rx
        if 0 <= wy < N and 0 <= wx < N:
            g[wy, wx] = R[ry, rx]
            if R[ry, rx] in (BOARD, STRIPE):
                board_cols.add(wx)
    # a thin bright foam wash right at the waterline where the board cuts the
    # wave -> the board reads as planing *through* the water, not floating over.
    for wx in board_cols:
        s = int(round(surface_row(wx, f)))
        for yy in (s, s + 1):
            if 0 <= yy < N and (wx * 3 + f * 5) % 5 != 0:        # ragged, seamless
                if g[yy, wx] in (BOARD, STRIPE, W_L, W_M, W_D):  # not Clawd's body
                    g[yy, wx] = FOAM
    # bow-spray kicking up off the water where the board's nose cuts in
    if board_cols:
        nose_x = min(board_cols)
        for k in range(9):
            wx = nose_x + k
            s = surface_row(wx, f)
            wobble = 0.5 + 0.5 * math.sin(k * 0.8 + 2*math.pi * f / F)  # seamless
            h = int((2 + 4 * wobble) * (1 - k / 11))                    # tallest at the nose
            for up in range(h):
                yy = int(round(s)) - 1 - up
                if 0 <= yy < N and 0 <= wx < N and g[yy, wx] in (T, W_L, W_M, W_D):
                    g[yy, wx] = FOAM

# ---- compose one frame ----------------------------------------------
def compose(f):
    g = np.zeros((N, N), dtype=np.uint8)
    paint_ocean(g, f)
    crest_foam(g, f)
    paint_crest_spray(g, f)         # spray off the wave lip, behind Clawd
    place_clawd(g, f)               # assembly + waterline wash + bow-spray
    if CELL == 1:
        big = g
    else:
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

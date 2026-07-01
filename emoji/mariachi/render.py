#!/usr/bin/env python3
"""'Mariachi' Clawd -- Clawd in a big straw sombrero, a maraca raised in each
hand, dancing. Rendered on the full 128 grid (CELL=1) like the surf emoji so
the sombrero curves and maraca bulbs stay crisp.

  assembly    : Clawd (full 2px white outline) + sombrero + two maracas, built
                as ONE rigid figure so the whole thing dances together.
  dance        : the figure sways side to side, hops (two little bounces per
                loop) and tilts, pivoting about the hips -- swinging the raised
                maracas like a cha-cha.
  flair        : short motion ticks flick off the shaking maraca bulbs and a
                couple of music notes bob overhead.

Seamless by construction: sway and tilt are sin(2*pi*f/F); the hop is
|sin(2*pi*f/F)| (two bounces, equal at f=0 and f=F); the note bob and the
maraca ticks are sin/cos of 2*pi*f/F. Outputs clawd_mariachi_still.png and .gif.
"""
import math
import sys
from pathlib import Path
import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from shared.clawd import ART, border_mask, pen_disk

OUT = Path(__file__).resolve().parent; OUT.mkdir(exist_ok=True)

N, CELL = 128, 1
CANVAS = N * CELL

# ---- palette ----------------------------------------------------------
COLORS = [
    (0, 0, 0),          # 0  transparent (reserved)
    (218, 119, 88),     # 1  CLAWD body  #DA7758
    (0, 0, 0),          # 2  eye
    (255, 255, 255),    # 3  white outline
    (163, 84, 60),      # 4  body shade (brim shadow on the face)
    (226, 188, 122),    # 5  straw light
    (196, 154, 92),     # 6  straw mid
    (150, 110, 62),     # 7  straw dark
    (201, 42, 46),      # 8  band / dot red
    (247, 199, 72),     # 9  gold trim / maraca bulb
    (120, 78, 42),      # 10 maraca handle brown
    (60, 176, 178),     # 11 teal accent dot
]
(T, CLAWD, EYE, WHITE, SHADE, STRAW_L, STRAW_M, STRAW_D,
 RED, GOLD, HANDLE, TEAL) = range(12)
pal_bytes = bytes([c for rgb in COLORS for c in rgb] + [0]*(768 - 3*len(COLORS)))

# ---- timing / motion --------------------------------------------------
F     = 12          # frames in the loop
DUR   = 90          # ms/frame
SWAY  = 4.0         # horizontal weight-shift (px)
HOP   = 3.0         # vertical bounce (px, two hops/loop)
TILT  = 5.0         # body lean amplitude (degrees)

# ---- figure layout (in the padded assembly canvas) --------------------
SCALE = 6                         # 12x8 art -> 72x48 body
SX, SY = 12*SCALE, 8*SCALE
AW, AH = 160, 116                 # assembly canvas
BX, BY = (AW - SX)//2, 52         # body top-left  (centred x, room for hat above)
CX0    = BX + SX//2               # body centre column


def fill_disk(A, cy, cx, r, color):
    for dy in range(-r, r+1):
        for dx in range(-r, r+1):
            if dy*dy + dx*dx <= r*r:
                yy, xx = cy+dy, cx+dx
                if 0 <= yy < AH and 0 <= xx < AW:
                    A[yy, xx] = color


def thick_line(A, y0, x0, y1, x1, r, color):
    steps = int(max(abs(y1-y0), abs(x1-x0))) + 1
    for s in range(steps+1):
        t = s/steps
        cy, cx = y0 + (y1-y0)*t, x0 + (x1-x0)*t
        fill_disk(A, int(round(cy)), int(round(cx)), r, color)


def draw_sombrero(A):
    """A wide straw sombrero sitting on top of Clawd's head."""
    cx = CX0
    brim_y   = BY - 1          # brim centreline (just above the head top)
    crown_h  = 21
    crown_th = 11              # crown half-width at the top
    crown_bh = 15              # crown half-width at the base
    brim_hw  = 50              # brim half-width
    brim_th  = 4               # brim thickness (vertical)
    brim_dip = 3               # brim droops this far in the middle (front edge)
    brim_curl = 6              # brim tips curl up this far

    # crown: a rounded trapezoid rising from the brim
    crown_top = brim_y - crown_h
    for ry in range(crown_top, brim_y + 1):
        t = (ry - crown_top) / crown_h              # 0 top .. 1 base
        hw = crown_th + (crown_bh - crown_th) * t
        if t < 0.30:                                # round the crown's top
            hw *= math.sqrt(t / 0.30)
        hw = int(round(hw))
        for dx in range(-hw, hw + 1):
            x = cx + dx
            if not (0 <= x < AW):
                continue
            frac = dx / max(hw, 1)
            c = STRAW_M
            if frac < -0.35:   c = STRAW_L          # lit left
            elif frac > 0.45:  c = STRAW_D          # shaded right
            A[ry, x] = c

    # brim: wide flattened band, dipping in front and curling up at the tips
    for dx in range(-brim_hw, brim_hw + 1):
        x = cx + dx
        if not (0 <= x < AW):
            continue
        tt = dx / brim_hw
        mid = brim_y + brim_dip * (1 - tt*tt) - brim_curl * (tt*tt)
        th = brim_th + (1 if abs(tt) > 0.82 else 0)  # slightly fatter, rolled tips
        for k in range(th + 1):
            y = int(round(mid - th/2 + k))
            if 0 <= y < AH:
                if k == 0:            c = STRAW_L    # lit top edge
                elif k >= th - 1:     c = STRAW_D    # shaded underside
                else:                 c = STRAW_M
                A[y, x] = c

    # red band with gold trim around the base of the crown
    band_y = brim_y - brim_th
    for dx in range(-crown_bh, crown_bh + 1):
        x = cx + dx
        if not (0 <= x < AW):
            continue
        for k, c in ((0, GOLD), (1, RED), (2, RED), (3, GOLD)):
            y = band_y - 3 + k
            if 0 <= y < AH:
                A[y, x] = c
    for gdx in range(-crown_bh + 3, crown_bh - 2, 6):      # gold studs on the band
        x = cx + gdx
        if 0 <= x < AW:
            A[band_y - 2, x] = GOLD

    # gold bolita trim hanging under the brim edge
    for dx in range(-brim_hw + 4, brim_hw - 3, 7):
        x = cx + dx
        tt = dx / brim_hw
        mid = brim_y + brim_dip * (1 - tt*tt) - brim_curl * (tt*tt)
        y = int(round(mid + brim_th/2 + 1))
        if 0 <= y < AH and 0 <= x < AW:
            A[y, x] = GOLD

    # soft shadow the brim casts on Clawd's forehead
    for dx in range(-crown_bh - 6, crown_bh + 7):
        x = cx + dx
        y = brim_y + brim_th
        if 0 <= y < AH and 0 <= x < AW and A[y, x] == CLAWD:
            A[y, x] = SHADE


def draw_maraca(A, base_xy, bulb_xy, r, lit_left=True):
    """A maraca: a brown handle from the hand up to a round gold bulb."""
    by_, bx_ = base_xy
    uy, ux = bulb_xy
    thick_line(A, by_, bx_, uy, ux, 1, HANDLE)          # handle
    fill_disk(A, uy, ux, r, GOLD)                       # bulb
    # volume shading on the far side + a highlight on the near side
    sx = -1 if lit_left else 1
    for dy in range(-r, r+1):
        for dx in range(-r, r+1):
            if dy*dy + dx*dx <= r*r:
                yy, xx = uy+dy, ux+dx
                if 0 <= yy < AH and 0 <= xx < AW:
                    if dx * sx > r*0.35 and dy > -r*0.3:
                        A[yy, xx] = STRAW_D             # shaded crescent
    A[uy - r//2, ux - sx*(r//2)] = STRAW_L              # sheen
    # festive dots
    A[uy, ux] = RED
    A[uy - 2, ux + sx] = TEAL
    A[uy + 2, ux - sx] = RED


def build_assembly():
    A = np.zeros((AH, AW), dtype=np.uint8)
    # Clawd body
    for j, row in enumerate(ART):
        for i, ch in enumerate(row):
            if ch == ".":
                continue
            A[BY+j*SCALE:BY+(j+1)*SCALE, BX+i*SCALE:BX+(i+1)*SCALE] = \
                EYE if ch == "O" else CLAWD
    # a maraca shaken close beside each shoulder (bulbs clear of the brim)
    draw_maraca(A, (BY + 32, BX + 8),      (BY + 14, BX - 8),      r=9, lit_left=True)
    draw_maraca(A, (BY + 32, BX + SX - 9), (BY + 14, BX + SX + 7), r=9, lit_left=False)
    # sombrero on top (drawn after the body so the brim occludes the head)
    draw_sombrero(A)
    # single white outline wrapping the whole figure
    solid = A > 0
    A[border_mask(solid, pen_disk(2))] = WHITE
    return A


ASSEMBLY = build_assembly()
PY, PX = BY + SY//2, CX0                    # pivot: Clawd's hips


def _center_on(A, cy, cx):
    H, W = A.shape
    py, px = max(cy, H-1-cy), max(cx, W-1-cx)
    out = np.zeros((2*py+1, 2*px+1), dtype=np.uint8)
    out[py-cy:py-cy+H, px-cx:px-cx+W] = A
    return out


CENTERED = _center_on(ASSEMBLY, PY, PX)


def rotated(angle_deg):
    im = Image.new("P", (CENTERED.shape[1], CENTERED.shape[0]))
    im.putpalette(pal_bytes)
    im.frombytes(CENTERED.tobytes())
    r = im.rotate(angle_deg, resample=Image.NEAREST, expand=True, fillcolor=0)
    return np.asarray(r)


# world position of the pivot (keeps the dancing figure centred)
WPX, WPY = 64, 74

# ---- music notes bobbing overhead ------------------------------------
NOTES = [(30, 3.0, 0.0), (150, 3.0, math.pi), (98, 4.0, 1.7)]  # (x, amp, phase)

def eighth_note(g, cy, cx, color):
    for dy in range(6):                         # stem
        y, x = cy - dy, cx + 2
        if 0 <= y < N and 0 <= x < N: g[y, x] = color
    for dy in range(2):                         # flag
        y, x = cy - 5 + dy, cx + 3
        if 0 <= y < N and 0 <= x < N: g[y, x] = color
    for dy in range(-1, 2):                     # notehead
        for dx in range(-1, 2):
            y, x = cy + dy, cx + dx
            if 0 <= y < N and 0 <= x < N: g[y, x] = color

def paint_notes(g, f):
    ph = 2*math.pi * f / F
    for nx, amp, phase in NOTES:
        y = int(round(26 + amp * math.sin(ph + phase)))
        x = int(round(nx + 2 * math.cos(ph + phase)))
        eighth_note(g, y, x, GOLD)


# bulb centres in the assembly, as offsets from the pivot (relx, rely, outer-sign)
BULBS = [(BX - 8 - PX, BY + 14 - PY, -1), (BX + SX + 7 - PX, BY + 14 - PY, +1)]

def _bulb_world(relx, rely, ang, sway, hop):
    th = math.radians(ang)                               # match PIL's CCW rotate
    rx = math.cos(th)*relx + math.sin(th)*rely
    ry = -math.sin(th)*relx + math.cos(th)*rely
    return WPX + sway + rx, WPY - hop + ry

def maraca_ticks(g, f, ang, sway, hop):
    """Little shake-lines flicking off the outer side of each maraca bulb."""
    ph = 2*math.pi * f / F
    for relx, rely, sgn in BULBS:
        bx, by = _bulb_world(relx, rely, ang, sway, hop)
        for i in range(3):
            wob = 1.3 * math.sin(ph + i*1.6)
            x = int(round(bx + sgn * (13 + i*2)))        # just outboard of the bulb
            y = int(round(by - 6 + i*5 + wob))
            for dx in range(2):                          # a short dash
                xx = x + sgn*dx
                if 0 <= y < N and 0 <= xx < N and g[y, xx] == T:
                    g[y, xx] = WHITE


def compose(f):
    g = np.zeros((N, N), dtype=np.uint8)
    ph = 2*math.pi * f / F
    paint_notes(g, f)                                     # behind the figure
    ang = TILT * math.sin(ph)
    R = rotated(ang)
    rh, rw = R.shape
    sway = SWAY * math.sin(ph)
    hop  = HOP * abs(math.sin(ph))
    y0 = int(round(WPY - hop)) - rh // 2
    x0 = int(round(WPX + sway)) - rw // 2
    ys, xs = np.nonzero(R)
    for ry, rx in zip(ys, xs):
        wy, wx = y0 + ry, x0 + rx
        if 0 <= wy < N and 0 <= wx < N:
            g[wy, wx] = R[ry, rx]
    maraca_ticks(g, f, ang, sway, hop)
    im = Image.frombytes("P", (CANVAS, CANVAS), g.tobytes())
    im.putpalette(pal_bytes)
    return im


frames = [compose(f) for f in range(F)]
frames[0].save(OUT / "clawd_mariachi_still.png")
frames[0].save(OUT / "clawd_mariachi.gif", save_all=True, append_images=frames[1:],
               duration=DUR, loop=0, transparency=0, disposal=2, optimize=False)
import os
print(f"mariachi: {F} frames @ {DUR}ms, "
      f"gif={os.path.getsize(OUT / 'clawd_mariachi.gif')//1024} KB")

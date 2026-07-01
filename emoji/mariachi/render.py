#!/usr/bin/env python3
"""'Mariachi' Clawd -- Clawd in a big straw sombrero, gripping a maraca by the
handle in each hand and shaking them as he steps side to side. Rendered on the
full 128 grid (CELL=1) like surf so the sombrero curves and round bulbs stay crisp.

  body + hat  : Clawd (full 2px white outline) + a wide sombrero, built as one
                rigid piece that steps left<->right with a little bounce.
  arms        : each arm (orange) grips a maraca by its handle, bulb on the far
                end. Built as its own piece and *rotated about the shoulder* so
                the maracas visibly shake -- twice per loop.
  flair        : a couple of gold music notes bob overhead.

Seamless by construction: the side-step is sin(2*pi*f/F), the bounce is
|sin(2*pi*f/F)|, the maraca shake is sin(2*pi*SHAKEK*f/F) and the note bob is
sin/cos of 2*pi*f/F -- all equal at f=0 and f=F. Outputs the still + gif.
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
F      = 12         # frames in the loop
DUR    = 90         # ms/frame
STEP   = 7.0        # left<->right travel (px)
HOP    = 2.5        # bounce (px, two hops/loop)
SHAKE  = 17.0       # maraca shake amplitude (degrees)
SHAKEK = 2          # shakes per loop

# ---- body + hat layout (in the padded body canvas) --------------------
SCALE = 6                         # 12x8 art -> 72x48 body
SX, SY = 12*SCALE, 8*SCALE
AW, AH = 160, 116                 # body canvas
BX, BY = (AW - SX)//2, 52         # body top-left
CX0    = BX + SX//2               # body centre column
PYB, PXB = BY + SY//2, CX0        # body reference point (hips)
SHO_L = (BY + 18, CX0 - 20)       # shoulders (where the arms attach), body coords
SHO_R = (BY + 18, CX0 + 20)

# world placement of the body reference (keeps the dancer centred)
WPX, WPY = 64, 74

# ---- arm + maraca geometry --------------------------------------------
ARM_ANG  = 10       # rest angle above horizontal (degrees, pointing up-and-out)
LARM     = 7        # orange upper arm length
LHANDLE  = 9        # brown handle length (holds the bulb out past the arm)
BULB_R   = 6        # maraca bulb radius


def fill_disk(A, cy, cx, r, color):
    H, W = A.shape
    for dy in range(-r, r+1):
        for dx in range(-r, r+1):
            if dy*dy + dx*dx <= r*r:
                yy, xx = cy+dy, cx+dx
                if 0 <= yy < H and 0 <= xx < W:
                    A[yy, xx] = color


def thick_line(A, y0, x0, y1, x1, r, color):
    steps = int(max(abs(y1-y0), abs(x1-x0))) + 1
    for s in range(steps+1):
        t = s/steps
        fill_disk(A, int(round(y0+(y1-y0)*t)), int(round(x0+(x1-x0)*t)), r, color)


def draw_bulb(A, cy, cx, r):
    """A round gold maraca bulb, lit from the upper-left, with festive dots."""
    H, W = A.shape
    fill_disk(A, cy, cx, r, GOLD)
    for dy in range(-r, r+1):                          # shaded far crescent
        for dx in range(-r, r+1):
            if dy*dy + dx*dx <= r*r and dx > r*0.28 and dy > -r*0.3:
                yy, xx = cy+dy, cx+dx
                if 0 <= yy < H and 0 <= xx < W:
                    A[yy, xx] = STRAW_D
    if 0 <= cy - r//2 < H and 0 <= cx - r//2 < W:
        A[cy - r//2, cx - r//2] = STRAW_L              # sheen
    for (dy, dx, c) in ((0, 0, RED), (-2, 1, TEAL), (2, -1, RED)):
        if 0 <= cy+dy < H and 0 <= cx+dx < W:
            A[cy+dy, cx+dx] = c


def draw_sombrero(A):
    """A wide straw sombrero sitting on top of Clawd's head."""
    H, W = A.shape
    cx = CX0
    brim_y   = BY - 1
    crown_h  = 21
    crown_th = 11              # crown half-width at the top
    crown_bh = 15              # crown half-width at the base
    brim_hw  = 50              # brim half-width
    brim_th  = 4
    brim_dip = 3               # brim droops in the middle (front edge)
    brim_curl = 6              # brim tips curl up

    crown_top = brim_y - crown_h
    for ry in range(crown_top, brim_y + 1):
        t = (ry - crown_top) / crown_h
        hw = crown_th + (crown_bh - crown_th) * t
        if t < 0.30:
            hw *= math.sqrt(t / 0.30)
        hw = int(round(hw))
        for dx in range(-hw, hw + 1):
            x = cx + dx
            if not (0 <= x < W):
                continue
            frac = dx / max(hw, 1)
            c = STRAW_M
            if frac < -0.35:   c = STRAW_L
            elif frac > 0.45:  c = STRAW_D
            A[ry, x] = c

    for dx in range(-brim_hw, brim_hw + 1):
        x = cx + dx
        if not (0 <= x < W):
            continue
        tt = dx / brim_hw
        mid = brim_y + brim_dip * (1 - tt*tt) - brim_curl * (tt*tt)
        th = brim_th + (1 if abs(tt) > 0.82 else 0)
        for k in range(th + 1):
            y = int(round(mid - th/2 + k))
            if 0 <= y < H:
                if k == 0:        c = STRAW_L
                elif k >= th - 1: c = STRAW_D
                else:             c = STRAW_M
                A[y, x] = c

    band_y = brim_y - brim_th
    for dx in range(-crown_bh, crown_bh + 1):
        x = cx + dx
        if not (0 <= x < W):
            continue
        for k, c in ((0, GOLD), (1, RED), (2, RED), (3, GOLD)):
            y = band_y - 3 + k
            if 0 <= y < H:
                A[y, x] = c
    for gdx in range(-crown_bh + 3, crown_bh - 2, 6):
        x = cx + gdx
        if 0 <= x < W:
            A[band_y - 2, x] = GOLD

    for dx in range(-brim_hw + 4, brim_hw - 3, 7):     # gold bolita trim
        x = cx + dx
        tt = dx / brim_hw
        mid = brim_y + brim_dip * (1 - tt*tt) - brim_curl * (tt*tt)
        y = int(round(mid + brim_th/2 + 1))
        if 0 <= y < H and 0 <= x < W:
            A[y, x] = GOLD

    for dx in range(-crown_bh - 6, crown_bh + 7):      # brim shadow on the face
        x = cx + dx
        y = brim_y + brim_th
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
    draw_sombrero(A)
    A[border_mask(A > 0, pen_disk(2))] = WHITE
    return A


def build_arm():
    """Returns (arm, maraca, shoulder). The orange arm and the maraca (handle +
    bulb) are kept on separate layers so the arm can sit behind Clawd while the
    maraca is composited in *front* -- the handle then reads as held out over
    the arm, not tucked behind it. Rest pose points up-and-out to the right;
    it gets mirrored for the left arm. Both layers share the shoulder pivot, so
    rotating each by the same angle keeps the hand on the handle."""
    H = W = 80
    arm = np.zeros((H, W), dtype=np.uint8)
    mar = np.zeros((H, W), dtype=np.uint8)
    sy, sx = 60, 12                                    # shoulder (lower-left)
    a = math.radians(ARM_ANG)
    dx, dy = math.cos(a), -math.sin(a)                 # up-and-out
    hy, hx = sy + dy*LARM, sx + dx*LARM                # hand
    ey, ex = sy + dy*(LARM+LHANDLE), sx + dx*(LARM+LHANDLE)      # handle end
    by, bx = sy + dy*(LARM+LHANDLE+BULB_R), sx + dx*(LARM+LHANDLE+BULB_R)  # bulb
    thick_line(arm, sy, sx, hy, hx, 2, CLAWD)          # upper arm (~5px), behind
    arm[border_mask(arm > 0, pen_disk(2))] = WHITE
    thick_line(mar, hy, hx, ey, ex, 1, HANDLE)         # handle (~3px), in front
    draw_bulb(mar, int(round(by)), int(round(bx)), BULB_R)
    mar[border_mask(mar > 0, pen_disk(2))] = WHITE
    return arm, mar, (sy, sx)


BODY = build_body()
ARM_R, MAR_R, (SRY, SRX) = build_arm()
ARM_L = ARM_R[:, ::-1].copy()                          # mirror for the left side
MAR_L = MAR_R[:, ::-1].copy()
SLY, SLX = SRY, ARM_R.shape[1] - 1 - SRX


def _center_on(A, cy, cx):
    H, W = A.shape
    py, px = max(cy, H-1-cy), max(cx, W-1-cx)
    out = np.zeros((2*py+1, 2*px+1), dtype=np.uint8)
    out[py-cy:py-cy+H, px-cx:px-cx+W] = A
    return out


CEN_ARM_R = _center_on(ARM_R, SRY, SRX)                # shoulder at the centre
CEN_ARM_L = _center_on(ARM_L, SLY, SLX)
CEN_MAR_R = _center_on(MAR_R, SRY, SRX)
CEN_MAR_L = _center_on(MAR_L, SLY, SLX)


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


def place_arm(g, cen, sho, by0, bx0, angle):
    R = rot(cen, angle)
    wy, wx = by0 + sho[0], bx0 + sho[1]                # world shoulder
    blit(g, R, wy - R.shape[0]//2, wx - R.shape[1]//2)


# ---- music notes bobbing overhead ------------------------------------
NOTES = [(38, 3.0, 0.0), (90, 3.0, math.pi), (64, 3.5, 1.7)]  # (x, amp, phase)

def eighth_note(g, cy, cx, color):
    for dy in range(6):
        y, x = cy - dy, cx + 2
        if 0 <= y < N and 0 <= x < N: g[y, x] = color
    for dy in range(2):
        y, x = cy - 5 + dy, cx + 3
        if 0 <= y < N and 0 <= x < N: g[y, x] = color
    for dy in range(-1, 2):
        for dx in range(-1, 2):
            y, x = cy + dy, cx + dx
            if 0 <= y < N and 0 <= x < N: g[y, x] = color

def paint_notes(g, f):
    ph = 2*math.pi * f / F
    for nx, amp, phase in NOTES:
        y = int(round(26 + amp * math.sin(ph + phase)))
        x = int(round(nx + 2 * math.cos(ph + phase)))
        eighth_note(g, y, x, GOLD)


def compose(f):
    g = np.zeros((N, N), dtype=np.uint8)
    ph = 2*math.pi * f / F
    step = STEP * math.sin(ph)
    hop  = HOP * abs(math.sin(ph))
    by0 = int(round(WPY - hop)) - PYB
    bx0 = int(round(WPX + step)) - PXB
    shake = SHAKE * math.sin(2*math.pi * SHAKEK * f / F)

    paint_notes(g, f)                                  # behind everything
    place_arm(g, CEN_ARM_L, SHO_L, by0, bx0, shake)    # arms behind the body
    place_arm(g, CEN_ARM_R, SHO_R, by0, bx0, shake)
    blit(g, BODY, by0, bx0)                            # body + hat
    place_arm(g, CEN_MAR_L, SHO_L, by0, bx0, shake)    # maracas in front
    place_arm(g, CEN_MAR_R, SHO_R, by0, bx0, shake)

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

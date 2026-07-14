#!/usr/bin/env python3
"""'Barbie' Clawd -- chuck another snag on: Clawd works a proper Aussie
barbecue, flipping a sausage with a spatula while snags and a prawn sizzle
and smoke drifts up off the hotplate.

  Clawd    : the authentic sprite (full 2px white outline) standing *behind*
             the barbie, little legs hidden by the hotplate, with a gentle bob.
  arm      : an orange arm gripping a spatula -- one assembly rotated about the
             shoulder (bugcatcher's net swing), so it scoops up once per loop.
  the flip : one snag launches off the spatula, does a full mid-air rotation
             on a parabola, and lands back in its slot -- a pure function of
             frame mod F.
  barbie   : dark hotplate on a red cart with legs; two resting snags and a
             prawn stay put and sizzle.
  smoke    : little grey puffs rise off the plate, growing and fading; each
             puff's life is ((f/F) + phase) mod 1, so the column never pops.

Seamless by construction: the bob is sin(2*pi*f/F), the arm swing is the
positive lobe of sin(2*pi*(t - t0)) (zero at both ends of the loop), the
flight window [T_UP, T_DOWN] is interior to the loop, and every smoke puff is
a mod-1 function of f/F. Outputs the still + gif.
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
    (52, 52, 58),       # 4  hotplate dark
    (86, 86, 96),       # 5  hotplate grate line / steel
    (168, 44, 40),      # 6  cart red
    (120, 30, 28),      # 7  cart red shade
    (150, 82, 44),      # 8  snag brown
    (108, 56, 30),      # 9  snag shade
    (232, 148, 130),    # 10 prawn pink
    (198, 200, 206),    # 11 smoke light / spatula steel
    (232, 234, 238),    # 12 smoke lighter
    (94, 60, 34),       # 13 spatula handle wood
]
(T, CLAWD, EYE, WHITE, PLATE, STEEL, RED, RED_D,
 SNAG, SNAG_D, PRAWN, SMOKE1, SMOKE2, WOOD) = range(14)
pal_bytes = bytes([c for rgb in COLORS for c in rgb] + [0]*(768 - 3*len(COLORS)))

# ---- timing -----------------------------------------------------------
F   = 20           # frames in the loop
DUR = 85           # ms/frame
BOB = 1.5          # Clawd's idle bob (px)

# the flip: launch/land window (fractions of the loop, interior so it loops)
T_UP, T_DOWN = 0.25, 0.70
FLIP_H = 26        # apex height above the plate (px)

# arm swing: positive lobe of sin(2*pi*(t - T0)), peaking as the snag launches
ARM_T0, ARM_A = 0.05, 32.0

# ---- layout -----------------------------------------------------------
SCALE = 8                          # 12x8 art -> 96x64 body
BODY_Y, BODY_CX = 24, 56           # body top / centre column (world px)

PLATE_Y  = 72                      # hotplate top surface
PLATE_X0, PLATE_X1 = 10, 118       # hotplate extent
CART_Y0, CART_Y1 = 79, 98          # red cart box
LEG_Y1 = 120                       # feet of the barbie

SHOULDER = (BODY_Y + 24, BODY_CX + 38)     # right side-bump, world px
SNAG_SLOT = (PLATE_Y - 3, 104)             # the flip happens under the spatula
RESTING = [(PLATE_Y - 3, 36), (PLATE_Y - 3, 62)]   # snags that stay put
PRAWN_AT = (PLATE_Y - 2, 16)

# smoke puffs: (x, phase) -- rise from the plate, threading between the eyes
PUFFS = [(24, 0.00), (24, 0.50), (56, 0.25), (56, 0.75), (88, 0.40), (88, 0.90)]
SMOKE_RISE = 34


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


def blit(g, arr, y0, x0):
    ys, xs = np.nonzero(arr)
    for ry, rx in zip(ys, xs):
        wy, wx = y0 + ry, x0 + rx
        if 0 <= wy < N and 0 <= wx < N:
            g[wy, wx] = arr[ry, rx]


def build_body():
    """Clawd on a padded canvas, white outline, ready to blit behind the barbie."""
    pad = 4
    SX, SY = 12*SCALE, 8*SCALE
    A = np.zeros((SY + 2*pad, SX + 2*pad), dtype=np.uint8)
    for j, row in enumerate(ART):
        for i, ch in enumerate(row):
            if ch == ".":
                continue
            A[pad+j*SCALE:pad+(j+1)*SCALE, pad+i*SCALE:pad+(i+1)*SCALE] = \
                EYE if ch == "O" else CLAWD
    A[border_mask(A > 0, pen_disk(2))] = WHITE
    return A, pad


BODY, BPAD = build_body()


def build_arm():
    """Arm + spatula as one rigid piece; returns (layer, shoulder-in-layer).
    Rest pose reaches down-right toward the hotplate; rotating it
    counter-clockwise about the shoulder scoops the spatula up."""
    H = W = 72
    A = np.zeros((H, W), dtype=np.uint8)
    sy, sx = 20, 14                                   # shoulder (upper-left)
    a = math.radians(-50)                             # down-and-out
    dy, dx = -math.sin(a), math.cos(a)
    hy, hx = sy + dy*12, sx + dx*12                   # hand
    ey, ex = sy + dy*22, sx + dx*22                   # end of the handle
    thick_line(A, sy, sx, hy, hx, 3, CLAWD)           # orange arm
    thick_line(A, hy, hx, ey, ex, 1, WOOD)            # wooden handle
    # flat steel blade, perpendicular-ish to the handle (sampled at half-px
    # steps -- integer steps along a diagonal leave holes for the outline
    # pen to fill, which reads as a checkerboard)
    py, px = -dx, dy                                  # unit normal
    for s in np.arange(0, 8.51, 0.5):                 # blade length
        by, bx = ey + dy*s, ex + dx*s
        for w in np.arange(-4, 4.01, 0.5):            # blade width
            y, x = int(round(by + py*w)), int(round(bx + px*w))
            if 0 <= y < H and 0 <= x < W:
                A[y, x] = SMOKE1 if s >= 1 else STEEL
    A[border_mask(A > 0, pen_disk(1))] = WHITE
    return A, (sy, sx)


ARM, (ASY, ASX) = build_arm()


def _center_on(A, cy, cx):
    H, W = A.shape
    py, px = max(cy, H-1-cy), max(cx, W-1-cx)
    out = np.zeros((2*py+1, 2*px+1), dtype=np.uint8)
    out[py-cy:py-cy+H, px-cx:px-cx+W] = A
    return out


CEN_ARM = _center_on(ARM, ASY, ASX)


def rot(arr, angle):
    im = Image.new("P", (arr.shape[1], arr.shape[0]))
    im.putpalette(pal_bytes)
    im.frombytes(arr.tobytes())
    r = im.rotate(angle, resample=Image.NEAREST, expand=True, fillcolor=0)
    return np.asarray(r)


def build_snag():
    """One sausage: a fat little capsule with a shaded underside."""
    A = np.zeros((14, 22), dtype=np.uint8)
    thick_line(A, 6, 5, 6, 16, 3, SNAG)
    for x in range(3, 19):                            # shaded underside
        if A[9, x] == SNAG:
            A[9, x] = SNAG_D
    A[border_mask(A > 0, pen_disk(1))] = WHITE
    return A


SNAG_SPR = build_snag()


def draw_barbie(g):
    """Hotplate + red cart + legs, drawn over Clawd's little legs."""
    g[PLATE_Y:PLATE_Y+5, PLATE_X0:PLATE_X1] = PLATE
    for x in range(PLATE_X0 + 4, PLATE_X1 - 3, 8):    # grate sheen lines
        g[PLATE_Y, x:x+3] = STEEL
    g[PLATE_Y+5:CART_Y0, PLATE_X0+2:PLATE_X1-2] = PLATE          # plate lip
    g[CART_Y0:CART_Y1, PLATE_X0+6:PLATE_X1-6] = RED              # cart box
    g[CART_Y0:CART_Y1, PLATE_X1-16:PLATE_X1-6] = RED_D           # shaded end
    g[CART_Y0+7:CART_Y0+9, PLATE_X0+10:PLATE_X1-10] = RED_D      # panel line
    g[CART_Y0+3:CART_Y0+6, PLATE_X0+11:PLATE_X0+16] = STEEL      # gas knob
    for lx in (PLATE_X0 + 12, PLATE_X1 - 16):                    # legs
        g[CART_Y1:LEG_Y1, lx:lx+4] = PLATE
    g[LEG_Y1-2:LEG_Y1, PLATE_X0+8, ] = PLATE
    g[LEG_Y1-2:LEG_Y1, PLATE_X0+8:PLATE_X0+20] = PLATE           # little feet
    g[LEG_Y1-2:LEG_Y1, PLATE_X1-20:PLATE_X1-8] = PLATE


def draw_prawn(g, cy, cx):
    """A little curled prawn on the grill."""
    for (dy, dx) in ((0, -3), (-1, -2), (-2, -1), (-2, 0), (-2, 1),
                     (-1, 2), (0, 2), (1, 1), (1, 0)):
        y, x = cy + dy, cx + dx
        if 0 <= y < N and 0 <= x < N:
            g[y, x] = PRAWN
    if 0 <= cy - 1 < N and 0 <= cx + 3 < N:
        g[cy - 1, cx + 3] = SNAG_D                    # tail flick


def flip_pose(t):
    """(height above slot, rotation degrees) of the flipping snag at time t."""
    if not (T_UP <= t <= T_DOWN):
        return 0.0, 0.0
    u = (t - T_UP) / (T_DOWN - T_UP)
    return FLIP_H * 4 * u * (1 - u), 360.0 * u


def draw_smoke(g, f):
    for (x, phase) in PUFFS:
        life = ((f / F) + phase) % 1.0
        y = int(round(PLATE_Y - 4 - life * SMOKE_RISE))
        r = 1 if life < 0.35 else 2
        if life > 0.8:                                # fade out and vanish
            continue
        color = SMOKE1 if life < 0.5 else SMOKE2
        wob = int(round(2 * math.sin(2*math.pi * (2*life + phase))))
        fill_disk(g, y, x + wob, r, color)


def compose(f):
    g = np.zeros((N, N), dtype=np.uint8)
    t = f / F
    ph = 2*math.pi * t
    bob = round(BOB * math.sin(ph))

    SX = 12*SCALE
    blit(g, BODY, BODY_Y + bob - BPAD, BODY_CX - SX//2 - BPAD)   # Clawd

    swing = ARM_A * max(0.0, math.sin(2*math.pi * (t - ARM_T0)))
    R = rot(CEN_ARM, swing)
    blit(g, R, SHOULDER[0] + bob - R.shape[0]//2,
         SHOULDER[1] - R.shape[1]//2)                 # arm + spatula

    draw_smoke(g, f)                                  # plate smoke drifts up
                                                      # in front of Clawd

    draw_barbie(g)                                    # barbie covers his legs

    for (sy, sx) in RESTING:                          # the snags that stay put
        blit(g, SNAG_SPR, sy - SNAG_SPR.shape[0]//2, sx - SNAG_SPR.shape[1]//2)
    draw_prawn(g, *PRAWN_AT)

    h, ang = flip_pose(t)                             # the star of the show
    S = rot(SNAG_SPR, ang) if ang else SNAG_SPR
    blit(g, S, int(round(SNAG_SLOT[0] - h)) - S.shape[0]//2,
         SNAG_SLOT[1] - S.shape[1]//2)

    im = Image.frombytes("P", (N, N), g.tobytes())
    im.putpalette(pal_bytes)
    return im


frames = [compose(f) for f in range(F)]
frames[0].save(OUT / "clawd_barbie_still.png")
frames[0].save(OUT / "clawd_barbie.gif", save_all=True, append_images=frames[1:],
               duration=DUR, loop=0, transparency=0, disposal=2, optimize=False)
import os
print(f"barbie: {F} frames @ {DUR}ms, "
      f"gif={os.path.getsize(OUT / 'clawd_barbie.gif')//1024} KB")

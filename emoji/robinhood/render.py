#!/usr/bin/env python3
"""'Robin Hood' Clawd -- a cute forest archer: Clawd in a pointed feathered cap
and a green tunic with a belt and little boots, a quiver slung across his back,
drawing a bow and loosing an arrow that streaks off to the right, over and over.
Rendered on the full 128 grid (CELL=1) like surf/mariachi so the bow curve, the
string and the arrow stay crisp; Clawd is drawn big so he fills most of the frame
(the bow tucks against the right edge, so the loosed arrow has only a short run --
its whoosh sells the shot).

  body + hat  : Clawd (full 2px white outline) recoloured into a green tunic
                (belt + buckle, zig-zag hem, boots) and a pointed cap with an
                up-turned brim and a red feather. Clawd's own side bumps ARE his
                arms: the right one reaches out to hold the bow (a short forearm
                joins it to the grip), the left one bends inward to draw.
  bow         : a wooden bow held just off his right hand -- a single static piece
                (the whole shot happens on the string).
  shot        : the left arm draws the string + nocked arrow back to the cheek,
                looses it with a forward snap + twang, and the arrow streaks off
                to the right with a little whoosh before a fresh arrow is nocked.
  quiver      : arrows angled off his back, fletchings over the left shoulder.

Seamless by construction: full-draw (the aim) is identical at f=0 and f=F; the
string snaps forward on release and a damped return brings it back to the draw by
the last frame, and the loosed arrow clears the right edge before the loop wraps
-- so only a fresh nocked arrow re-appears, the natural "re-load" beat.

All the pixel geometry is expressed as sc(v) = round(v*SCALE/6), i.e. multiples of
the original SCALE=6 tuning, so bumping SCALE rescales the whole archer coherently.
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
    (0, 0, 0),          # 0  transparent
    (218, 119, 88),     # 1  CLAWD body  #DA7758
    (0, 0, 0),          # 2  eye
    (255, 255, 255),    # 3  white outline
    (163, 84, 60),      # 4  body shade (brim shadow on the face)
    (92, 150, 66),      # 5  tunic / cap green (light)
    (58, 110, 50),      # 6  tunic / cap green (dark)
    (94, 60, 34),       # 7  belt / hatband (brown)
    (226, 184, 84),     # 8  buckle (gold)
    (70, 46, 28),       # 9  boots / quiver (dark brown)
    (156, 110, 60),     # 10 bow wood (light)
    (110, 74, 40),      # 11 bow wood (dark)
    (238, 238, 228),    # 12 bowstring / whoosh (pale)
    (188, 144, 90),     # 13 arrow shaft (wood)
    (176, 182, 190),    # 14 arrowhead (steel)
    (200, 58, 54),      # 15 feather / fletching (red)
]
(T, CLAWD, EYE, WHITE, SHADE, TUN_L, TUN_D, BELT, BUCKLE, BOOT,
 BOW_L, BOW_D, STRING, SHAFT, HEAD, RED) = range(16)
pal_bytes = bytes([c for rgb in COLORS for c in rgb] + [0]*(768 - 3*len(COLORS)))

# ---- timing -----------------------------------------------------------
F        = 18       # frames in the loop
DUR      = 75       # ms/frame
RELEASE  = 7        # last aim frame; the string looses on RELEASE -> RELEASE+1

# ---- body layout (built in a padded canvas, then blitted) -------------
SCALE    = 8                       # 12x8 art -> 96x64 (big: fills the frame)
def sc(v):                         # scale a SCALE=6-era pixel constant
    return int(round(v * SCALE / 6))

SXP, SYP = 12*SCALE, 8*SCALE
BOX, BOY = 10, 36                  # Clawd top-left in the canvas (room above for cap)
AW, AH   = 120, BOY + SYP + 8
HCX      = BOX + SXP//2            # head centre column (canvas)
BODY_Y0, BODY_X0 = 0, -2           # blit offset (world = canvas + offset)

def _w(cy, cx):                    # canvas point -> world point
    return cy + BODY_Y0, cx + BODY_X0

# Clawd's side bumps (ART rows 2-3, cols 0-1 and 10-11) ARE his arms:
ARM_L_ELBOW = _w(BOY + 3*SCALE, BOX + SCALE)         # centre of the left bump
ARM_R_HAND  = _w(BOY + 3*SCALE, BOX + 12*SCALE - 2)  # right bump, outer edge

# ---- bow + shot geometry (world coords) -------------------------------
GRIP    = (ARM_R_HAND[0] - sc(4), ARM_R_HAND[1] + sc(8))   # just up-and-off the hand
LIMB    = sc(18)                          # half bow length
BOW_BULGE = sc(8)                         # how far the bow bows out (right)
STR_X   = GRIP[1] - sc(4)                 # string brace column (bow tips)
TIP_T   = (GRIP[0] - LIMB, STR_X)         # top bow tip
TIP_B   = (GRIP[0] + LIMB, STR_X)         # bottom bow tip

NOCK_Y  = GRIP[0]                         # arrow / string-nock height (cheek level)
DRAW_X  = ARM_L_ELBOW[1] + sc(28)         # full-draw nock column (left cheek)
PARTIAL_X = DRAW_X + sc(11)                # nock at the start of the draw (loop rest)
BRACE_X = STR_X                           # relaxed (loosed) string column
ARROWLEN = GRIP[1] - DRAW_X - sc(2)       # nock -> tip (head lands at the grip)
FLYSPD   = sc(10)                         # loosed-arrow travel (px/frame)


# ======================================================================
# small drawing helpers
# ======================================================================
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


def ease(t):
    t = min(max(t, 0.0), 1.0)
    return t*t*(3 - 2*t)


# ======================================================================
# Clawd body: green tunic + belt + boots + feathered cap + quiver
# ======================================================================
def draw_quiver(A):
    """A quiver slung across the back: three arrows angled steeply up-and-left off
    the shoulder, their fletched tops poking well clear (drawn behind Clawd, so
    his body hides where they tuck into the quiver)."""
    vy, vx = -0.966, -0.26                          # steeply up, leaning left
    py, px = -vx, vy                                # perpendicular (fans the arrows)
    base = (BOY + sc(16), BOX + sc(11))             # behind the left shoulder
    L = sc(22)
    for k, col in ((-1, RED), (0, WHITE), (1, RED)):
        by = base[0] + py*k*sc(4)
        bx = base[1] + px*k*sc(4)
        ty, tx = by + vy*L, bx + vx*L
        thick_line(A, int(round(by)), int(round(bx)), int(round(ty)), int(round(tx)), 1, SHAFT)
        for m in range(sc(6)):                      # feathered fletching along the top
            cy, cx = ty - vy*m, tx - vx*m
            reach = sc(2) if m < sc(3) else sc(1)
            for r in range(0, reach + 1):
                for s in (-1, 1):
                    y, x = int(round(cy + py*s*r)), int(round(cx + px*s*r))
                    if 0 <= y < AH and 0 <= x < AW:
                        A[y, x] = col


def draw_tunic(A):
    """Recolour Clawd's lower torso into a belted green tunic with a zig-zag hem
    and little boots on the leg tips."""
    y_top = BOY + 3*SCALE          # tunic starts at art row 3 (shoulders)
    y_hem = BOY + 6*SCALE          # ...down to the top of the legs
    for y in range(y_top, y_hem):
        xs = [x for x in range(AW) if A[y, x] == CLAWD]
        if not xs:
            continue
        x0, x1 = min(xs), max(xs)
        mid = (x0 + x1) / 2
        half = max(1, (x1 - x0) / 2)
        for x in range(x0, x1 + 1):
            if A[y, x] != CLAWD:
                continue
            frac = (x - mid) / half
            A[y, x] = TUN_D if frac > 0.25 else TUN_L
    # collar shadow along the very top of the tunic
    for x in range(AW):
        if A[y_top, x] == TUN_L:
            A[y_top, x] = TUN_D

    # zig-zag hem: green points drooping just below the tunic over the legs
    period = max(2, sc(3))
    for x in range(AW):
        if A[y_hem - 1, x] in (TUN_L, TUN_D):
            depth = sc(3) if ((x - BOX) // period) % 2 == 0 else sc(1)
            for d in range(depth):
                y = y_hem + d
                if 0 <= y < AH and A[y, x] in (CLAWD, 0):
                    A[y, x] = TUN_D if d == depth - 1 else TUN_L

    # belt across the waist with a buckle
    by = BOY + 5*SCALE - sc(1)
    xs = [x for x in range(AW) if A[by, x] in (TUN_L, TUN_D)]
    if xs:
        x0, x1 = min(xs), max(xs)
        for x in range(x0, x1 + 1):
            for k in range(sc(3)):
                y = by + k
                if 0 <= y < AH and A[y, x] in (TUN_L, TUN_D):
                    A[y, x] = BELT
        for dy in range(sc(3)):
            for dx in range(-sc(1), sc(1) + 1):
                y, x = by + dy, HCX + dx
                if 0 <= y < AH and 0 <= x < AW and A[y, x] == BELT:
                    A[y, x] = BUCKLE

    # boots on the leg tips (bottom of art rows 6-7)
    for y in range(BOY + 7*SCALE, BOY + 8*SCALE):
        for x in range(AW):
            if A[y, x] == CLAWD:
                A[y, x] = BOOT


def draw_cap(A):
    """A pointed forest cap: a rounded crown that flops back to a point, an
    up-turned brim with a small front peak, a brown hatband, and a red feather."""
    cx = HCX
    brim_y = BOY + 1               # brim rides just above the eyes
    peak = (BOY - sc(13), cx - sc(13))     # the crown flops up-and-back (left)

    ch = brim_y - peak[0]
    for ry in range(peak[0], brim_y + 1):
        t = (brim_y - ry) / ch                     # 0 at brim .. 1 at the point
        cxr = cx - (cx - peak[1]) * (t**1.3)       # centre drifts to the point
        hw = int(round(sc(16) * (1 - 0.85*t) + 1))
        for dx in range(-hw, hw + 1):
            x = int(round(cxr)) + dx
            if 0 <= x < AW:
                A[ry, x] = TUN_D if dx / max(hw, 1) > 0.15 else TUN_L

    brim_hw = sc(21)
    th = max(3, sc(3))
    for dx in range(-brim_hw, brim_hw + sc(4)):
        x = cx + dx
        if not (0 <= x < AW):
            continue
        tt = dx / brim_hw
        lift = sc(5) * (tt*tt) + (sc(3) if tt > 0.55 else 0)   # curls up, higher at front
        mid = brim_y - lift
        for k in range(th):
            y = int(round(mid + k))
            if 0 <= y < AH:
                A[y, x] = TUN_L if k == 0 else (TUN_D if k == th-1 else TUN_L)
    for hb in range(max(1, sc(1))):                 # brown hatband
        for dx in range(-sc(15), sc(15) + 1):
            x = cx + dx
            if 0 <= x < AW:
                A[brim_y - sc(3) + hb, x] = BELT

    # feather: a fuller plume sweeping up-and-right from the right of the band
    fy0, fx0 = brim_y - sc(4), cx + sc(14)
    flen = min(sc(20), fy0 - 3)                      # keep the tip in-frame
    pts = [(fy0 - i, fx0 + int(round(0.75*i - 0.02*i*i))) for i in range(flen)]
    for i, (y, x) in enumerate(pts):                # shaft
        if 0 <= y < AH and 0 <= x < AW:
            A[y, x] = RED
    for i, (y, x) in enumerate(pts):                # plume: barbs off both sides
        w = 2 if 3 <= i <= flen - 4 else 1
        for s in (-1, 1):
            for k in range(1, w + 1):
                yy, xx = y + k*s, x + (1 if s > 0 else -1)
                if 0 <= yy < AH and 0 <= xx < AW and A[yy, xx] == 0:
                    A[yy, xx] = WHITE if (i % 4 == 0 and k == w) else RED


def build_body():
    A = np.zeros((AH, AW), dtype=np.uint8)
    draw_quiver(A)                                  # behind Clawd (drawn first)
    for j, row in enumerate(ART):
        for i, ch in enumerate(row):
            if ch == ".":
                continue
            A[BOY+j*SCALE:BOY+(j+1)*SCALE, BOX+i*SCALE:BOX+(i+1)*SCALE] = \
                EYE if ch == "O" else CLAWD
    # right arm: a short forearm from the right bump out to the bow grip
    thick_line(A, ARM_R_HAND[0] - BODY_Y0, ARM_R_HAND[1] - BODY_X0,
               GRIP[0] - BODY_Y0, GRIP[1] - BODY_X0, sc(2), CLAWD)
    draw_tunic(A)
    draw_cap(A)
    # one clean 2px white outline around the whole silhouette
    A[border_mask(A > 0, pen_disk(2))] = WHITE
    # brim shadow just above the eyes
    for dx in range(-sc(13), sc(13) + 1):
        x = HCX + dx
        for y in (BOY + sc(3), BOY + sc(4)):
            if 0 <= y < AH and 0 <= x < AW and A[y, x] == CLAWD:
                A[y, x] = SHADE
    return A


# ======================================================================
# bow: one static piece (a wooden arc + riser)
# ======================================================================
def build_bow():
    A = np.zeros((N, N), dtype=np.uint8)
    gy, gx = GRIP
    for t in range(0, 201):                         # limbs: quadratic arc, convex right
        u = t / 200.0
        y = TIP_T[0] + (TIP_B[0] - TIP_T[0]) * u
        bow = 4 * BOW_BULGE * u * (1 - u)
        x = STR_X + bow
        yi, xi = int(round(y)), int(round(x))
        for k in range(max(2, sc(2))):
            xx = xi + k
            if 0 <= yi < N and 0 <= xx < N:
                A[yi, xx] = BOW_L if k == 0 else BOW_D
    fill_disk(A, gy, gx, sc(3), BOW_D)              # riser / grip
    fill_disk(A, gy, gx - sc(1), sc(2), BOW_L)
    A[border_mask(A > 0, pen_disk(2))] = WHITE
    return A


BODY = build_body()
BOW  = build_bow()


def blit(g, arr, y0, x0):
    ys, xs = np.nonzero(arr)
    for ry, rx in zip(ys, xs):
        wy, wx = y0 + ry, x0 + rx
        if 0 <= wy < N and 0 <= wx < N:
            g[wy, wx] = arr[ry, rx]


# ======================================================================
# per-frame pieces: string, arrow, draw-arm
# ======================================================================
def draw_string(g, nock_x):
    """Bowstring from the top tip, through the nock, to the bottom tip."""
    thick_line(g, TIP_T[0], TIP_T[1], NOCK_Y, nock_x, 0, STRING)
    thick_line(g, NOCK_Y, nock_x, TIP_B[0], TIP_B[1], 0, STRING)


def draw_arrow(g, nx, whoosh=False):
    """A RIGHT-pointing arrow whose nock is at (NOCK_Y, nx): fletching at the back
    (the nock), a wood shaft, and a steel head that tapers to a point at the tip."""
    ny = NOCK_Y
    tipx = nx + ARROWLEN
    sth = max(2, sc(2))                             # shaft thickness
    y0 = ny - (sth - 1)//2
    for x in range(nx, tipx - sc(3)):               # shaft
        if 0 <= x < N:
            for t in range(sth):
                yy = y0 + t
                if 0 <= yy < N:
                    g[yy, x] = BOW_D if t == sth-1 else SHAFT
    for dx in range(0, sc(5)):                      # head: point at tipx, base left
        x = tipx - dx
        hw = int(round(dx * 0.6))
        for dy in range(-hw, hw + 1):
            if 0 <= ny+dy < N and 0 <= x < N:
                g[ny+dy, x] = HEAD
    for i in range(sc(6)):                          # fletching: flares at the back
        x = nx + i
        reach = max(0, sc(3) - i // 2)
        for s, col in ((-1, RED), (1, WHITE)):
            for k in range(1, reach + 1):
                y = ny + s * k
                if 0 <= y < N and 0 <= x < N:
                    g[y, x] = col
    if whoosh:                                      # streaks trailing a loosed arrow
        for k, dx in enumerate((sc(4), sc(9), sc(14))):
            x = nx - dx
            for dy in (-1, 1):
                y = ny + dy * (k % 2)
                if 0 <= y < N and 0 <= x < N:
                    g[y, x] = STRING


def draw_arm(g, hand_x, open_hand=False):
    """Left draw-arm: Clawd's left bump bends inward, the fist gripping the string
    at the cheek. The hand only travels between the partial and full draw, so the
    arm reaches inward to draw and never sprawls out or crosses the face."""
    L = np.zeros((N, N), dtype=np.uint8)
    thick_line(L, ARM_L_ELBOW[0], ARM_L_ELBOW[1], NOCK_Y, hand_x, sc(2), CLAWD)
    fill_disk(L, NOCK_Y, hand_x, sc(2), CLAWD)
    if open_hand:                                   # fingers flick open on release
        for dy, dx in ((-sc(3), sc(1)), (-sc(3), -sc(1)), (sc(3), sc(1)), (0, sc(3))):
            y, x = NOCK_Y + dy, hand_x + dx
            if 0 <= y < N and 0 <= x < N:
                L[y, x] = CLAWD
    L[border_mask(L > 0, pen_disk(2))] = WHITE
    blit(g, L, 0, 0)


def aim_nock_x(f):
    """During the draw the nock is pulled from a partial draw to full draw."""
    return PARTIAL_X - (PARTIAL_X - DRAW_X) * ease(f / RELEASE)


def string_nock_x(f):
    """Where the string sits this frame. Tracks the draw during the aim; on
    release it snaps forward to brace, then a damped return brings it back to the
    partial-draw rest by the last frame, so f=0 and f=F match."""
    if f <= RELEASE:
        return aim_nock_x(f)
    u = (f - RELEASE) / (F - RELEASE)               # 0+ just after release .. 1 at wrap
    env = (1 - ease(u)) * (1 + 0.22*math.sin(u*6*math.pi))   # forward + twang -> 0
    return PARTIAL_X + (BRACE_X - PARTIAL_X) * max(env, 0.0)


def hand_x(f):
    """The draw fist: follows the string during the draw, then drifts forward to
    nock the next arrow."""
    if f <= RELEASE:
        return aim_nock_x(f)
    u = (f - RELEASE) / (F - RELEASE)
    return DRAW_X + (PARTIAL_X - DRAW_X) * ease(u)


# ======================================================================
# compose one frame
# ======================================================================
def compose(f):
    g = np.zeros((N, N), dtype=np.uint8)
    blit(g, BODY, BODY_Y0, BODY_X0)
    blit(g, BOW, 0, 0)

    snx = int(round(string_nock_x(f)))
    draw_string(g, snx)

    if f <= RELEASE:                                 # nocked arrow, drawn back
        draw_arrow(g, int(round(aim_nock_x(f))))
    elif f >= F - 3:                                 # a fresh arrow, re-nocked
        draw_arrow(g, snx)
    if f > RELEASE:                                  # loosed arrow in flight
        fly_nx = DRAW_X + FLYSPD * (f - RELEASE)
        if fly_nx < N:
            draw_arrow(g, int(round(fly_nx)), whoosh=True)

    draw_arm(g, int(round(hand_x(f))), open_hand=(f == RELEASE + 1))

    im = Image.frombytes("P", (CANVAS, CANVAS), g.tobytes())
    im.putpalette(pal_bytes)
    return im


frames = [compose(f) for f in range(F)]
frames[RELEASE].save(OUT / "clawd_robinhood_still.png")     # full-draw: the iconic pose
frames[0].save(OUT / "clawd_robinhood.gif", save_all=True, append_images=frames[1:],
               duration=DUR, loop=0, transparency=0, disposal=2, optimize=False)
import os
print(f"robinhood: {F} frames @ {DUR}ms, SCALE={SCALE}, "
      f"gif={os.path.getsize(OUT / 'clawd_robinhood.gif')//1024} KB")

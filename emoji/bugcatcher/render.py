#!/usr/bin/env python3
"""'Bug catcher' Clawd -- Clawd out in a sunny field in a pith helmet and a
collector's satchel, swinging a handheld net at a butterfly that keeps
fluttering just out of reach. Rendered on the full 128 grid (CELL=1) like surf
and mariachi so the helmet dome, the net hoop and the butterfly stay crisp.

  field       : blue sky over a green meadow with a few swaying blades and
                flowers, plus a specimen jar sitting in the grass (equipment).
  Clawd       : full 2px white outline, in a khaki pith helmet with a strap-slung
                satchel -- one rigid piece, with a tiny bob.
  net         : an orange arm grips a long pole ending in a mesh hoop; the whole
                arm+pole+net is ONE assembly rotated about the shoulder so it
                swings up and back once per loop.
  butterfly   : flaps its wings and flies a little evasive loop, staying a few
                pixels above the hoop at the top of every swing -- so close.

Seamless by construction: the net swing is sin(2*pi*f/F), the butterfly path is
sin/cos of 2*pi*f/F, the wing flap is cos(2*pi*FLAPK*f/F) and the grass sway is
sin(2*pi*f/F) -- all equal at f=0 and f=F. Outputs the still + gif.
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
CANVAS = N * CELL

# ---- palette ----------------------------------------------------------
COLORS = [
    (0, 0, 0),          # 0  transparent (reserved; the scene fills the square)
    (218, 119, 88),     # 1  CLAWD body  #DA7758
    (0, 0, 0),          # 2  eye
    (255, 255, 255),    # 3  white outline
    (163, 84, 60),      # 4  body shade (under the helmet brim)
    (150, 208, 236),    # 5  sky
    (185, 227, 246),    # 6  sky (upper, lighter) / soft cloud edge
    (122, 201, 98),     # 7  grass light (sunlit tops)
    (82, 168, 74),      # 8  grass mid
    (52, 130, 60),      # 9  grass dark
    (247, 208, 74),     # 10 flower yellow / centre
    (233, 104, 138),    # 11 flower pink
    (208, 186, 120),    # 12 helmet khaki light
    (168, 142, 86),     # 13 helmet khaki dark
    (120, 84, 48),      # 14 net pole / handle brown
    (176, 182, 190),    # 15 net hoop metal (silver-grey)
    (226, 238, 242),    # 16 net mesh (pale)
    (188, 208, 216),    # 17 net mesh grid line
    (122, 132, 74),     # 18 satchel canvas (olive)
    (243, 140, 52),     # 19 butterfly orange
    (64, 124, 208),     # 20 butterfly blue spot
    (44, 34, 42),       # 21 dark (butterfly body / outline / antennae)
    (234, 243, 250),    # 22 soft cloud
]
(T, CLAWD, EYE, WHITE, SHADE, SKY, SKY_HI, GRASS_L, GRASS_M, GRASS_D,
 FLOWER_Y, FLOWER_P, HELM_L, HELM_D, POLE, HOOP, MESH, MESH_D, SATCH,
 BFLY, BFLY2, DARK, CLOUD) = range(23)
pal_bytes = bytes([c for rgb in COLORS for c in rgb] + [0]*(768 - 3*len(COLORS)))

# ---- timing / motion --------------------------------------------------
F      = 16         # frames in the loop
DUR    = 80         # ms/frame
FLAPK  = 3          # butterfly wing-flaps per loop
GSWAY  = 3.0        # grass sway amplitude (px)

# ---- world layout -----------------------------------------------------
HORIZON = 76        # top row of the grass

# body built in a local canvas, then blitted at a fixed spot (+ tiny bob)
AW, AH   = 110, 118
SCALE    = 6                       # 12x8 art -> 72x48
SXP, SYP = 12*SCALE, 8*SCALE
BOX, BOY = 19, 40                  # Clawd top-left inside the body canvas
HELM_CX  = BOX + SXP//2            # helmet centre column (= body centre)
SHO_LOC  = (BOY + 13, BOX + SXP - 6)    # net-arm shoulder, body-canvas coords
BODY_Y0, BODY_X0 = 21, -11         # placed so the net shoulder lands ~(74,74)
FEET_LOC = BOY + SYP               # 88 -> world 109

# ---- net (arm + pole + mesh hoop) -------------------------------------
MID     = 44        # rest swing angle above horizontal (degrees, up-and-right)
AMP     = 22        # swing amplitude (degrees, one up-and-back per loop)
LARM    = 14        # orange upper-arm length
LPOLE   = 15        # brown pole length (hand -> hoop rim)
HOOP_R  = 12        # net hoop radius

# ---- butterfly --------------------------------------------------------
BFX, BFY = 95, 32   # nominal flutter centre
BFAX, BFAY = 8, 6   # flutter drift amplitudes


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


def fill_ellipse(A, cy, cx, ry, rx, color):
    ry = max(1, ry); rx = max(1, rx)
    H, W = A.shape
    for dy in range(-ry, ry+1):
        for dx in range(-rx, rx+1):
            if (dy/ry)**2 + (dx/rx)**2 <= 1.0:
                yy, xx = cy+dy, cx+dx
                if 0 <= yy < H and 0 <= xx < W:
                    A[yy, xx] = color


def thick_line(A, y0, x0, y1, x1, r, color):
    steps = int(max(abs(y1-y0), abs(x1-x0))) + 1
    for s in range(steps+1):
        t = s/steps
        fill_disk(A, int(round(y0+(y1-y0)*t)), int(round(x0+(x1-x0)*t)), r, color)


# ======================================================================
# Clawd body + pith helmet + satchel  (one rigid, outlined piece)
# ======================================================================
def draw_helmet(A):
    """A khaki pith helmet: a rounded dome on a darker band, a wide brim that
    curves down at the tips, and a little top knob. Sits high so Clawd's eyes
    stay clear below it."""
    cx = HELM_CX
    brim_y   = BOY + 1                 # brim rides the crown; eyes stay below
    dome_top = brim_y - 19
    dome_bh  = 19                      # dome half-width at its base
    brim_hw  = 30                      # brim half-width (wider than the head)
    dome_h   = brim_y - dome_top

    # rounded dome (half-ellipse profile, lit from the upper-left)
    for ry in range(dome_top, brim_y + 1):
        v = (brim_y - ry) / dome_h                 # 1 at the top .. 0 at the brim
        hw = int(round(dome_bh * math.sqrt(max(1 - v*v, 0))))
        for dx in range(-hw, hw + 1):
            x = cx + dx
            if 0 <= x < A.shape[1]:
                A[ry, x] = HELM_D if dx / max(hw, 1) > 0.3 else HELM_L
    # dark band around the base of the dome
    for dx in range(-dome_bh, dome_bh + 1):
        x = cx + dx
        if 0 <= x < A.shape[1]:
            for k in range(2):
                y = brim_y - 2 + k
                if 0 <= y < A.shape[0]:
                    A[y, x] = HELM_D
    # wide brim, curving down a touch at the tips
    for dx in range(-brim_hw, brim_hw + 1):
        x = cx + dx
        if not (0 <= x < A.shape[1]):
            continue
        tt = dx / brim_hw
        mid = brim_y + 1 + 2.0 * (tt*tt)
        th = 3
        for k in range(th):
            y = int(round(mid - 1 + k))
            if 0 <= y < A.shape[0]:
                A[y, x] = HELM_L if k == 0 else (HELM_D if k == th-1 else HELM_L)
    # top knob
    for dy in range(-2, 1):
        for dx in range(-1, 2):
            x, y = cx + dx, dome_top - 1 + dy
            if 0 <= y < A.shape[0] and 0 <= x < A.shape[1]:
                A[y, x] = HELM_L


def draw_satchel(A):
    """A collector's satchel slung on a diagonal strap across the body."""
    # strap: right shoulder -> left hip
    thick_line(A, BOY + 11, BOX + SXP - 14, BOY + 37, BOX + 12, 2, SATCH)
    # bag on the left hip
    bx0, by0 = BOX + 2, BOY + 30
    fill_ellipse(A, by0 + 7, bx0 + 7, 9, 10, SATCH)
    for dx in range(-10, 11):                      # flap across the top
        x = bx0 + 7 + dx
        if 0 <= x < A.shape[1]:
            A[by0, x] = HELM_D
            A[by0 + 1, x] = HELM_D


def build_body():
    A = np.zeros((AH, AW), dtype=np.uint8)
    for j, row in enumerate(ART):
        for i, ch in enumerate(row):
            if ch == ".":
                continue
            A[BOY+j*SCALE:BOY+(j+1)*SCALE, BOX+i*SCALE:BOX+(i+1)*SCALE] = \
                EYE if ch == "O" else CLAWD
    draw_satchel(A)
    draw_helmet(A)
    # one clean 2px white outline around the whole silhouette
    A[border_mask(A > 0, pen_disk(2))] = WHITE
    # brim shadow on the forehead, just above the eyes (after the outline)
    for dx in range(-15, 16):
        x = HELM_CX + dx
        for y in (BOY + 4, BOY + 5):
            if 0 <= y < AH and 0 <= x < AW and A[y, x] == CLAWD:
                A[y, x] = SHADE
    return A


# ======================================================================
# net: arm + pole + mesh hoop, built once along the rest angle
# ======================================================================
def build_net():
    H = W = 150
    A = np.zeros((H, W), dtype=np.uint8)
    sy, sx = 118, 36                          # shoulder, lower-left of canvas
    a = math.radians(MID)
    dx, dy = math.cos(a), -math.sin(a)        # up-and-right
    hy, hx = sy + dy*LARM, sx + dx*LARM                       # hand
    ry_, rx_ = sy + dy*(LARM+LPOLE), sx + dx*(LARM+LPOLE)     # hoop rim (near)
    cy, cx = sy + dy*(LARM+LPOLE+HOOP_R), sx + dx*(LARM+LPOLE+HOOP_R)  # hoop centre
    cyi, cxi = int(round(cy)), int(round(cx))

    # mesh netting inside the hoop, with a woven grid
    fill_disk(A, cyi, cxi, HOOP_R, MESH)
    for yy in range(cyi-HOOP_R, cyi+HOOP_R+1):
        for xx in range(cxi-HOOP_R, cxi+HOOP_R+1):
            if 0 <= yy < H and 0 <= xx < W and A[yy, xx] == MESH:
                if (xx + yy) % 3 == 0 or (xx - yy) % 3 == 0:
                    A[yy, xx] = MESH_D
    # hoop rim (metal ring, ~2px)
    for ang in range(0, 360, 2):
        rr = math.radians(ang)
        for rad in (HOOP_R, HOOP_R - 1):
            yy = int(round(cyi + rad*math.sin(rr)))
            xx = int(round(cxi + rad*math.cos(rr)))
            if 0 <= yy < H and 0 <= xx < W:
                A[yy, xx] = HOOP
    # pole (hand -> rim) then arm (shoulder -> hand)
    thick_line(A, hy, hx, ry_, rx_, 1, POLE)
    thick_line(A, sy, sx, hy, hx, 2, CLAWD)
    # white outline around the whole net silhouette
    A[border_mask(A > 0, pen_disk(2))] = WHITE
    return A, (sy, sx)


# ======================================================================
# build the rigid pieces + centre them on their pivots
# ======================================================================
BODY = build_body()
NET, (SNY, SNX) = build_net()


def _center_on(A, cy, cx):
    H, W = A.shape
    py, px = max(cy, H-1-cy), max(cx, W-1-cx)
    out = np.zeros((2*py+1, 2*px+1), dtype=np.uint8)
    out[py-cy:py-cy+H, px-cx:px-cx+W] = A
    return out


CEN_NET = _center_on(NET, SNY, SNX)


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


# ======================================================================
# field: sky, grass, flowers, specimen jar
# ======================================================================
def paint_sky(g):
    for y in range(HORIZON):
        c = SKY_HI if y < HORIZON * 0.45 else SKY
        g[y, :] = c
    draw_cloud(g, 22, 20, 1.0)
    draw_cloud(g, 12, 58, 0.7)


def draw_cloud(g, cy, cx, scale):
    """A soft puffy cloud from a few overlapping lobes."""
    lobes = [(0, 0, 6), (0, -7, 4), (0, 7, 4), (-3, -3, 4), (-3, 4, 4)]
    for dy, dx, r in lobes:
        r = max(2, int(round(r * scale)))
        fill_ellipse(g, int(cy + dy*scale), int(cx + dx*scale), r - 1, r, CLOUD)


_rng = random.Random(23)
BACK_BLADES  = [(_rng.randint(4, 123), _rng.randint(5, 11), _rng.uniform(0, 6.28))
                for _ in range(26)]
FRONT_BLADES = [(_rng.randint(2, 125), _rng.randint(10, 20), _rng.uniform(0, 6.28))
                for _ in range(30)]


def paint_grass(g):
    for y in range(HORIZON, N):
        d = y - HORIZON
        if d < 3:     c = GRASS_L
        elif d < 34:  c = GRASS_M
        else:         c = GRASS_D
        g[y, :] = c
    # a scatter of lighter speckle so the meadow isn't flat
    for x in range(0, N, 1):
        if (x * 7) % 13 == 0:
            yy = HORIZON + 5 + (x * 3) % 30
            if yy < N:
                g[yy, x] = GRASS_L


def draw_blade(g, bx, base_y, height, phase, f, color):
    sway = GSWAY * math.sin(2*math.pi * f / F + phase)
    for t in range(height):
        frac = t / height
        y = base_y - t
        x = int(round(bx + sway * frac * frac))
        if 0 <= y < N and 0 <= x < N:
            g[y, x] = color


def paint_back_grass(g, f):
    for bx, h, ph in BACK_BLADES:
        draw_blade(g, bx, HORIZON + 2, h, ph, f, GRASS_D)


def paint_front_grass(g, f):
    for bx, h, ph in FRONT_BLADES:
        draw_blade(g, bx, N - 1, h, ph, f, GRASS_D)
        draw_blade(g, bx + 1, N - 2, h - 2, ph, f, GRASS_M)
        draw_blade(g, bx - 1, N - 1, h - 4, ph, f, GRASS_L)   # sunlit tip


FLOWERS = [(20, 92, FLOWER_P, 0.6), (108, 96, FLOWER_Y, 2.4), (70, 112, FLOWER_P, 4.1)]

def paint_flowers(g, f):
    for fx, fy, petal, ph in FLOWERS:
        sway = GSWAY * math.sin(2*math.pi * f / F + ph)
        # stem
        for t in range(fy - HORIZON - 2):
            y = fy - t
            x = int(round(fx + sway * (t / max(fy - HORIZON, 1))**2))
            if 0 <= y < N and 0 <= x < N:
                g[y, x] = GRASS_D
        # blossom
        hy = int(round(fy - (fy - HORIZON - 2)))
        hx = int(round(fx + sway))
        for dy, dx in ((-2, 0), (2, 0), (0, -2), (0, 2)):
            y, x = hy + dy, hx + dx
            if 0 <= y < N and 0 <= x < N:
                g[y, x] = petal
        if 0 <= hy < N and 0 <= hx < N:
            g[hy, hx] = FLOWER_Y


# ======================================================================
# butterfly
# ======================================================================
def draw_butterfly(g, cy, cx, spread):
    wr = 3 + int(round(4 * spread))
    for sign in (-1, 1):
        # upper wing (bigger)
        ucy, ucx = cy - 3, cx + sign * (2 + wr // 2)
        fill_ellipse(g, ucy, ucx, 5, wr // 2 + 2, DARK)
        fill_ellipse(g, ucy, ucx, 4, wr // 2 + 1, BFLY)
        yy, xx = ucy - 1, ucx + sign
        if 0 <= yy < N and 0 <= xx < N:
            g[yy, xx] = BFLY2
        # lower wing (smaller)
        lcy, lcx = cy + 3, cx + sign * (2 + wr // 3)
        fill_ellipse(g, lcy, lcx, 3, wr // 3 + 2, DARK)
        fill_ellipse(g, lcy, lcx, 2, wr // 3 + 1, BFLY)
    # body
    for dy in range(-4, 5):
        y = cy + dy
        if 0 <= y < N and 0 <= cx < N:
            g[y, cx] = DARK
    # antennae
    for k, (dy, dx) in enumerate(((-5, -1), (-6, -2), (-5, 1), (-6, 2))):
        y, x = cy + dy, cx + dx
        if 0 <= y < N and 0 <= x < N:
            g[y, x] = DARK


def butterfly_pos(f):
    ph = 2*math.pi * f / F
    bx = BFX + BFAX * math.sin(ph)
    by = BFY + BFAY * math.sin(2*ph)          # gentle figure-8
    return int(round(by)), int(round(bx))


# ======================================================================
# compose one frame
# ======================================================================
def compose(f):
    g = np.zeros((N, N), dtype=np.uint8)
    ph = 2*math.pi * f / F
    bob = int(round(1.5 * abs(math.sin(ph))))

    paint_sky(g)
    paint_grass(g)
    paint_back_grass(g, f)
    paint_flowers(g, f)

    # Clawd (rigid) with a tiny bob
    blit(g, BODY, BODY_Y0 - bob, BODY_X0)

    # net swinging about the shoulder (in front of the body)
    swing = AMP * math.sin(ph)
    R = rot(CEN_NET, swing)
    wy = BODY_Y0 - bob + SHO_LOC[0]
    wx = BODY_X0 + SHO_LOC[1]
    blit(g, R, wy - R.shape[0]//2, wx - R.shape[1]//2)

    # butterfly, always on top -- the elusive target
    flap = 0.45 + 0.55 * (0.5 + 0.5 * math.cos(2*math.pi * FLAPK * f / F))
    by, bx = butterfly_pos(f)
    draw_butterfly(g, by, bx, flap)

    # foreground grass over Clawd's feet for depth
    paint_front_grass(g, f)

    im = Image.frombytes("P", (CANVAS, CANVAS), g.tobytes())
    im.putpalette(pal_bytes)
    return im


frames = [compose(f) for f in range(F)]
frames[0].save(OUT / "clawd_bugcatcher_still.png")
# The field fills the whole square (no transparency), so write full opaque
# frames -- passing a transparency index here would let PIL delta-encode
# unchanged pixels as transparent, which fights disposal and flickers.
frames[0].save(OUT / "clawd_bugcatcher.gif", save_all=True, append_images=frames[1:],
               duration=DUR, loop=0, disposal=1, optimize=False)
import os
print(f"bugcatcher: {F} frames @ {DUR}ms, "
      f"gif={os.path.getsize(OUT / 'clawd_bugcatcher.gif')//1024} KB")

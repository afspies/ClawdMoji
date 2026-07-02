#!/usr/bin/env python3
"""'Hacker' Clawd -- the authentic Clawd (full silhouette, eyes and all) in a
black hoodie, hood up, hunched behind an open laptop we see from *behind*: the
screen is hidden, only its cold glow spills out and softly, diffusely washes up
over his face, breathing in a loop. The Anthropic spark sits on the back of the
lid, in Anthropic's own clay-orange (Clawd's colour), where an apple would go.
Drawn big so Clawd + laptop fill most of the 128 frame.

  body + hood : the real Clawd sprite (full 2px white outline) recoloured into a
                black hoodie. The hood is a cowl that dips to a soft point over
                the middle of his brow and casts a shadow on his face (so it
                reads as a hood, not a beret), with a couple of fabric fold
                creases for texture. His face is left orange so he still reads as
                Clawd, and his authentic little side-hands (the row 2-3 bumps of
                the default sprite) poke out orange at his sides.
  laptop      : held facing away, so we see the aluminium *back* of the lid
                (rounded, white-outlined, a lit top edge, a base slab below) with
                the Anthropic spark on it. The screen faces Clawd and is hidden.
  glow        : a cold screen-light escaping over the top edge. It is modelled as
                a *diffuse* wash -- brightest just above the lid and fading up and
                out with a wide, soft falloff, ordered-dithered so it reads as a
                gradient, not a bright disc -- and it is dim. It oscillates gently
                over the loop. Skin + fabric use dark->lit ramps, so his face
                reads as Clawd softly lit by a monitor in the dark.

Seamless by construction: the glow is 0.52 + 0.14*sin(2*pi*f/F) plus a tiny
sin(3*.) flicker, and the eye glints track it -- all equal at f=0 and f=F.

All pixel geometry is sc(v) = round(v*SCALE/7), multiples of the SCALE=7 tuning,
so bumping SCALE rescales the whole scene coherently.
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
# Skin + hood are dark->lit ramps swept per frame by the (dim, diffuse) glow.
# The logo is a fixed Clawd-orange; everything else fixed too.
SKIN_RAMP = [                      # Clawd's face: shadow (warm) -> softly monitor-lit
    (70, 50, 52), (100, 68, 60), (130, 84, 68), (158, 104, 82),
    (180, 128, 104), (182, 164, 154), (176, 194, 190), (200, 220, 214),
]
HOOD_RAMP = [                      # black fabric: only catches a faint cold rim
    (22, 24, 30), (30, 34, 44), (44, 54, 70), (64, 82, 104),
]
COLORS = [(0, 0, 0)]               # 0 transparent
def _add(rgb):
    COLORS.append(rgb); return len(COLORS) - 1
EYE      = _add((12, 14, 20))      # eye (near-black, distinct from transparent)
WHITE    = _add((244, 247, 250))   # outline
SEAM     = _add((12, 13, 17))      # hood inner-shadow rim at the opening
FOLD     = _add((16, 18, 24))      # hoodie fold crease (texture)
CLAWD    = _add((218, 119, 88))    # Clawd orange = the Anthropic logo colour
LID      = _add((56, 60, 72))      # lid back (aluminium)
LID_D    = _add((34, 37, 46))      # lid back (shaded)
LID_E    = _add((88, 96, 114))     # lid top edge / bevel highlight
BASE_L   = _add((120, 126, 138))   # base slab (light metal)
BASE_D   = _add((72, 78, 90))      # base slab (shaded)
GLINT    = _add((188, 224, 220))   # cold catchlight in the eyes
SKIN0    = len(COLORS); [ _add(c) for c in SKIN_RAMP ]   # SKIN0..SKIN0+5
HOOD0    = len(COLORS); [ _add(c) for c in HOOD_RAMP ]   # HOOD0..HOOD0+3
NSKIN, NHOOD = len(SKIN_RAMP), len(HOOD_RAMP)
pal_bytes = bytes([c for rgb in COLORS for c in rgb] + [0]*(768 - 3*len(COLORS)))

# ---- timing / motion --------------------------------------------------
F   = 16            # frames in the loop
DUR = 90            # ms/frame

# ---- body layout (big: Clawd + laptop fill most of the frame) ---------
SCALE = 9                          # 12x8 art -> 108x72 body
def sc(v):
    return int(round(v * SCALE / 7))

SXP, SYP = 12*SCALE, 8*SCALE
BOX, BOY = 10, 26                  # Clawd top-left (a little margin above the hood)
HCX = BOX + SXP//2                 # head centre column (== 64)

# eyes (ART row 1, cols 3 & 8)
EYES = [(BOY + sc(11), BOX + sc(24)), (BOY + sc(11), BOX + sc(60))]

# laptop: held facing away -- we see the back of the lid. It sits low enough to
# leave a band of hoodie torso showing between his chin and the lid.
LID_T, LID_B = 61, 105             # lid top edge .. hinge
LID_L, LID_R = HCX - 38, HCX + 38  # lid x-span
LOGO_C = (85, HCX)                 # Anthropic spark centre on the lid
LOGO_R = sc(8)
GLOW_Y = LID_T                     # screen-glow escapes over the top edge
DY, DX = sc(28), sc(58)            # diffuse glow falloff (wide -> soft, not a disc)

# ---- ordered-dither matrix (breaks the glow into a smooth gradient) ---
_BAYER = np.array([[0, 8, 2, 10], [12, 4, 14, 6],
                   [3, 11, 1, 9], [15, 7, 13, 5]]) / 16.0
DITH = np.tile(_BAYER, (N // 4 + 1, N // 4 + 1))[:N, :N]


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


def thick_line(A, y0, x0, y1, x1, r, color, only=None):
    steps = int(max(abs(y1-y0), abs(x1-x0))) + 1
    for s in range(steps+1):
        t = s/steps
        cy, cx = int(round(y0+(y1-y0)*t)), int(round(x0+(x1-x0)*t))
        for dy in range(-r, r+1):
            for dx in range(-r, r+1):
                if dy*dy + dx*dx <= r*r:
                    yy, xx = cy+dy, cx+dx
                    if 0 <= yy < N and 0 <= xx < N and (only is None or A[yy, xx] == only):
                        A[yy, xx] = color


def ellipse_mask(cy, cx, ry, rx):
    yy, xx = np.ogrid[:N, :N]
    return ((yy - cy)/ry)**2 + ((xx - cx)/rx)**2 <= 1.0


def rounded_rect(A, y0, y1, x0, x1, rad, color):
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            dy = max(y0 + rad - y, y - (y1 - rad), 0)
            dx = max(x0 + rad - x, x - (x1 - rad), 0)
            if dy*dy + dx*dx <= rad*rad:
                A[y, x] = color


# ======================================================================
# Clawd body: authentic sprite recoloured into a black hoodie (hood up)
# ======================================================================
M_SKIN, M_BROW, M_HOOD = 250, 249, 251

def build_body():
    """Returns (mat, R): a material grid and a receptivity map R[y,x] in [0,1]
    for the diffuse screen glow. Clawd keeps his true silhouette; the hood dips
    over his brow and shades his face so it reads as a hood, not a beret."""
    gy, gx = np.mgrid[0:N, 0:N]

    body = np.zeros((N, N), dtype=bool)
    for j, row in enumerate(ART):
        for i, ch in enumerate(row):
            if ch != ".":
                body[BOY+j*SCALE:BOY+(j+1)*SCALE, BOX+i*SCALE:BOX+(i+1)*SCALE] = True
    mat = np.zeros((N, N), dtype=np.uint8)
    mat[body] = M_HOOD
    hood = ellipse_mask(BOY + sc(2), HCX, sc(19), sc(31))     # raised cowl
    mat[hood] = M_HOOD

    # the face: an orange patch whose top edge dips to a point over the brow
    y_brow = BOY + sc(4) + sc(4) * np.exp(-((gx - HCX) / sc(14)) ** 2)
    face = body & (gx >= BOX + sc(15)) & (gx <= BOX + sc(69)) \
                & (gy >= y_brow) & (gy <= BOY + sc(28))
    mat[face] = M_SKIN
    mat[face & (gy < y_brow + sc(4))] = M_BROW               # cast shadow under the hood

    # hood inner-shadow rim just above the face opening
    rim = (gy >= y_brow - sc(2)) & (gy < y_brow) & (mat == M_HOOD) \
        & (gx >= BOX + sc(12)) & (gx <= BOX + sc(72))
    mat[rim] = SEAM

    # soft vertical drape folds down the hood (texture, not cap panels)
    for fx in (-sc(26), -sc(14), sc(14), sc(26)):
        thick_line(mat, BOY - sc(4), HCX + int(fx * 0.78), BOY + sc(13), HCX + fx, 0,
                   FOLD, only=M_HOOD)

    # Clawd's authentic little hands: the row 2-3 side bumps, left orange (poking
    # out of the hoodie) rather than covered -- exactly as in the default sprite
    handrows = (gy >= BOY + 2*SCALE) & (gy < BOY + 4*SCALE)
    sidebumps = (gx < BOX + 2*SCALE) | (gx >= BOX + 10*SCALE)
    mat[handrows & sidebumps & body] = CLAWD

    # eyes
    for (ey, ex) in EYES:
        fill_disk(mat, ey, ex, sc(3), EYE)

    # white outline around the whole hooded silhouette
    mat[border_mask(mat > 0, pen_disk(2))] = WHITE

    # diffuse receptivity: a wide, soft wash above the lid's top edge
    dy = np.maximum(0.0, GLOW_Y - gy)
    dx = np.abs(gx - HCX)
    R = 1.0 / (1.0 + (dy / DY) ** 2 + (dx / DX) ** 2)
    R = np.where(np.isin(mat, [M_SKIN, M_BROW, M_HOOD, SEAM]), R, 0.0)
    return mat, R


MAT, RECEPT = build_body()
SKIN_MASK = MAT == M_SKIN
BROW_MASK = MAT == M_BROW
HOOD_MASK = MAT == M_HOOD
FIXED_MASK = (MAT != 0) & ~SKIN_MASK & ~BROW_MASK & ~HOOD_MASK


# ======================================================================
# laptop, seen from the back (all static: chrome + a solid orange logo)
# ======================================================================
def build_laptop():
    A = np.zeros((N, N), dtype=np.uint8)
    # base slab peeking below the hinge (the part tipped toward us)
    rounded_rect(A, LID_B + sc(1), LID_B + sc(7), LID_L - sc(3), LID_R + sc(3), sc(3), BASE_D)
    for x in range(LID_L - sc(3), LID_R + sc(3) + 1):
        A[LID_B + sc(7), x] = BASE_L               # front lip catches light
    # lid back: rounded aluminium panel
    rounded_rect(A, LID_T, LID_B, LID_L, LID_R, sc(5), LID)
    for x in range(LID_L, LID_R + 1):              # shaded lower half
        for y in range(LOGO_C[0], LID_B + 1):
            if A[y, x] == LID:
                A[y, x] = LID_D
    for x in range(LID_L + sc(5), LID_R - sc(4)):  # lit top edge (glow wraps over)
        A[LID_T, x] = LID_E; A[LID_T + 1, x] = LID_E

    # the Anthropic spark: a solid clay-orange radial burst (does NOT pulse)
    cy, cx = LOGO_C
    for k in range(12):                            # 12 tapered rays
        ang = math.pi * k / 6
        dy, dx = -math.cos(ang), math.sin(ang)
        for t in range(LOGO_R + 1):
            w = 1 if t > LOGO_R*0.45 else 2        # thicker toward the hub
            for u in range(-w, w + 1):
                yy = int(round(cy + dy*t + (-dx)*u*0.5))
                xx = int(round(cx + dx*t + (dy)*u*0.5))
                if 0 <= yy < N and 0 <= xx < N:
                    A[yy, xx] = CLAWD
    fill_disk(A, cy, cx, sc(2), CLAWD)             # solid hub

    # white outline around the whole laptop
    A[border_mask(A > 0, pen_disk(2))] = WHITE
    return A


LAPTOP = build_laptop()


def blit_colors(g, arr):
    ys, xs = np.nonzero(arr)
    g[ys, xs] = arr[ys, xs]


# ======================================================================
# per-frame glow (dim, gentle breathe)
# ======================================================================
def glow(f):
    ph = 2*math.pi * f / F
    g = 0.52 + 0.14*math.sin(ph) + 0.02*math.sin(3*ph)
    return min(max(g, 0.0), 1.0)


def paint_body(g, gl):
    g[FIXED_MASK] = MAT[FIXED_MASK]
    cont = RECEPT * gl
    sl = np.clip((cont * (NSKIN - 1) + DITH).astype(int), 0, NSKIN - 1)
    g[SKIN_MASK] = (SKIN0 + sl)[SKIN_MASK]
    bl = np.clip((cont * (NSKIN - 1) * 0.45 + DITH - 1).astype(int), 0, NSKIN - 1)
    g[BROW_MASK] = (SKIN0 + bl)[BROW_MASK]
    hl = np.clip((cont * (NHOOD - 1) + DITH).astype(int), 0, NHOOD - 1)
    g[HOOD_MASK] = (HOOD0 + hl)[HOOD_MASK]
    if gl > 0.5:                                   # a faint cold catchlight in each eye
        for (ey, ex) in EYES:
            g[ey - sc(1), ex + sc(1)] = GLINT


def compose(f):
    g = np.zeros((N, N), dtype=np.uint8)
    gl = glow(f)
    paint_body(g, gl)                          # hooded Clawd (little hands), diffusely lit
    blit_colors(g, LAPTOP)                      # laptop back over his lower body
    im = Image.frombytes("P", (CANVAS, CANVAS), g.tobytes())
    im.putpalette(pal_bytes)
    return im


frames = [compose(f) for f in range(F)]
bright = max(range(F), key=glow)               # the iconic bright-glow pose
frames[bright].save(OUT / "clawd_hacker_still.png")
frames[0].save(OUT / "clawd_hacker.gif", save_all=True, append_images=frames[1:],
               duration=DUR, loop=0, transparency=0, disposal=2, optimize=False)
import os
print(f"hacker: {F} frames @ {DUR}ms, SCALE={SCALE}, still@f{bright}, "
      f"gif={os.path.getsize(OUT / 'clawd_hacker.gif')//1024} KB")

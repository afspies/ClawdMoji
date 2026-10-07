#!/usr/bin/env python3
"""Santa Clawd — a little present held up in one hand, lid popping open.

Bearded, Santa-hatted Clawd holds a small wrapped green box up on his left
hand, beside his head, and bobs with excitement. Once a loop the lid hops off
and tilts, and a burst of sparkles fans up and over his hat; then the lid
settles back for the next peek. The lid lift is a clipped sine of the loop
phase, so it is shut again at frame F. Snow falls behind him the whole time:
every flake travels exactly one canvas height per F frames, so it loops too.

Clawd is full width (SCALE=10, 120 px); the box sits on top of his hand cell,
inside the canvas, and the hat and sparkles use the headroom above.
"""
import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from shared.clawd import ART, CLAWD_RGB, EYE_RGB, WHITE_RGB, border_mask, pen_disk

OUT = Path(__file__).resolve().parent
NAME = "clawd_santa"

N = 128                          # canvas (fixed: Slack emoji size)
F = 28                           # frames per loop
DUR = 70                         # ms per frame
SCALE = 10                       # cell size -> 120x80 px sprite

BOB = 2                          # px Clawd bobs up and down
SPRITE_BOTTOM = N - 5            # 2 px outline below his legs, plus the 2 px bob

# ---- hat -------------------------------------------------------------------
BRIM_H = 9                       # fur band height
BRIM_OVERLAP = 3                 # how far the band sits down over his head
CONE_H = 23                      # red cone height above the brim
TIP_LEAN = -26                   # px the cone tip flops (negative = to the left)
POM_R = 7                        # pom-pom radius
POM_SWING = 5                    # px the pom swings as the tip flops

# ---- face ------------------------------------------------------------------
BEARD_TOP = 2 * SCALE + 3        # sprite y where the beard starts (below the eyes)
BEARD_BOTTOM = 4 * SCALE + 3     # where the straight part of the hem sits
BEARD_SCALLOP = 3                # depth of the hem's bumps
MOUTH_W, MOUTH_H = 10, 5         # open "ooh" mouth inside the beard
CHEEK = 5                        # rosy cheek square side

# ---- box (held up on his left hand) ----------------------------------------
HAND_L, HAND_TOP = 10 * SCALE, 2 * SCALE          # sprite x/y of his left hand cell (on our right)
BOX_W, BOX_H = 18, 18            # box body; the hand cell is 20 wide
LID_H = 5                        # lid thickness
LID_LIP = 1                      # lid overhangs the box on each side
RIBBON_W = 4                     # vertical ribbon width
BOW_R = 4                        # bow loop radius
LID_LIFT = 7                     # px the lid hops up when it pops
LID_TILT = 4                     # px the lid's right end rises more than its left
OPEN_FROM, OPEN_TO = 0.30, 0.85  # the slice of the loop the lid is open

# ---- sparkles --------------------------------------------------------------
SPARKS = 10
SPARK_RISE = 40                  # px a sparkle climbs: from the box to above the hat
SPARK_FAN_L, SPARK_FAN_R = -60, 6    # sideways spread; mostly left, over his hat
SPARK_SEED = 1224

# ---- snow ------------------------------------------------------------------
SNOW_SEED = 1225                 # seeded so the flakes land where they landed
SNOW_FLAKES = 30
SNOW_DRIFT = 4                   # px of sideways sway per flake

# ---- palette (P-mode GIF: index 0 is transparent) --------------------------
COLORS = [
    (0, 0, 0),                   # 0: transparent slot
    WHITE_RGB,                   # 1: outline
    CLAWD_RGB,                   # 2: body
    EYE_RGB,                     # 3: eyes
    (204, 30, 40),               # 4: hat red
    (150, 20, 28),               # 5: hat shadow red
    (247, 245, 238),             # 6: fur and beard
    (46, 158, 84),               # 7: box green
    (28, 110, 58),               # 8: box shadow green
    (246, 196, 64),              # 9: ribbon gold
    (255, 184, 28),              # 10: sparkle, deep gold so it reads on the white beard
    (255, 255, 255),             # 11: sparkle core (same white as outline, by design)
    (232, 128, 118),             # 12: rosy cheeks
    (120, 24, 30),               # 13: open mouth
    (150, 196, 236),             # 14: falling snow, mid blue so it reads on light and dark Slack
]
(T, OUTLINE, BODY, EYE, RED, RED_D, FUR, GREEN, GREEN_D, GOLD, SPARK, SPARK_C,
 CHEEK_C, MOUTH, SNOW) = range(15)
PAL = bytes([c for rgb in COLORS for c in rgb] + [0] * (768 - 3 * len(COLORS)))


def sprite():
    """Rasterize the shared ART grid -> index grid (one int per pixel)."""
    h, w = len(ART) * SCALE, len(ART[0]) * SCALE
    g = np.zeros((h, w), dtype=np.uint8)
    for r, row in enumerate(ART):
        for c, ch in enumerate(row):
            if ch == ".":
                continue
            g[r * SCALE:(r + 1) * SCALE, c * SCALE:(c + 1) * SCALE] = (
                EYE if ch == "O" else BODY
            )
    return g


SPRITE = sprite()
SH, SW = SPRITE.shape
HEAD_L, HEAD_R = 2 * SCALE, 10 * SCALE            # top row of ART spans cols 2..9


def fill_disk(g, cy, cx, r, color):
    yy, xx = np.ogrid[:N, :N]
    g[(yy - cy) ** 2 + (xx - cx) ** 2 <= r * r + 1] = color


def draw_face(g, y0, x0, flop):
    """Beard, mouth and cheeks, all inside the pixels the body already owns."""
    bl, br = x0 + HEAD_L, x0 + HEAD_R
    top, hem = y0 + BEARD_TOP, y0 + BEARD_BOTTOM
    g[top:hem, bl:br] = FUR
    bumps = 5                                         # scalloped hem, jiggling with the bob
    for x in range(bl, br):
        u = (x - bl) / (br - bl) * bumps * math.pi
        depth = int(round(BEARD_SCALLOP * abs(math.sin(u)) + 1.0 * flop))
        g[hem:hem + max(0, depth), x] = FUR
    g[top - 2:top, bl + 6:br - 6] = FUR               # moustache under the eyes
    mx = (bl + br) // 2 - MOUTH_W // 2
    g[top + 2:top + 2 + MOUTH_H, mx:mx + MOUTH_W] = MOUTH
    cy = top - 2 - CHEEK
    g[cy:cy + CHEEK, bl + 1:bl + 1 + CHEEK] = CHEEK_C
    g[cy:cy + CHEEK, br - 1 - CHEEK:br - 1] = CHEEK_C


def draw_hat(g, head_y, x0, flop):
    """Santa hat on the head whose top-left corner is (head_y, x0)."""
    brim_top = head_y - BRIM_H + BRIM_OVERLAP
    bl, br = x0 + HEAD_L - 3, x0 + HEAD_R + 3
    cone_base_y = brim_top + 1

    cone_l, cone_r = bl + 4, br - 4
    half_w0 = (cone_r - cone_l) / 2
    cx0 = (cone_l + cone_r) / 2
    for i in range(CONE_H):
        u = i / (CONE_H - 1)
        y = cone_base_y - i
        lean = (TIP_LEAN - POM_SWING * flop) * u * u
        half_w = max(3, half_w0 * (1 - u) ** 0.8)
        cx = cx0 + lean
        xl, xr = int(round(cx - half_w)), int(round(cx + half_w))
        g[y, xl:xr + 1] = RED
        shade = max(2, int(half_w * 0.45))
        g[y, max(xl, xr + 1 - shade):xr + 1] = RED_D

    tip_y = cone_base_y - (CONE_H - 1)
    tip_x = cx0 + TIP_LEAN - POM_SWING * flop
    fill_disk(g, tip_y - 2, int(round(tip_x)), POM_R, FUR)
    g[brim_top:brim_top + BRIM_H, bl:br + 1] = FUR


def lid_open(t):
    """0 (shut) .. 1 (fully up) as a smooth bump over the open slice of the loop."""
    if not (OPEN_FROM < t < OPEN_TO):
        return 0.0
    u = (t - OPEN_FROM) / (OPEN_TO - OPEN_FROM)
    return math.sin(math.pi * u) ** 0.7                # quick up, hang, quick down


def box_anchor(y0, x0):
    """Canvas (top, left, center-x) of the box body sitting on his left hand."""
    left = x0 + HAND_L + (SCALE * 2 - BOX_W) // 2
    return y0 + HAND_TOP - BOX_H, left, left + BOX_W // 2


def draw_box(g, y0, x0, opn):
    top, bl, cx = box_anchor(y0, x0)
    br = bl + BOX_W
    g[top:top + BOX_H, bl:br] = GREEN
    g[top:top + BOX_H, br - 4:br] = GREEN_D           # shadow down the right
    g[top:top + BOX_H, cx - RIBBON_W // 2:cx + RIBBON_W // 2] = GOLD
    if opn > 0:
        g[top:top + 2, bl + 1:br - 1] = GREEN_D       # the dark inside, once it's open

    lift = int(round(LID_LIFT * opn))
    tilt = LID_TILT * opn
    ll, lr = bl - LID_LIP, br + LID_LIP
    for x in range(ll, lr):
        u = (x - ll) / (lr - ll)
        y = top - LID_H - lift - int(round(tilt * u))
        g[y:y + LID_H, x] = GREEN
        g[y + LID_H - 1:y + LID_H, x] = GREEN_D
        if cx - RIBBON_W // 2 <= x < cx + RIBBON_W // 2:
            g[y:y + LID_H, x] = GOLD
    by = top - LID_H - lift - int(round(tilt * 0.5)) - 2
    fill_disk(g, by, cx - BOW_R, BOW_R, GOLD)
    fill_disk(g, by, cx + BOW_R, BOW_R, GOLD)
    g[by - 1:by + 2, cx - 1:cx + 2] = GREEN_D         # the knot


def spark_field():
    rng = np.random.default_rng(SPARK_SEED)
    xs = rng.uniform(SPARK_FAN_L, SPARK_FAN_R, SPARKS)    # offset from the box center
    delay = rng.uniform(0, 0.35, SPARKS)              # stagger within the open slice
    big = rng.random(SPARKS) < 0.5
    return list(zip(xs, delay, big))


SPARKLES = spark_field()


def draw_sparks(g, y0, x0, t):
    if not (OPEN_FROM < t < OPEN_TO):
        return
    u = (t - OPEN_FROM) / (OPEN_TO - OPEN_FROM)
    top, _, cx = box_anchor(y0, x0)
    start_y = top - LID_H
    for (dx, delay, big) in SPARKLES:
        life = (u - delay) / (1 - delay)
        if life <= 0 or life >= 1:
            continue
        y = int(round(start_y - SPARK_RISE * (1 - (1 - life) ** 2)))  # fast out, then slows
        x = int(round(cx + dx * (0.2 + 0.8 * life)))   # fan out as they rise
        arm = (5 if big else 4) if life < 0.75 else 2  # shrink as they fade
        for d in range(-arm, arm + 1):
            w = 1 if abs(d) <= arm // 2 else 0          # 3 px thick near the center
            for k in range(-w, w + 1):
                for (yy, xx) in ((y + d, x + k), (y + k, x + d)):
                    if 0 <= yy < N and 0 <= xx < N - 1:
                        g[yy, xx] = SPARK
        g[max(0, y - 1):y + 2, max(0, x - 1):x + 2] = SPARK_C


def snow_field():
    rng = np.random.default_rng(SNOW_SEED)
    xs = rng.integers(2, N - 3, SNOW_FLAKES)
    ys = rng.integers(0, N, SNOW_FLAKES)
    ph = rng.uniform(0, 2 * math.pi, SNOW_FLAKES)
    big = rng.random(SNOW_FLAKES) < 0.4
    return list(zip(xs, ys, ph, big))


FLAKES = snow_field()


def draw_snow(g, f):
    t = f / F
    for (x0, y0, ph, big) in FLAKES:
        y = int(round((y0 + t * N) % N))              # one canvas height per loop
        x = int(round(x0 + SNOW_DRIFT * math.sin(2 * math.pi * t + ph)))
        s = 5 if big else 3
        ys, xs = slice(max(0, y), min(N, y + s)), slice(max(0, x), min(N, x + s))
        region = g[ys, xs]
        region[region == T] = SNOW                    # behind everything already drawn


def compose(f):
    g = np.zeros((N, N), dtype=np.uint8)
    t = f / F
    ph = 2 * math.pi * t
    bob = round(BOB * math.sin(2 * ph))               # double-time: he's excited
    flop = math.sin(2 * ph - math.pi / 2)
    opn = lid_open(t)

    y0 = SPRITE_BOTTOM - SH + bob
    x0 = (N - SW) // 2
    region = g[y0:y0 + SH, x0:x0 + SW]
    region[SPRITE != 0] = SPRITE[SPRITE != 0]
    draw_face(g, y0, x0, flop)
    draw_hat(g, y0, x0, flop)
    draw_box(g, y0, x0, opn)                          # in front of the brim's corner

    # Clawd's trademark 2 px white outline, wrapped around hat, box and all
    solid = g != 0
    g[border_mask(solid, pen_disk(2))] = OUTLINE

    draw_snow(g, f)
    draw_sparks(g, y0, x0, t)                         # in front of everything
    return g


def save():
    frames = []
    for f in range(F):
        im = Image.frombytes("P", (N, N), compose(f).tobytes())
        im.putpalette(PAL)
        frames.append(im)

    frames[0].convert("RGBA").save(OUT / f"{NAME}_still.png")
    gif = OUT / f"{NAME}.gif"
    frames[0].save(
        gif, save_all=True, append_images=frames[1:], duration=DUR, loop=0,
        transparency=T, disposal=2, optimize=False,
    )
    kb = gif.stat().st_size / 1024
    assert kb <= 128, f"{gif.name} is {kb:.0f} KB — over Slack's 128 KB cap"
    print(f"{NAME}: {F} frames @ {DUR}ms, gif={kb:.0f} KB")


if __name__ == "__main__":
    save()

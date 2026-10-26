#!/usr/bin/env python3
"""Birthday Clawd, variant A -- blow out the candles.

Clawd peeks over a big two-tier birthday cake (frosting drips, sprinkles) with
four lit candles in front of his chest. Once a loop he sucks in a breath
(cheeks puff, eyes squeeze shut), leans in and blows: light-blue air streaks
fan out from his mouth, the flames bend away from him, shrink and go out one
by one, each leaving a grey smoke wisp curling up from a glowing wick. Then the
candles pop back alight (trick candles) and the flames flicker until the loop
restarts.

Everything is a pure function of t = f/F, and every periodic bit (flicker,
bob) uses a whole number of cycles per loop, so frame F equals frame 0. The
whole composition is drawn on the full 128 grid (CELL=1): Clawd (SCALE=10,
full width) is behind the cake, which hides his legs.
"""
import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from shared.clawd import ART, CLAWD_RGB, EYE_RGB, WHITE_RGB, border_mask, pen_disk, happy_eye

OUT = Path(__file__).resolve().parent
NAME = "clawd_birthday"

N = 128                          # canvas (fixed: Slack emoji size)
F = 40                           # frames per loop
DUR = 70                         # ms per frame
SCALE = 10                       # cell size -> 120x80 px sprite (full width)

# ---- layout (canvas px) ----------------------------------------------------
SPRITE_TOP = 5                   # sprite y when standing upright
CAKE_BOTTOM = 125                # last row of the cake (2 px outline fits below)
TIER2_TOP, TIER1_TOP = 66, 92    # top of the upper / lower tier
TIER1_L, TIER1_R = 5, 123        # lower tier x span (exclusive right)
TIER2_L, TIER2_R = 20, 108       # upper tier x span
FROST = 7                        # frosting band thickness on each tier

# ---- candles ---------------------------------------------------------------
CANDLE_X = (28, 52, 76, 100)     # centre x of each candle (mouth sits at x=64)
CANDLE_W, CANDLE_H = 8, 15       # candle body
FLAME_H, FLAME_W = 15, 11        # chunky teardrop
FLICKER = 0.07                   # fractional height wobble while lit
GUTTER_LEAN = 9                  # px a flame bends away from Clawd before it dies
GUTTER_SHRINK = 0.6              # fraction of height lost before it dies
LIGHT_SPEED = 0.05               # loop fraction a candle takes to relight

# ---- timeline (fractions of the loop) -------------------------------------
INHALE_FROM = 0.20               # cheeks start to puff
BLOW_FROM = 0.34                 # mouth opens, air starts
BLOW_TO = 0.58                   # air stops
OUT_AT = (0.50, 0.42, 0.42, 0.50)  # inner candles, nearest the mouth, die first; outer hang on
RELIGHT_AT = (0.86, 0.88, 0.90, 0.92)  # trick candles pop back
LEAN_DOWN = 3                    # px Clawd leans in while blowing
LEAN_UP = -2                     # px he rears back while inhaling
BOB = 1                          # idle bob amplitude, 2 cycles per loop

# ---- smoke / air -----------------------------------------------------------
SMOKE_LIFE = 0.30                # loop fraction a wisp lives
SMOKE_RISE = 24                  # px a wisp climbs
SMOKE_SWAY = 4                   # px sideways wiggle
AIR_LEN = 8                      # air streak length
AIR_REACH = 36                   # how far streaks travel from the mouth

# ---- palette (P-mode GIF: index 0 is transparent) --------------------------
COLORS = [
    (0, 0, 0),                   # 0: transparent slot
    WHITE_RGB,                   # 1: outline
    CLAWD_RGB,                   # 2: body
    EYE_RGB,                     # 3: eyes
    (255, 150, 28),              # 4: flame outer
    (255, 236, 96),              # 5: flame core
    (255, 128, 172),             # 6: pink frosting
    (214, 84, 132),              # 7: pink frosting shade
    (252, 214, 120),             # 8: vanilla sponge
    (122, 74, 56),               # 9: chocolate sponge
    (82, 48, 38),                # 10: chocolate shade
    (255, 240, 208),             # 11: cream frosting
    (232, 206, 160),             # 12: cream shade
    (70, 160, 240),              # 13: candle blue
    (60, 200, 150),              # 14: candle mint
    (160, 110, 230),             # 15: candle purple
    (150, 150, 160),             # 16: smoke
    (60, 40, 40),                # 17: wick
    (255, 70, 50),               # 18: ember
    (176, 218, 255),             # 19: air streak
    (240, 150, 150),             # 20: puffed cheek
    (110, 30, 40),               # 21: open mouth
    (255, 214, 64),              # 22: sprinkle yellow
    (60, 190, 120),              # 23: sprinkle green
    (80, 140, 255),              # 24: sprinkle blue
    (230, 60, 90),               # 25: sprinkle red
    (255, 255, 255),             # 26: candle stripe (same white as outline)
    (236, 184, 88),              # 27: vanilla sponge shade
]
(T, OUTLINE, BODY, EYE, FL_O, FL_I, PINK, PINK_D, SPONGE, CHOC, CHOC_D, CREAM,
 CREAM_D, C_BLUE, C_MINT, C_PURP, SMOKE, WICK, EMBER, AIR, CHEEK, MOUTH,
 SP_Y, SP_G, SP_B, SP_R, STRIPE, SPONGE_D) = range(28)
PAL = bytes([c for rgb in COLORS for c in rgb] + [0] * (768 - 3 * len(COLORS)))
CANDLE_COL = (C_BLUE, C_MINT, C_PURP, C_BLUE)


def sprite(closed):
    """Rasterise the shared ART grid; `closed` swaps the eyes for '^' arcs."""
    h, w = len(ART) * SCALE, len(ART[0]) * SCALE
    g = np.zeros((h, w), dtype=np.uint8)
    for r, row in enumerate(ART):
        for c, ch in enumerate(row):
            if ch == ".":
                continue
            g[r * SCALE:(r + 1) * SCALE, c * SCALE:(c + 1) * SCALE] = (
                BODY if (ch == "O" and closed) or ch == "#" else EYE
            )
    if closed:
        for c in (3, 8):
            happy_eye(g, SCALE, c * SCALE, SCALE, EYE)
    return g


SPRITES = {False: sprite(False), True: sprite(True)}
SH, SW = SPRITES[False].shape
X0 = (N - SW) // 2
MOUTH_X = N // 2                  # canvas centre column (between his two eyes)
MOUTH_Y = 29                      # sprite-relative y of the mouth centre
CHEEK_XY = ((29, 26), (29, SW - 26))   # sprite-relative (y, x) cheek centres, under the eyes


def disk(g, cy, cx, r, color):
    y0, y1 = max(0, cy - r - 1), min(N, cy + r + 2)
    x0, x1 = max(0, cx - r - 1), min(N, cx + r + 2)
    yy, xx = np.ogrid[y0:y1, x0:x1]
    m = (yy - cy) ** 2 + (xx - cx) ** 2 <= r * r + 1
    g[y0:y1, x0:x1][m] = color


def rect(g, y0, y1, x0, x1, color):
    g[max(0, y0):max(0, y1), max(0, x0):max(0, x1)] = color


def clamp01(x):
    return min(1.0, max(0.0, x))


def smooth(x):
    x = clamp01(x)
    return x * x * (3 - 2 * x)


# ---- cake ------------------------------------------------------------------
# (x offset from tier left, drip width, drip length) -- hand placed, so no RNG
DRIPS_UP = ((4, 8, 11), (22, 7, 6), (36, 9, 13), (56, 7, 7), (72, 8, 10))
DRIPS_LO = ((6, 9, 10), (26, 8, 15), (47, 9, 7), (66, 8, 12), (88, 9, 9), (104, 8, 6))
SPRINKLES = (  # (y, x, horizontal?, colour) on the upper tier sponge/frosting and lower
    (TIER2_TOP + 2, 34, True, SP_Y), (TIER2_TOP + 3, 62, False, SP_B),
    (TIER2_TOP + 1, 88, True, SP_G), (TIER2_TOP + 17, 30, False, SP_R),
    (TIER2_TOP + 18, 56, True, SP_G), (TIER2_TOP + 17, 82, False, SP_Y),
    (TIER1_TOP + 3, 16, False, SP_R), (TIER1_TOP + 2, 44, True, SP_B),
    (TIER1_TOP + 3, 74, False, SP_G), (TIER1_TOP + 2, 104, True, SP_Y),
    (TIER1_TOP + 20, 20, True, SP_Y), (TIER1_TOP + 22, 46, False, SP_B),
    (TIER1_TOP + 20, 78, True, SP_R), (TIER1_TOP + 23, 100, False, SP_G),
)


def draw_tier(g, top, bottom, xl, xr, sponge, shade, frost, frost_shade, drips):
    rect(g, top, bottom, xl, xr, sponge)
    rect(g, top, bottom, xr - 6, xr, shade)               # shadow down the right
    rect(g, top, top + FROST, xl, xr, frost)
    rect(g, top + FROST - 2, top + FROST, xl, xr, frost_shade)
    for dx, w, ln in drips:
        x = xl + dx
        rect(g, top + FROST, top + FROST + ln - w // 2, x, x + w, frost)
        disk(g, top + FROST + ln - w // 2, x + w // 2, w // 2, frost)
    rect(g, top, top + 2, xl, xr, frost)                  # lit top edge (re-cover shade)


def draw_cake(g):
    draw_tier(g, TIER1_TOP, CAKE_BOTTOM, TIER1_L, TIER1_R, CHOC, CHOC_D, CREAM, CREAM_D, DRIPS_LO)
    draw_tier(g, TIER2_TOP, TIER1_TOP, TIER2_L, TIER2_R, SPONGE, SPONGE_D, PINK, PINK_D, DRIPS_UP)
    for y, x, horiz, c in SPRINKLES:
        if horiz:
            rect(g, y, y + 2, x, x + 5, c)
        else:
            rect(g, y, y + 5, x, x + 2, c)


# ---- candles and flames ----------------------------------------------------
CANDLE_TOP = TIER2_TOP - CANDLE_H


def draw_candle(g, i):
    cx = CANDLE_X[i]
    x0 = cx - CANDLE_W // 2
    rect(g, CANDLE_TOP, TIER2_TOP + 1, x0, x0 + CANDLE_W, CANDLE_COL[i])
    for k in range(3, CANDLE_H, 5):                      # two white stripes
        rect(g, CANDLE_TOP + k, CANDLE_TOP + k + 2, x0, x0 + CANDLE_W, STRIPE)
    rect(g, CANDLE_TOP - 3, CANDLE_TOP, cx - 1, cx + 1, WICK)


def draw_flame(g, cx, h, w, lean, color):
    """Teardrop of height h, widest near the base, tip pushed sideways by `lean`."""
    h = int(round(h))
    if h < 2:
        return
    base = CANDLE_TOP - 2
    for dy in range(h + 1):
        u = dy / h
        if u < 0.3:
            p = math.sqrt(max(0.0, 1 - ((0.3 - u) / 0.45) ** 2))
        else:
            p = math.sqrt(max(0.0, 1 - ((u - 0.3) / 0.7) ** 2)) ** 1.2
        half = w / 2 * p
        mid = cx + lean * u ** 1.6
        g[base - dy, int(round(mid - half)):int(round(mid + half)) + 1] = color


def flame_state(i, t):
    """(height scale, lean px) of candle i at loop phase t; scale 0 = out."""
    side = -1 if CANDLE_X[i] < MOUTH_X else 1
    out, rel = OUT_AT[i], RELIGHT_AT[i]
    if t < rel and t >= BLOW_FROM:
        if t >= out:
            return 0.0, 0.0
        b = smooth((t - BLOW_FROM) / (out - BLOW_FROM))
        return 1 - GUTTER_SHRINK * b, side * GUTTER_LEAN * b
    if t >= rel:
        u = clamp01((t - rel) / LIGHT_SPEED)
        return math.sin(u * math.pi / 2) * (1 + 0.25 * math.sin(u * math.pi)), 0.0
    return 1.0, 0.0


def lit_wobble(i, t):
    ph = 2 * math.pi * t
    return (1 + FLICKER * math.sin(2 * ph + 1.7 * i),
            round(1.2 * math.sin(3 * ph + 2.3 * i)))


# ---- effects ---------------------------------------------------------------
def draw_air(g, t, mouth_y):
    if not (BLOW_FROM + 0.02 < t < BLOW_TO):
        return
    life = (t - BLOW_FROM) / (BLOW_TO - BLOW_FROM)
    for side in (-1, 1):
        for k in range(3):
            s = (k / 3 + life * 1.6) % 1                 # each streak travels mouth -> candle
            r = 8 + s * AIR_REACH
            ang = math.radians(28 + 14 * (k - 1))
            dx, dy = side * math.cos(ang), math.sin(ang)
            for j in range(AIR_LEN):
                if s > 0.9 and j > AIR_LEN // 2:
                    break
                cx = int(round(MOUTH_X + dx * (r + j)))
                cy = int(round(mouth_y + dy * (r + j)))
                disk(g, cy, cx, 1 + (j % 4 < 3), AIR)


def draw_smoke(g, i, t):
    a = (t - OUT_AT[i]) / SMOKE_LIFE
    if not (0 <= a < 1) or t >= RELIGHT_AT[i]:
        return
    cx = CANDLE_X[i]
    base = CANDLE_TOP - 3
    side = -1 if cx < MOUTH_X else 1
    steps = 14
    for s in range(steps + 1):
        p = a * s / steps                                # 0 (wick) .. a (head)
        y = base - SMOKE_RISE * (1 - (1 - p) ** 2)
        x = cx + side * 5 * p + SMOKE_SWAY * math.sin(2 * math.pi * (1.6 * p + 0.2 * i)) * p
        thick = 1 + 2 * (s / steps) * (1 - a ** 2) * 1.0  # thin at the tail, fat at the head
        disk(g, int(round(y)), int(round(x)), int(round(thick)) if thick >= 1.5 else 1, SMOKE)
    if a < 0.35:                                         # the wick glows while it smokes
        rect(g, CANDLE_TOP - 3, CANDLE_TOP, cx - 1, cx + 1, EMBER)


def clawd_state(t):
    """(lean px, puff 0..1, blowing, eyes closed)."""
    inh = smooth((t - INHALE_FROM) / (BLOW_FROM - INHALE_FROM))
    deflate = 1 - smooth((t - BLOW_TO + 0.04) / 0.12)
    puff = inh * deflate if t < BLOW_FROM + 0.001 else min(1.0, deflate) if t < BLOW_TO + 0.08 else 0.0
    if t < BLOW_FROM:
        lean = LEAN_UP * inh
    elif t < BLOW_TO:
        lean = LEAN_UP + (LEAN_DOWN - LEAN_UP) * smooth((t - BLOW_FROM) / 0.05)
    else:
        lean = LEAN_DOWN * (1 - smooth((t - BLOW_TO) / 0.1))
    blowing = BLOW_FROM <= t < BLOW_TO
    closed = INHALE_FROM + 0.03 <= t < BLOW_TO + 0.03
    return lean, puff, blowing, closed


def compose(f):
    g = np.zeros((N, N), dtype=np.uint8)
    t = f / F
    lean, puff, blowing, closed = clawd_state(t)
    bob = BOB * math.sin(4 * math.pi * t) * (1 - abs(lean) / 3)
    y0 = SPRITE_TOP + int(round(lean + bob))

    spr = SPRITES[closed]
    reg = g[y0:y0 + SH, X0:X0 + SW]
    reg[spr != 0] = spr[spr != 0]
    cheek_r = int(round(5 + 3 * puff))
    if puff > 0.05:
        for cy, cx in CHEEK_XY:
            disk(g, y0 + cy, X0 + cx, cheek_r, CHEEK)
    if blowing:
        mr = 5 if f % 2 == 0 else 4                 # lips flutter
        disk(g, y0 + MOUTH_Y, MOUTH_X, mr, MOUTH)
    elif puff > 0.05:
        disk(g, y0 + MOUTH_Y, MOUTH_X, 2, MOUTH)         # pursed

    draw_cake(g)
    for i in range(len(CANDLE_X)):
        draw_candle(g, i)
        sc, ln = flame_state(i, t)
        if sc > 0:
            if BLOW_FROM > t or t >= RELIGHT_AT[i] + LIGHT_SPEED:
                wob, jit = lit_wobble(i, t)
                sc, ln = sc * wob, ln + jit
            draw_flame(g, CANDLE_X[i], FLAME_H * sc, FLAME_W * min(1.0, 0.5 + sc * 0.5), ln, FL_O)
            draw_flame(g, CANDLE_X[i] + 0.0, FLAME_H * sc * 0.55, FLAME_W * 0.5 * min(1.0, 0.5 + sc * 0.5), ln * 0.55, FL_I)

    # Clawd's trademark 2 px white outline, wrapped around cake and candles too
    solid = g != 0
    g[border_mask(solid, pen_disk(2))] = OUTLINE

    draw_air(g, t, y0 + MOUTH_Y)
    for i in range(len(CANDLE_X)):
        draw_smoke(g, i, t)
    return g


def save():
    frames = []
    for f in range(F):
        g = compose(f)
        im = Image.frombytes("P", (N, N), g.tobytes())
        im.putpalette(PAL)
        frames.append(im)

    frames[0].convert("RGBA").save(OUT / f"{NAME}_still.png")
    gif = OUT / f"{NAME}.gif"
    frames[0].save(
        gif, save_all=True, append_images=frames[1:], duration=DUR, loop=0,
        transparency=T, disposal=2, optimize=False,
    )
    kb = gif.stat().st_size / 1024
    assert all(im.size == (N, N) for im in frames)
    assert kb <= 128, f"{gif.name} is {kb:.0f} KB — over Slack's 128 KB cap"
    pts = [np.nonzero(compose(f)) for f in range(F)]
    ys = np.concatenate([p[0] for p in pts]); xs = np.concatenate([p[1] for p in pts])
    print(f"margins  t {ys.min()}  b {N - 1 - ys.max()}  l {xs.min()}  r {N - 1 - xs.max()}")
    print(f"{NAME}: {F} frames @ {DUR}ms, gif={kb:.0f} KB")


if __name__ == "__main__":
    save()

#!/usr/bin/env python3
"""Uncle Clawd, maximalist cut -- "I WANT YOU" in front of a waving Old Glory.

Everything the plain Uncle Clawd does (striped star-band top hat, goatee, white
glove that jabs a pointing finger once a loop while the hat hops late) plus
three more layers of patriotism:

  brows   : the bushy white brows act, on a script keyed to the jab. Beat 1,
            a wind-up: the left brow cocks up, sceptical. Beat 2, both drop
            into a V scowl as the finger fires and hold it through the jab.
            Beat 3, they ease back to rest. All whole-pixel moves, 2-3 px of
            travel, and they never rise above the hat brim.
  costume : recoloured from pixels the body already owns, the silhouette is
            untouched. Face rows stay orange; below the chin he wears a deep
            navy tailcoat with lighter lapels, a white shirt front, a red bow
            tie under a shortened goatee and gold buttons, and his legs are
            red-and-white pinstripe trousers.
  flag    : a full opaque backdrop, a US flag muted down to dim red / dusty
            grey-white / slate blue so it sits behind him. A coarse travelling
            sine ripple (whole-pixel vertical shear, one wavelength across the
            canvas, one full cycle per loop) with fold shading. The canton is
            in the top-left corner, clear of the hat.

Legibility: hat, coat and flag are all red/white/blue, so he is separated from
the flag three ways: the flag is much darker and less saturated than anything
on him, he keeps his 2 px white outline plus a 1 px near-black keyline outside
it (a white-on-grey-white edge would otherwise vanish), and the coat navy is
darker than the canton and the hat band. He is drawn at SCALE=9 (108 px wide)
because the flag needs to be seen; it earns the space.

Everything is a function of f mod F: the jab, hat and brows are keyed to the
loop phase and the ripple is sin(2 pi (x/WAVE_LEN - f/F)), so frame 0 and
frame F are identical.
"""
import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from shared.clawd import ART, CLAWD_RGB, EYE_RGB, WHITE_RGB, border_mask, pen_disk

OUT = Path(__file__).resolve().parent
NAME = "clawd_unclesam"

N = 128                          # canvas (fixed: Slack emoji size)
F = 24                           # frames per loop
DUR = 55                         # ms per frame -> a 1.3 s loop
SCALE = 9                        # cell size -> 108x72 px sprite; the flag earns the margin

SPRITE_BOTTOM = N - 4            # 3 px outline + keyline below his legs, 1 px to spare
HOP = 2                          # px he hops up into the jab

# ---- the jab (fractions of the loop) ---------------------------------------
JAB_FROM, JAB_TO = 0.26, 0.70    # the slice of the loop the finger is out
JAB_SNAP = 0.45                  # < 1 squares the pulse off: fast out, hang, fast back
HAT_LAG = 0.11                   # fraction of a loop the hat trails the finger by

# ---- hat -------------------------------------------------------------------
BRIM_H = 5                       # navy brim thickness
BRIM_OVERLAP = 0                 # brim sits right on his head: the brows own the forehead
BRIM_OVER = 6                    # px the brim sticks out past the crown each side
BAND_H = 12                      # blue star band
STRIPE_H = 20                    # red/white striped crown above the band
CAP_H = 2                        # dark rim closing the crown
STRIPES = 7                      # odd, so both outer stripes are red
FLARE = 4                        # px the crown widens each side toward the top
STARS = 4                        # stars along the band
STAR_ARM = 4                     # half-size of a star: a chunky plus-diamond
HAT_FLY = 5                      # px the hat lifts off his head after a jab
HAT_TILT = 5                     # px the crown's top leans back as it flies

# ---- face ------------------------------------------------------------------
BROW_THICK = 5                   # bushy white brows
BROW_Y = 3                       # brow's outer-end top, below the brim, at rest
BROW_REACH = 3                   # px a brow overhangs its eye cell each side
MOUTH_Y = 2 * SCALE + 3          # sprite y of the thin, unimpressed mouth
MOUTH_W = 16
GOATEE_TOP = MOUTH_Y + 4         # sprite y where the goatee starts
GOATEE_TIP = 4 * SCALE + 1       # it ends in a point just above the bow tie
GOATEE_W = 22                    # width at the top

# Brow script. Each key is (loop phase, (lift_L, drop_L, lift_R, drop_R)):
# `lift` raises the whole brow (px), `drop` tilts its inner end down toward the
# nose (px) -- the bigger the drop, the harder the scowl. Poses are blended
# linearly between keys and rounded, so every move is a whole-pixel move.
BROW_KEYS = [
    (0.00, (0, 3, 0, 3)),        # rest: a mild frown
    (0.12, (0, 3, 0, 3)),
    (0.20, (2, 1, 0, 3)),        # wind-up: left brow cocks up, sceptical
    (0.25, (2, 1, 0, 3)),        # hold it...
    (0.29, (0, 5, 0, 5)),        # ...and both drop into a V as the finger fires
    (0.68, (0, 5, 0, 5)),        # held through the jab
    (0.78, (0, 3, 0, 3)),        # finger gone: ease back to rest
    (1.00, (0, 3, 0, 3)),        # = rest, so the loop closes
]

# ---- glove (his left hand, on our right) -----------------------------------
HAND_CX, HAND_CY = 11 * SCALE, 3 * SCALE     # sprite x/y of the hand cell's center
FIST_R = (8, 13)                 # fist half-size, at rest -> at full jab
FIST_DX = (-1, -6)               # fist center offset from the hand cell
FIST_DY = (1, 9)
FINGER_LEN = (11, 30)            # fist center to fingertip center
FINGER_BASE_R = (4, 5.5)
FINGER_TIP_R = (4, 8)            # the tip outgrows the base as it nears the camera
FINGER_DIR = (-0.70, 0.71)       # (dx, dy): down and across his body, at you
THUMB_R = 0.38                   # thumb radius, as a fraction of the fist's
GLOVE_RING = 2                   # navy line around the glove

# ---- costume (all in sprite coordinates) -----------------------------------
COAT_TOP = 3 * SCALE             # tailcoat starts under the chin; above it stays orange
COAT_END = 6 * SCALE             # ... and ends where the legs begin
TIE_Y, TIE_H, TIE_W = 4 * SCALE + 1, 8, 24   # red bow tie: top, height, width
SHIRT_W = (7, 3)                 # shirt-front half-width under the tie -> at the hem
LAPEL_W = 5                      # px: lighter coat lapels sloping down to the shirt
BUTTONS = (COAT_END - 7, COAT_END - 2)   # sprite y of the two gold buttons
PIN = (3, 2, 3)                  # trouser pinstripe: red / white / red px across a leg

# ---- flag ------------------------------------------------------------------
STRIPE_PX = 11                   # 13 stripes * 11 = 143 px, taller than the canvas
CANTON_W, CANTON_H = 27, 60      # blue field, top-left, clear of the hat
FLAG_STAR_ARM = 3                # canton star half-size (plus-diamond)
WAVE_LEN = 128                   # px per ripple: one wavelength across the canvas
WAVE_AMP = 5                     # px of vertical shear
WAVE_STEP = 4                    # ripple is sampled in 4 px columns: coarse, cheap, readable
FOLD = 0.35                      # cos(phase) above this takes the dark fold shade

# ---- palette (P-mode GIF, fully opaque) ------------------------------------
COLORS = [
    (0, 0, 0),                   # 0: unused
    WHITE_RGB,                   # 1: outline
    CLAWD_RGB,                   # 2: body
    EYE_RGB,                     # 3: eyes
    (206, 32, 44),               # 4: hat stripe red
    (132, 18, 30),               # 5: crown rim, dark red
    (250, 248, 240),             # 6: stripe / star / glove / brow white
    (40, 72, 172),               # 7: hat band blue
    (22, 34, 92),                # 8: navy: brim, glove line
    (214, 212, 216),             # 9: glove, goatee shadow
    (96, 40, 30),                # 10: mouth
    (14, 14, 30),                # 11: keyline outside the white outline
    (18, 26, 74),                # 12: tailcoat navy (darker than canton/band)
    (44, 62, 142),               # 13: lapel blue
    (228, 190, 70),              # 14: gold buttons
    (190, 24, 40),               # 15: bow tie red / trouser red
    # the flag, muted: lit / folded pairs
    (140, 40, 52), (104, 28, 40),        # 16,17 flag red
    (152, 146, 160), (118, 112, 130),    # 18,19 flag white
    (62, 74, 120), (46, 56, 96),         # 20,21 canton slate
    (206, 202, 212), (160, 156, 170),    # 22,23 canton stars
]
(T, OUTLINE, BODY, EYE, RED, RED_D, WHITE, BLUE, NAVY, SHADE, MOUTH, KEYLINE,
 COAT, LAPEL, GOLD, TIE, FRED, FRED_S, FWHT, FWHT_S, FBLU, FBLU_S, FSTAR, FSTAR_S) = range(24)
PAL = bytes([c for rgb in COLORS for c in rgb] + [0] * (768 - 3 * len(COLORS)))
SHADE_OF = {FRED: FRED_S, FWHT: FWHT_S, FBLU: FBLU_S, FSTAR: FSTAR_S}   # lit -> folded


def sprite():
    """Rasterize the shared ART grid -> index grid, then dress him.

    Only pixels that are already BODY change colour: the silhouette is untouched.
    """
    h, w = len(ART) * SCALE, len(ART[0]) * SCALE
    g = np.zeros((h, w), dtype=np.uint8)
    for r, row in enumerate(ART):
        for c, ch in enumerate(row):
            if ch == ".":
                continue
            g[r * SCALE:(r + 1) * SCALE, c * SCALE:(c + 1) * SCALE] = (
                EYE if ch == "O" else BODY
            )
    yy, xx = np.mgrid[:h, :w]
    body = g == BODY
    cx = w // 2

    # tailcoat: everything below the chin down to the legs
    coat = body & (yy >= COAT_TOP) & (yy < COAT_END)
    g[coat] = COAT
    # lapels: two slanting strips from the shoulders down to the shirt front
    for side in (-1, 1):
        for y in range(COAT_TOP, COAT_END):
            u = (y - COAT_TOP) / (COAT_END - COAT_TOP)
            far = int(round(lerp((cx - 3 * SCALE + 3, SHIRT_W[1] + 3), u)))   # outer edge, from cx
            for x in range(cx + side * (far - LAPEL_W), cx + side * far, side):
                if g[y, x] == COAT:
                    g[y, x] = LAPEL
    # white shirt front, narrowing toward the hem
    for y in range(TIE_Y + TIE_H // 2, COAT_END):
        u = (y - TIE_Y) / (COAT_END - TIE_Y)
        half = int(round(lerp(SHIRT_W, min(1.0, u))))
        g[y, cx - half:cx + half] = WHITE
    # gold buttons down the shirt
    for by in BUTTONS:
        g[by:by + 2, cx - 1:cx + 1] = GOLD
    # red bow tie: two wings and a knot
    ty = TIE_Y
    for i in range(TIE_W // 2):
        wing = int(round(TIE_H / 2 * (0.45 + 0.55 * i / (TIE_W // 2 - 1))))
        c = TIE_H // 2
        for x in (cx - 1 - i, cx + i):
            g[ty + c - wing:ty + c + wing, x] = TIE
    g[ty + 1:ty + TIE_H - 1, cx - 2:cx + 2] = RED_D                      # the knot
    # pinstripe trousers on the legs
    legs = body & (yy >= COAT_END)
    cell = (xx % SCALE)
    stripe_a = (cell < PIN[0]) | (cell >= PIN[0] + PIN[1])
    g[legs & stripe_a] = TIE
    g[legs & ~stripe_a] = WHITE
    return g


def lerp(ab, p):
    return ab[0] + (ab[1] - ab[0]) * p


SPRITE = sprite()
SH, SW = SPRITE.shape
HEAD_L, HEAD_R = 2 * SCALE, 10 * SCALE            # top row of ART spans cols 2..9
YY, XX = np.mgrid[:N, :N]


def jab(t):
    """0 (hand at rest) .. 1 (finger in your face) at loop phase t, wrapping."""
    t %= 1.0
    if not (JAB_FROM < t < JAB_TO):
        return 0.0
    u = (t - JAB_FROM) / (JAB_TO - JAB_FROM)
    return math.sin(math.pi * u) ** JAB_SNAP


def brow_pose(t):
    """(lift_L, drop_L, lift_R, drop_R) as whole pixels at loop phase t."""
    t %= 1.0
    for (t0, a), (t1, b) in zip(BROW_KEYS, BROW_KEYS[1:]):
        if t0 <= t <= t1:
            u = (t - t0) / (t1 - t0) if t1 > t0 else 1.0
            return tuple(int(round(a[i] + (b[i] - a[i]) * u)) for i in range(4))
    return BROW_KEYS[0][1]


def draw_face(g, y0, x0, pose):
    """Brows, mouth and goatee, all inside the pixels the body already owns."""
    lift_l, drop_l, lift_r, drop_r = pose
    # left brow (on our left) tilts down toward the right; right brow mirrors it
    for (ex, inward, lift, drop) in ((3 * SCALE, 1, lift_l, drop_l),
                                    (8 * SCALE, -1, lift_r, drop_r)):
        for i in range(-BROW_REACH, SCALE + BROW_REACH):
            u = (i + BROW_REACH) / (SCALE + 2 * BROW_REACH - 1)   # 0 at the cell's left .. 1 at its right
            tilt = drop * (u if inward > 0 else 1 - u)
            y = y0 + BROW_Y - lift + int(round(tilt))
            g[y:y + BROW_THICK, x0 + ex + i] = WHITE

    cx = x0 + SW // 2
    g[y0 + MOUTH_Y:y0 + MOUTH_Y + 3, cx - MOUTH_W // 2:cx + MOUTH_W // 2] = MOUTH
    rows = GOATEE_TIP - GOATEE_TOP
    for i in range(rows):
        u = i / (rows - 1)
        half = max(2, int(round(GOATEE_W / 2 * (1 - u) ** 0.7)))
        y = y0 + GOATEE_TOP + i
        g[y, cx - half:cx + half] = WHITE
        g[y, cx + half - max(2, half // 3):cx + half] = SHADE     # shadow down the right


def star(g, cy, cx):
    """Chunky plus-diamond: reads as a star at 128 px and as a white dot at 32."""
    d = np.abs(YY - cy) + np.abs(XX - cx)
    plus = ((np.abs(YY - cy) <= 1) & (np.abs(XX - cx) <= STAR_ARM)) | \
           ((np.abs(XX - cx) <= 1) & (np.abs(YY - cy) <= STAR_ARM))
    g[plus | (d <= STAR_ARM - 1)] = WHITE


def draw_hat(g, head_y, x0, fly, tilt):
    """Top hat on the head whose top-left corner is (head_y, x0).

    Drawn upright into its own layer, then sheared row by row so the crown's
    top leans `tilt` px while the brim stays put.
    """
    h = np.zeros((N, N), dtype=np.uint8)
    brim_top = head_y - BRIM_H + BRIM_OVERLAP - fly
    cl, cr = x0 + HEAD_L, x0 + HEAD_R                 # crown is as wide as his head
    band_top = brim_top - BAND_H
    crown_top = band_top - STRIPE_H
    cap_top = crown_top - CAP_H
    hat_h = brim_top - cap_top

    for y in range(cap_top, brim_top):
        u = (brim_top - y) / hat_h                    # 0 at the brim .. 1 at the top
        fl = int(round(FLARE * u))
        xl, xr = cl - fl, cr + fl
        if y >= band_top:
            h[y, xl:xr] = BLUE
        elif y >= crown_top:
            for s in range(STRIPES):
                a = xl + (xr - xl) * s // STRIPES
                b = xl + (xr - xl) * (s + 1) // STRIPES
                h[y, a:b] = RED if s % 2 == 0 else WHITE
        else:
            h[y, xl:xr] = RED_D
    for s in range(STARS):
        star(h, band_top + BAND_H // 2, cl + (cr - cl) * (2 * s + 1) // (2 * STARS))
    h[brim_top:brim_top + BRIM_H, cl - BRIM_OVER:cr + BRIM_OVER] = NAVY

    for y in range(max(0, cap_top), brim_top + BRIM_H):
        u = max(0.0, (brim_top - y) / hat_h)
        row = np.roll(h[y], int(round(tilt * u)))
        g[y][row != 0] = row[row != 0]


def draw_glove(g, y0, x0, p):
    """White pointing glove on his hand; `p` (0..1) is how far the jab is out.

    A squarish fist with the curled fingers creased down one side, a thumb on
    top, and the index finger as a cone that lengthens and fattens toward its
    tip. Everything is a distance field, so the hand scales smoothly.
    """
    fx = x0 + HAND_CX + lerp(FIST_DX, p)
    fy = y0 + HAND_CY + lerp(FIST_DY, p)
    fist_r = lerp(FIST_R, p)
    length = lerp(FINGER_LEN, p)
    dx, dy = FINGER_DIR
    r0, r1 = lerp(FINGER_BASE_R, p), lerp(FINGER_TIP_R, p)

    fist = (np.abs(XX - fx) ** 4.0 + np.abs(YY - fy) ** 4.0) ** 0.25 - fist_r   # squircle
    thumb = np.hypot(XX - (fx - fist_r * 0.35), YY - (fy - fist_r * 0.72)) - fist_r * THUMB_R
    # the finger: distance to its axis, against a radius that grows along it
    along = (XX - fx) * dx + (YY - fy) * dy
    u = np.clip(along / length, 0, 1)
    finger = np.hypot(XX - (fx + dx * length * u), YY - (fy + dy * length * u)) \
        - (r0 + (r1 - r0) * u)

    g[(fist <= GLOVE_RING) | (thumb <= GLOVE_RING) | (finger <= GLOVE_RING)] = NAVY
    g[thumb <= 0] = WHITE
    g[(fist <= 0) & (thumb > 0) & (thumb <= GLOVE_RING)] = NAVY   # thumb's line across the fist
    g[(fist <= 0) & (thumb > GLOVE_RING)] = WHITE
    # the three curled fingers: a shadowed block down the right, creased twice
    curled = (fist <= 0) & (XX - fx > fist_r * 0.1)
    g[curled] = SHADE
    crease = max(1.0, fist_r * 0.07)
    for k in (-0.3, 0.33):
        g[curled & (np.abs(YY - (fy + fist_r * k)) <= crease)] = NAVY
    # the finger crosses the fist with its own line, open only at the knuckle
    g[(finger <= GLOVE_RING) & (fist <= 0) & (along > r0)] = NAVY
    g[finger <= 0] = WHITE
    side = (XX - fx) * dy - (YY - fy) * dx            # > 0 on the finger's underside
    g[(finger <= 0) & (finger > -max(2.0, r1 * 0.35)) & (side < 0) & (along > fist_r)] = SHADE


def make_flag():
    """The static flag in flag coordinates: stripes, canton, stars (lit indices)."""
    fl = np.zeros((13 * STRIPE_PX, N), dtype=np.uint8)
    for s in range(13):
        fl[s * STRIPE_PX:(s + 1) * STRIPE_PX] = FRED if s % 2 == 0 else FWHT
    fl[:CANTON_H, :CANTON_W] = FBLU
    ys, xs = np.mgrid[:fl.shape[0], :fl.shape[1]]
    for cy in range(8, CANTON_H - 4, 15):                     # 2 columns x 4 rows
        for cx in (7, 20):
            d = np.abs(ys - cy) + np.abs(xs - cx)
            plus = ((np.abs(ys - cy) <= 1) & (np.abs(xs - cx) <= FLAG_STAR_ARM)) | \
                   ((np.abs(xs - cx) <= 1) & (np.abs(ys - cy) <= FLAG_STAR_ARM))
            fl[plus | (d <= FLAG_STAR_ARM - 1)] = FSTAR
    return fl


FLAG = make_flag()


def draw_flag(f):
    """Rippled flag for frame f: each 4 px column shears vertically by a sine.

    The phase is x/WAVE_LEN - f/F, so the wave travels right and is exactly one
    wavelength per loop; the fold shade lands where the cloth tilts toward you.
    """
    xs = (np.arange(N) // WAVE_STEP) * WAVE_STEP + WAVE_STEP // 2
    ph = 2 * math.pi * (xs / WAVE_LEN - f / F)
    disp = np.rint(WAVE_AMP * np.sin(ph)).astype(int)         # per column
    fold = np.cos(ph) > FOLD
    sy = np.clip(YY - disp[None, :] + 3, 0, FLAG.shape[0] - 1)   # +3: start inside the first stripe
    g = FLAG[sy, XX].copy()
    shaded = np.zeros_like(g, dtype=bool)
    shaded[:, :] = fold[None, :]
    for lit, dark in SHADE_OF.items():
        g[(g == lit) & shaded] = dark
    return g


def compose(f):
    g = np.zeros((N, N), dtype=np.uint8)
    t = f / F
    p = jab(t)
    hat_p = jab(t - HAT_LAG)                          # the hat finds out late

    y0 = SPRITE_BOTTOM - SH - int(round(HOP * p))
    x0 = (N - SW) // 2
    region = g[y0:y0 + SH, x0:x0 + SW]
    region[SPRITE != 0] = SPRITE[SPRITE != 0]
    draw_face(g, y0, x0, brow_pose(t))
    draw_hat(g, y0, x0, int(round(HAT_FLY * hat_p)), HAT_TILT * hat_p)
    draw_glove(g, y0, x0, p)                          # in front of everything

    # Clawd's trademark 2 px white outline wrapped around hat, glove and all,
    # then a 1 px near-black keyline so he cuts out of the flag
    solid = g != 0
    outline = border_mask(solid, pen_disk(2))
    key = border_mask(solid | outline, pen_disk(1))
    out = draw_flag(f)
    out[key] = KEYLINE
    out[outline] = OUTLINE
    out[solid] = g[solid]
    return out


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
        disposal=1, optimize=False,
    )
    kb = gif.stat().st_size / 1024
    assert kb <= 128, f"{gif.name} is {kb:.0f} KB — over Slack's 128 KB cap"
    print(f"{NAME}: {F} frames @ {DUR}ms, gif={kb:.0f} KB")


if __name__ == "__main__":
    save()

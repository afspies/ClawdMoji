#!/usr/bin/env python3
"""Melting Clawd — the 🫠 face, done as a crab.

A melt front climbs him from the feet up. Everything the front has passed is
liquid: it thins as it runs down, drops to the floor line, and spreads out into
a puddle. Everything still above it is Clawd, sinking, because there is less
and less holding him up. His eyes go soft last and slide down the front of him,
and what settles is a wide puddle with two dark smudges lying in it.

Nothing here is a redrawn Clawd: the melt is a coordinate map over the shared
ART grid plus light on what has gone liquid, so frame 0 is exactly him -- his
own orange, untouched. Only liquid lifts, and the puddle catches a glint.

NOTE: this is the first renderer here to break CONTRIBUTING's seamless-loop
constraint, deliberately. The melt runs one way only and then holds on the
puddle, because a Clawd who un-melts just looks like a Clawd bobbing his legs.
CI's actual gates still hold: >= 2 frames and loop=0.
"""
import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from shared.clawd import ART, CLAWD_RGB, EYE_RGB, WHITE_RGB, border_mask, pen_disk

OUT = Path(__file__).resolve().parent
NAME = "clawd_melting"

N = 128                 # canvas (Slack emoji size)
F = 24                  # frames of melt
DUR = 80                # ms per melt frame (GIFs store centiseconds, so this
                        # has to be a multiple of 10 or Pillow truncates it)
HOLD = 1800             # ms the finished puddle sits there before the restart
SCALE = 10              # 120x80 sprite: full canvas width. FLOOR, PILE_RX and
                        # PILE_H below are fitted to it.
TOP = 4                 # where his shell sits before anything gives way
EPS = 1e-6

FLOOR = 120             # the floor line liquid runs down to
SOFT = 0.30             # how much of him is mid-melt at once (0 = a hard line)
NECK = 0.30             # how far a stretching strand thins as it runs down.
                        # Liquid narrows on the way and the volume turns up in
                        # the puddle instead, so he doesn't swell mid-melt.
TILT = 0.18             # extra melt on his right, so he goes over lopsided
CROWN = 0.26            # his middle holds out longest, so the melt stays domed
WOBBLE = 1.4            # px of waver on the molten edge
WAVER = 0.35            # and how tight that waver is, per px down him
SINK = 56               # px his surviving upper half descends as he loses legs

PILE_RX = 60            # half-width the finished puddle spreads to
PILE_H = 20             # how tall the finished puddle stands above the floor
LIP = 2                 # px of puddle drawn below the floor line
WET = 4                 # puddle height at which its underside reads as wet
GLINT = 0.22            # fraction of the puddle's width that catches the light
GLINT_H = 3             # px the glint sits below the puddle's surface, so it
                        # reads as a highlight in the liquid and not as a second
                        # white outline hugging the dome

EYE_MELT = 0.30         # melt progress at which his eyes start to go soft
EYE_DROOP = 5           # px they slide down his face while it still holds
EYE_LAG = 2             # px the right eye trails the left, matching TILT
EYE_SINK = 3            # px an eye settles into the puddle's surface
EYE_SQUASH = 0.52       # how much a runny eye flattens
EYE_SPREAD = 0.60       # ... and how much it widens doing it

STILL = 21              # frame the gallery still is taken from

WET_MIX = 0.09          # how far the puddle's underside sits under his own
                        # colour. Shallow on purpose: anything deeper reads as
                        # a dark bar ruled under him rather than shadow.
GLOSS_MIX = 0.16        # how far the thinnest liquid lifts towards white
GLOSS_STEPS = 4         # tints between solid Clawd and fully-runny liquid.
                        # Fewer and the ramp bands; more and it's wasted palette.


def mix(rgb, other, t):
    return tuple(int(round(a + (b - a) * t)) for a, b in zip(rgb, other))


COLORS = [
    (0, 0, 0),          # 0: transparent slot
    WHITE_RGB,          # 1: outline
    CLAWD_RGB,          # 2: body
    EYE_RGB,            # 3: eyes
    mix(CLAWD_RGB, (0, 0, 0), WET_MIX),     # 4: the wet underside of the puddle
] + [mix(CLAWD_RGB, WHITE_RGB, GLOSS_MIX * (i + 1) / GLOSS_STEPS)
     for i in range(GLOSS_STEPS)]           # 5..: thinning liquid, lightest last
T, OUTLINE, BODY, EYE, SHADE = 0, 1, 2, 3, 4
LIQUID = list(range(5, 5 + GLOSS_STEPS))
SHEEN = LIQUID[-1]
CLAWD_INK = {BODY, SHADE, *LIQUID}          # every index that is made of Clawd
PAL = bytes([c for rgb in COLORS for c in rgb] + [0] * (768 - 3 * len(COLORS)))

GY, GX = len(ART), len(ART[0])
SH, SW = GY * SCALE, GX * SCALE
CX = N / 2


def sprite():
    """Rasterise the shared ART grid -> boolean body mask. Body only: his eyes
    melt on their own schedule, so they are drawn from EYE_CELLS instead."""
    g = np.zeros((SH, SW), dtype=bool)
    for r, row in enumerate(ART):
        for c, ch in enumerate(row):
            if ch != ".":
                g[r * SCALE:(r + 1) * SCALE, c * SCALE:(c + 1) * SCALE] = True
    return g


SPRITE = sprite()
EYE_CELLS = [(r, c) for r, row in enumerate(ART)
             for c, ch in enumerate(row) if ch == "O"]
FEET = [x for x in range(SW) if SPRITE[SH - 1, x]]
assert FEET, "the shared ART grid has no feet to melt from"
assert CX + PILE_RX + 2 < N, "the puddle plus its outline would leave the canvas"


def thinned(e):
    """Palette index for body liquid `e` of the way to the floor: thinning liquid
    holds less colour, so it lifts towards white (see NECK). Solid Clawd is
    untouched, which is what keeps frame 0 exactly him."""
    if e <= 0:
        return BODY
    return LIQUID[min(int(e ** 1.6 * GLOSS_STEPS), GLOSS_STEPS - 1)]


def smoothstep(t):
    return t * t * (3 - 2 * t)


def progress(f):
    """0 -> 1 across the melt frames. Eased in so the first give is slow, but
    with no ease-out: he should not spend the last third barely settling."""
    return (f / (F - 1)) ** 1.45


def give(y, x, m):
    """How liquid sprite (y, x) is at melt progress m: 0 still Clawd, 1 already
    down on the floor. Every function below takes that same m.

    m=1 does NOT melt him flat: his crown is only ~50% gone, and that leftover
    dome IS the resting image. Nudge CROWN, TILT or SOFT and you change it."""
    depth = 1 - y / (SH - 1)                     # 0 at his feet, 1 at his shell
    u = x / (SW - 1)
    rate = 1 - TILT / 2 + TILT * u - CROWN * np.sin(np.pi * u)
    return float(np.clip((m * (1 + SOFT + CROWN) * rate - depth) / SOFT, 0, 1))


def warp(y, x, m, clock=None):
    """Sprite (y, x) -> canvas (y, x). Solid sinks; liquid thins and falls.

    `clock` melts a feature on another column's schedule: his eyes share his
    middle's, so they can never drift far enough apart to read as a glitch."""
    e = give(y, x if clock is None else clock, m)
    yy = (TOP + y + SINK * smoothstep(m)) * (1 - e) + FLOOR * e
    xx = CX + (x - SW / 2) * (1 - NECK * e) + WOBBLE * e * np.sin(y * WAVER)
    return yy, xx


def _landfall():
    """Melt progress at which the first liquid reaches the floor. Only his feet
    can land first, so only their columns are asked."""
    for f in range(F):
        m = progress(f)
        if max(give(SH - 1, x, m) for x in FEET) >= 1.0:
            return m
    return 1.0


LANDFALL = _landfall()


def pooled(m):
    """0 until the first liquid lands, then 0 -> 1 as the rest of him arrives."""
    return float(np.clip((m - LANDFALL) / max(1 - LANDFALL, EPS), 0, 1))


def pile_span(g, m):
    """Where the puddle is, read off the frame: which columns liquid has landed
    in -- anything whose rectangle has reached the floor line, which includes
    the leading tip of a strand still on its way down -- and how high it has
    mounded up. Reading it back rather than centring a dome is
    what keeps the puddle joined to him -- his middle melts last, so the first
    liquid lands out at his legs. It also spreads on its own as it fills, out to
    PILE_RX, so the span is whichever is wider; since it always covers the
    landed columns, the puddle cannot come away from him.

    Returns (left, right, height), or None while nothing has landed."""
    landed = np.nonzero((g[FLOOR:FLOOR + 2] != 0).any(axis=0))[0]
    if not len(landed):
        return None
    rx = pooled(m) * PILE_RX
    return (min(float(landed[0]), CX - rx),
            max(float(landed[-1]), CX + rx),
            pooled(m) * PILE_H)


def pile_top(xx, span):
    """Canvas row where the puddle's surface sits at column xx."""
    lo, hi, h = span
    u = (xx - (lo + hi) / 2) / max((hi - lo) / 2, EPS)
    return FLOOR + LIP - h * np.sqrt(max(0.0, 1 - min(u * u, 1)))


def dome(g, span):
    """Draw the puddle over the columns it covers. A puddle with no height
    draws nothing at all, or it blinks in as a bar under his feet."""
    lo, hi, h = span
    if h < 1:
        return
    mid = (lo + hi) / 2
    for xx in range(int(np.floor(lo)), int(np.ceil(hi)) + 1):
        if not 0 <= xx < N:
            continue
        top = pile_top(xx, span)
        deep = FLOOR + LIP - top >= WET
        lit = abs(xx - mid) < (hi - lo) * GLINT and h >= WET
        for yy in range(int(round(top)), FLOOR + LIP + 1):
            if not (0 <= yy < N and (g[yy, xx] == 0 or g[yy, xx] in CLAWD_INK)):
                continue
            if yy > FLOOR and deep:
                g[yy, xx] = SHADE
            elif lit and 0 < yy - top <= GLINT_H:
                g[yy, xx] = SHEEN
            else:
                g[yy, xx] = BODY


def superellipse(g, cy, cx, ry, rx, p, color):
    """One eye. p is high early (a square eye) and 2 once it has gone runny."""
    for yy in range(max(int(cy - ry) - 1, 0), min(int(cy + ry) + 2, N)):
        for xx in range(max(int(cx - rx) - 1, 0), min(int(cx + rx) + 2, N)):
            if abs((yy - cy) / max(ry, EPS)) ** p + \
               abs((xx - cx) / max(rx, EPS)) ** p <= 1:
                g[yy, xx] = color


def fill_holes(g):
    """Close the 1 px pinholes the warp's rounding leaves, or the outline
    dilation paints each one white and he looks stippled."""
    for _ in range(2):
        b = (g != 0).astype(np.uint8)
        p = np.pad(b, 1)                     # pad, don't roll: a roll would let
        nb = (p[:-2, 1:-1] + p[2:, 1:-1]     # one canvas edge fill the other
              + p[1:-1, :-2] + p[1:-1, 2:])
        v = np.pad(g, 1)                     # a pinhole takes a neighbour's own
        take = np.maximum.reduce([v[:-2, 1:-1], v[2:, 1:-1],    # tint: filling it
                                  v[1:-1, :-2], v[1:-1, 2:]])   # flat would speck
        holes = (b == 0) & (nb >= 3)                             # the gloss ramp
        g[holes] = np.where(take[holes] != 0, take[holes], BODY)


def compose(f):
    m = progress(f)
    g = np.zeros((N, N), dtype=np.uint8)

    for y in range(SH):
        for x in range(SW):
            if not SPRITE[y, x]:
                continue
            e = give(y, x, m)
            ya, xa = warp(y, x, m)
            yb, _ = warp(min(y + 1, SH - 1), x, m)
            _, xb = warp(y, min(x + 1, SW - 1), m)
            # a rect ends exactly where its neighbour begins (both round the
            # same warped edge): no tears down either axis, and no fattening.
            # The shear still opens pinholes, which fill_holes below closes.
            y0 = int(round(ya)); y1 = max(int(round(yb)), y0 + 1)
            x0 = int(round(xa)); x1 = max(int(round(xb)), x0 + 1)
            g[max(y0, 0):min(y1, N), max(x0, 0):min(x1, N)] = thinned(e)

    fill_holes(g)
    span = pile_span(g, m)
    if span:
        dome(g, span)

    soft = smoothstep(float(np.clip((m - EYE_MELT) / (1 - EYE_MELT), 0, 1)))
    rad = (SCALE - 1) / 2                    # centre the eye on its ART cell
    for r, c in EYE_CELLS:
        cy, cx = warp(r * SCALE + rad, c * SCALE + rad, m, clock=SW / 2)
        rest = cy
        if span and span[2] >= 1:
            rest = min(pile_top(cx, span) + EYE_SINK, float(FLOOR))
        lag = EYE_LAG * soft if c * SCALE + rad > SW / 2 else 0.0
        cy = (cy + EYE_DROOP * soft) * (1 - soft) + rest * soft + lag
        if soft == 0:                        # still a hard ART eye, so draw the
            y0 = max(int(round(cy - rad)), 0)   # cell itself, no rounded corners
            x0 = max(int(round(cx - rad)), 0)
            g[y0:y0 + SCALE, x0:x0 + SCALE] = EYE
        else:
            superellipse(g, cy, cx, rad * (1 - EYE_SQUASH * soft),
                         rad * (1 + EYE_SPREAD * soft), 8 - 6 * soft, EYE)

    g[border_mask(g != 0, pen_disk(2))] = OUTLINE
    return g


def save():
    frames = []
    for f in range(F):
        g = compose(f)
        im = Image.frombytes("P", (N, N), g.tobytes())
        im.putpalette(PAL)
        frames.append(im)

    dry = set(np.unique(np.frombuffer(frames[0].tobytes(), dtype=np.uint8)))
    assert not dry & {SHADE, *LIQUID}, \
        "frame 0 has melt colours on it — it must be plain, un-melted Clawd"

    frames[STILL].convert("RGBA").save(OUT / f"{NAME}_still.png")

    gif = OUT / f"{NAME}.gif"
    frames[0].save(
        gif, save_all=True, append_images=frames[1:],
        duration=[DUR] * (F - 1) + [HOLD], loop=0,
        transparency=T, disposal=2, optimize=False,
    )
    kb = gif.stat().st_size / 1024
    assert kb <= 128, f"{gif.name} is {kb:.0f} KB — over Slack's 128 KB cap"
    print(f"{NAME}: {F} frames @ {DUR}ms + {HOLD}ms hold, gif={kb:.0f} KB")


if __name__ == "__main__":
    save()

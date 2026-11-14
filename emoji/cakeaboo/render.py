#!/usr/bin/env python3
"""Surprise Cake Clawd -- he bursts out of a giant tiered birthday cake.

A fat two-tier cake (chocolate on top, vanilla below, on a plate) fills the
bottom of the frame. Clawd shoots up out of the frosting on top with a little
overshoot, hops for a beat with delighted ^ ^ eyes while confetti and four
streamers fan out behind him and rain back into the cake, then sinks back
behind the frosting lip so the loop can restart.

Layering is what sells the pop: cake first, then the confetti, then Clawd, and
finally the *front* of the cake (frosting lip, drips and rosettes) over the
top so he really comes out of the cake rather than standing on it.

Seamless by construction: every motion is a pure function of the loop time `s`
(in [0,1)), the loop is rotated so frame 0 lands in the hold (a good still),
and every particle is born and has landed behind the cake inside the loop,
with Clawd fully hidden at the wrap. Rendered on the full 128 grid (CELL=1).
"""
import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from shared.clawd import ART, CLAWD_RGB, EYE_RGB, WHITE_RGB, border_mask, pen_disk, pen_square, happy_eye

OUT = Path(__file__).resolve().parent
NAME = "clawd_cakeaboo"

N = 128                          # canvas (fixed: Slack emoji size)
F = 36                           # frames per loop
DUR = 60                         # ms per frame
SCALE = 9                        # cell size -> 108x72 sprite (top tier is 112 wide)
CX = (N - 1) / 2                 # horizontal centre of everything (63.5)

# ---- loop timeline (fractions of the loop) ---------------------------------
START = 0.25                     # loop time shown at frame 0: mid-hold, a good still
RISE = (0.04, 0.17)              # Clawd shoots up
HOLD = (0.17, 0.70)              # ... and hops at the top
SINK = (0.70, 0.82)              # ... then ducks back in; hidden until the wrap
OVERSHOOT = 2.2                  # back-ease overshoot on the rise (bigger = more pop)
HOPS = 4                         # hops during the hold
HOP_H = 3                        # px per hop
POP_Y = 28                       # sprite top (px) at rest at the top of the pop
HID_Y = 90                       # sprite top (px) when fully sunk behind the lip

# ---- cake geometry (all ellipses share this squashed perspective) ----------
RY = 7                           # half-height of every tier's top/bottom ellipse
TOP_CY, TOP_BASE = 78, 98        # top tier: top-surface centre y, base centre y
TOP_RX = 56                      # top tier half width (covers Clawd + his outline)
BOT_CY, BOT_BASE = 98, 116       # bottom tier
BOT_RX = 60
PLATE_CY, PLATE_RX, PLATE_RY = 116, 62, 7
CRATER_RX, CRATER_RY = 51, 4     # the dip Clawd comes out of (shows when he's gone)
CLIP_Y = 96                      # nothing but cake is ever drawn below this row
LIP = 5                          # frosting lip thickness under the front rim
DRIP = 5                         # extra length of the frosting drips
DRIP_N = 7                       # drips across the top tier
ROSETTE_R = 5                    # frosting rosettes along the front rim
ROSETTE_N = 8
STRIPE = (7, 11)                 # bottom-tier pink band: px above the base edge
DOT_STEP = 9                     # spacing of the sprinkle dots on the bottom tier

# ---- confetti & streamers ---------------------------------------------------
SEED = 2710
CONFETTI = 46                    # number of confetti bits
LAUNCH_Y = 76                    # where they leave the cake (behind Clawd)
LAND_DROP = 12                   # they land this far below the launch, behind the lip
STREAMERS = 4
STREAM_LEN = 11                  # ribbon points per streamer
STREAM_DELAY = 0.02              # loop time between consecutive ribbon points
STREAM_WAVE = 5                # px of side-to-side ripple in a ribbon

# ---- palette (P-mode GIF: index 0 is transparent) --------------------------
COLORS = [
    (0, 0, 0),                   # 0: transparent slot
    WHITE_RGB,                   # 1: outline
    CLAWD_RGB,                   # 2: body
    EYE_RGB,                     # 3: eyes
    (112, 66, 50),               # 4: chocolate
    (74, 38, 34),                # 5: cake outline / dark chocolate
    (255, 150, 182),             # 6: pink frosting
    (222, 92, 138),              # 7: deep pink (shadow / crater / ring)
    (252, 218, 140),             # 8: vanilla sponge
    (255, 246, 232),             # 9: cream (rosettes, pearls)
    (168, 198, 228),             # 10: plate
    (118, 150, 196),             # 11: plate shadow
    (230, 48, 70),               # 12: red
    (255, 190, 0),               # 13: amber
    (50, 130, 240),              # 14: blue
    (40, 184, 108),              # 15: green
    (156, 84, 218),              # 16: purple
]
(T, OUTLINE, BODY, EYE, CHOC, CHOC_D, PINK, PINK_D, VAN, CREAM, PLATE, PLATE_D,
 RED, AMBER, BLUE, GREEN, PURPLE) = range(17)
BITS = [RED, AMBER, BLUE, GREEN, PURPLE, PINK]
PAL = bytes([c for rgb in COLORS for c in rgb] + [0] * (768 - 3 * len(COLORS)))

YY, XX = np.mgrid[0:N, 0:N]


def ellipse(cy, rx, ry, cx=CX):
    return ((XX - cx) / rx) ** 2 + ((YY - cy) / ry) ** 2 <= 1.0


def disk(cy, cx, r):
    return (YY - cy) ** 2 + (XX - cx) ** 2 <= r * r + 1


def rim(x, rx, ry):
    """Height of an ellipse's front arc below its centre line, at column x."""
    t = np.clip((x - CX) / rx, -1, 1)
    return ry * np.sqrt(1 - t * t)


COLX = np.arange(N)


def tier(cy_top, cy_base, rx):
    """A tier's solid mask: top ellipse + straight sides + rounded base."""
    body = (np.abs(XX - CX) <= rx) & (YY >= cy_top) & (YY <= cy_base)
    return body | ellipse(cy_top, rx, RY) | ellipse(cy_base, rx, RY)


def build_cake():
    """Returns (index image, front mask). `front` = the part of the cake that
    sits in front of Clawd (everything below the front rim, plus the rosettes)."""
    C = np.zeros((N, N), dtype=np.uint8)

    def paint(mask, col, outline=True):
        if outline:
            C[border_mask(mask, pen_square(1))] = CHOC_D
        C[mask] = col

    # plate
    plate = ellipse(PLATE_CY + 2, PLATE_RX, PLATE_RY) | ellipse(PLATE_CY, PLATE_RX, PLATE_RY)
    paint(plate, PLATE_D)
    C[ellipse(PLATE_CY, PLATE_RX, PLATE_RY)] = PLATE
    C[ellipse(PLATE_CY, PLATE_RX - 6, PLATE_RY - 3)] = PLATE_D

    # bottom tier: vanilla with a pink band, sprinkle dots and pearls
    bot = tier(BOT_CY, BOT_BASE, BOT_RX)
    paint(bot, VAN)
    off = rim(COLX, BOT_RX, RY)[None, :]
    base_edge = BOT_BASE + off
    bot_front = bot & (YY > BOT_CY + 1)
    C[bot_front & (YY >= base_edge - STRIPE[1]) & (YY <= base_edge - STRIPE[0])] = PINK
    C[bot_front & (YY > base_edge - STRIPE[0]) & (YY <= base_edge - STRIPE[0] + 1)] = PINK_D
    cols = [RED, AMBER, BLUE, GREEN, PURPLE]
    for k, x in enumerate(range(BOT_RX * 0 + int(CX) - BOT_RX + 4, int(CX) + BOT_RX - 2, DOT_STEP)):
        y = int(BOT_BASE + RY * math.sqrt(max(0, 1 - ((x - CX) / BOT_RX) ** 2))) - 3 + (k % 2) * 0
        C[y - 1:y + 2, x - 1:x + 2] = cols[k % 5]
    # (pearls along the bottom edge)
    for x in range(int(CX) - BOT_RX + 3, int(CX) + BOT_RX - 1, 6):
        y = int(BOT_BASE + RY * math.sqrt(max(0, 1 - ((x - CX) / BOT_RX) ** 2)))
        C[disk(y - 1, x, 1) & bot] = CREAM

    # top tier: chocolate, pink top surface with a crater, drippy lip
    top = tier(TOP_CY, TOP_BASE, TOP_RX)
    paint(top, CHOC)
    surf = ellipse(TOP_CY, TOP_RX, RY)
    C[surf] = PINK
    C[ellipse(TOP_CY, CRATER_RX, CRATER_RY)] = PINK_D
    arc = TOP_CY + rim(COLX, TOP_RX, RY)
    for x in range(int(CX) - TOP_RX, int(CX) + TOP_RX):
        a = arc[x]
        u = (x - (CX - TOP_RX)) / (2 * TOP_RX) * DRIP_N * math.pi
        drip = DRIP * max(0.0, math.sin(u)) ** 2
        bottom = a + LIP + drip
        sel = (YY[:, x] >= a - 0.5) & (YY[:, x] <= bottom) & top[:, x]
        C[sel, x] = PINK
        C[(YY[:, x] > bottom) & (YY[:, x] <= bottom + 1) & top[:, x], x] = PINK_D
    # sprinkles on the chocolate below the drips
    for k, x in enumerate(range(int(CX) - TOP_RX + 8, int(CX) + TOP_RX - 4, 11)):
        y = int(arc[x] + LIP + DRIP + 6 + (k % 2) * 3)
        C[y:y + 2, x:x + 3] = cols[(k + 2) % 5]
    C[border_mask(top, pen_square(1)) & (C == CHOC_D)] = CHOC_D

    # front mask: below the front arc; plus the rosettes standing on the rim
    xs = np.clip(XX, 0, N - 1)
    inside = np.abs(XX - CX) <= TOP_RX
    arc2 = np.where(inside, TOP_CY + rim(XX, TOP_RX, RY), TOP_CY)
    front = (C != 0) & (YY >= arc2)
    for i in range(ROSETTE_N):
        x = CX - TOP_RX + 8 + i * (2 * TOP_RX - 16) / (ROSETTE_N - 1)
        y = TOP_CY + rim(np.array([x]), TOP_RX, RY)[0] - 1
        d_out = disk(y, x, ROSETTE_R + 1)
        d_in = disk(y, x, ROSETTE_R - 1)
        C[d_out] = PINK_D
        C[d_in] = CREAM
        C[disk(y - 2, x - 1, 1)] = PINK
        front |= d_out
    return C, front


CAKE, FRONT = build_cake()


# ---- Clawd ------------------------------------------------------------------
def sprite(happy):
    h, w = len(ART) * SCALE, len(ART[0]) * SCALE
    g = np.zeros((h, w), dtype=np.uint8)
    for r, row in enumerate(ART):
        for c, ch in enumerate(row):
            if ch == ".":
                continue
            g[r * SCALE:(r + 1) * SCALE, c * SCALE:(c + 1) * SCALE] = EYE if ch == "O" else BODY
    if happy:
        for r, row in enumerate(ART):
            for c, ch in enumerate(row):
                if ch == "O":
                    g[r * SCALE:(r + 1) * SCALE, c * SCALE:(c + 1) * SCALE] = BODY
                    happy_eye(g, r * SCALE, c * SCALE, SCALE, EYE)
    return g


SPRITES = {False: sprite(False), True: sprite(True)}
SH, SW = SPRITES[True].shape


def smooth(p):
    return p * p * (3 - 2 * p)


def clawd_state(s):
    """-> (sprite top y, x shake, happy eyes?, visible?) at loop time s."""
    if s < RISE[0] or s >= SINK[1]:
        return HID_Y, 0, False, False
    if s < RISE[1]:
        p = (s - RISE[0]) / (RISE[1] - RISE[0])
        c = OVERSHOOT
        e = 1 + (c + 1) * (p - 1) ** 3 + c * (p - 1) ** 2         # back-ease-out
        return HID_Y + (POP_Y - HID_Y) * e, 0, False, True
    if s < HOLD[1]:
        p = (s - HOLD[0]) / (HOLD[1] - HOLD[0])
        hop = HOP_H * abs(math.sin(math.pi * HOPS * p))
        # settle: no x shake at either end of the hold
        shake = 2 * math.sin(2 * math.pi * HOPS * p) * math.sin(math.pi * p)
        return POP_Y - hop, shake, True, True
    p = (s - SINK[0]) / (SINK[1] - SINK[0])
    return POP_Y + (HID_Y - POP_Y) * smooth(p) ** 1.5, 0, False, True


# ---- confetti ---------------------------------------------------------------
def gravity(h, drop):
    """Gravity (px per unit-flight^2) for a bit that peaks h above launch and
    lands `drop` below it after one unit of flight time: y = -vy t + g t^2/2."""
    # y(1) = -vy + g/2 = drop, peak = vy^2/(2g) = h  ->  (g/2 - drop)^2 = 2 g h
    # g^2/4 - g(drop + 2h) + drop^2 = 0, take the larger root
    b = drop + 2 * h
    return 2 * (b + math.sqrt(b * b - drop * drop))


def make_bits():
    rs = np.random.RandomState(SEED)
    bits = []
    for i in range(CONFETTI):
        x0 = rs.uniform(16, 112)
        h = rs.uniform(44, 70)
        dx = float(np.clip(rs.uniform(-8, 8) + (x0 - CX) * 0.3, -22, 22))
        x0 = float(np.clip(x0, 12, 115 - abs(dx)))
        bits.append(dict(x0=x0, dx=dx, h=h, s0=rs.uniform(0.08, 0.32),
                         D=rs.uniform(0.38, 0.52), col=BITS[i % len(BITS)],
                         shape=i % 3, spin=rs.randint(0, 2)))
    return bits


def make_streamers():
    out = []
    spec = [(-1, 16, RED), (-1, 36, BLUE), (1, 36, AMBER), (1, 16, GREEN)]
    rs = np.random.RandomState(SEED + 1)
    for side, dx, col in spec:
        out.append(dict(x0=CX + side * 22, dx=side * dx * rs.uniform(1.3, 1.7),
                        h=rs.uniform(48, 58), s0=0.09 + 0.02 * len(out), D=0.55, col=col,
                        ph=rs.uniform(0, 6.28)))
    return out


BIT_LIST, STREAMER_LIST = make_bits(), make_streamers()


def flight(b, tau):
    g = gravity(b["h"], LAND_DROP)
    vy = g / 2 - LAND_DROP
    return b["x0"] + b["dx"] * tau, LAUNCH_Y - vy * tau + 0.5 * g * tau * tau


def stamp(g, y, x, h, w, col):
    y0, x0 = int(round(y - h / 2)), int(round(x - w / 2))
    ya, yb, xa, xb = max(0, y0), min(N, y0 + h), max(0, x0), min(N, x0 + w)
    if ya < yb and xa < xb:
        g[ya:yb, xa:xb] = col


def draw_particles(g, s):
    for b in BIT_LIST:
        tau = (s - b["s0"]) / b["D"]
        if not 0 <= tau < 1:
            continue
        x, y = flight(b, tau)
        flip = (int(tau * 5) + b["spin"]) % 2
        if b["shape"] == 0:
            stamp(g, y, x, 5, 5, b["col"])
        elif flip:
            stamp(g, y, x, 3, 7, b["col"])
        else:
            stamp(g, y, x, 7, 3, b["col"])
    for st in STREAMER_LIST:
        for k in range(STREAM_LEN):
            tau = (s - st["s0"] - k * STREAM_DELAY) / st["D"]
            if not 0 <= tau < 1:
                continue
            x, y = flight(st, tau)
            w = min(1.0, tau * 4)
            x += STREAM_WAVE * math.sin(st["ph"] + 1.1 * k) * w
            y += STREAM_WAVE * 0.6 * math.cos(st["ph"] + 1.1 * k) * w
            stamp(g, y, x, 4, 4, st["col"])


# ---- frame ------------------------------------------------------------------
def compose(f):
    s = (f / F + START) % 1.0
    g = np.zeros((N, N), dtype=np.uint8)
    g[CAKE != 0] = CAKE[CAKE != 0]                       # whole cake first

    parts = np.zeros((N, N), dtype=np.uint8)
    draw_particles(parts, s)
    keep = (parts != 0) & ~FRONT & (YY < CLIP_Y)
    g[keep] = parts[keep]

    y0, shake, happy, visible = clawd_state(s)
    if visible:
        layer = np.zeros((N, N), dtype=np.uint8)
        sp = SPRITES[happy]
        ty, tx = int(round(y0)), int(round(CX - SW / 2 + shake + 0.5))
        ya, xa = max(0, ty), max(0, tx)
        ye, xe = min(N, ty + SH), min(N, tx + SW)
        layer[ya:ye, xa:xe] = sp[ya - ty:ye - ty, xa - tx:xe - tx]
        outline = border_mask(layer != 0, pen_disk(2))
        layer[outline] = OUTLINE
        show = (layer != 0) & ~FRONT & (YY < CLIP_Y)
        g[show] = layer[show]

    g[FRONT & (CAKE != 0)] = CAKE[FRONT & (CAKE != 0)]    # lip + rosettes over Clawd
    return g


def save():
    frames = []
    for f in range(F):
        g = compose(f)
        im = Image.frombytes("P", (N, N), g.tobytes())
        im.putpalette(PAL)
        frames.append(im)

    still = OUT / f"{NAME}_still.png"
    frames[0].convert("RGBA").save(still)

    gif = OUT / f"{NAME}.gif"
    frames[0].save(gif, save_all=True, append_images=frames[1:], duration=DUR, loop=0,
                   transparency=T, disposal=2, optimize=False)
    assert Image.open(gif).size == (N, N)
    kb = gif.stat().st_size / 1024
    assert kb <= 128, f"{gif.name} is {kb:.0f} KB -- over Slack's 128 KB cap"

    pts = [np.nonzero(np.asarray(compose(f))) for f in range(F)]
    ys = np.concatenate([p[0] for p in pts]); xs = np.concatenate([p[1] for p in pts])
    print(f"{NAME}: {F} frames @ {DUR}ms, gif={kb:.0f} KB, "
          f"margins t {ys.min()} b {N - 1 - ys.max()} l {xs.min()} r {N - 1 - xs.max()}")


if __name__ == "__main__":
    save()

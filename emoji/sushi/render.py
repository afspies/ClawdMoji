#!/usr/bin/env python3
"""'Sushi' Clawd -- he isn't eating the sushi, he *is* the sushi: one slab of
Clawd-coloured salmon pressed onto a bed of rice, about to be picked up.

  Clawd    : the authentic sprite, unreshaped and uncostumed. His #DA7758
             already *is* salmon, so the only thing that turns the creature into
             a topping is the rice coming up over his little legs. The moment he
             leaves the board his eyes squeeze into delighted '^' arcs and his
             cheeks go pink -- he is thrilled to be eaten.
  rice     : a rounded press of cream grains with a broad nori band across the
             front and a shaded underside, so it still reads as an object on a
             white Slack background.
  board    : a wooden board across the bottom. The nigiri lifts off it, and
             that opening gap is what sells the pick-up at 32 px.
  sticks   : two tapered chopsticks reaching in from the right edge, on a line
             that stays clear of his outstretched hand -- a rod drawn across the
             sprite lops the hand off and leaves it floating as an island. The
             far rod passes behind the rice and the near one in front. They
             pinch, lift the whole nigiri, set it down, and let go.

Seamless by construction: every animated quantity is a `track()` -- piecewise
smoothstep over keyframes whose first and last values are equal -- plus a
sin(2*pi*f/F) idle bob, so frame 0 and frame F match exactly.
"""
import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from shared.clawd import ART, border_mask, happy_eye, pen_disk

OUT = Path(__file__).resolve().parent
NAME = "clawd_sushi"

N = 128
F = 22
DUR = 80

COLORS = [
    (0, 0, 0),          # 0  transparent
    (218, 119, 88),     # 1  CLAWD body #DA7758
    (0, 0, 0),          # 2  eye
    (255, 255, 255),    # 3  white outline
    (246, 241, 229),    # 4  rice
    (208, 197, 174),    # 5  rice shade / grain
    (28, 46, 34),       # 6  nori
    (58, 84, 62),       # 7  nori sheen
    (188, 132, 78),     # 8  chopstick (near)
    (162, 112, 66),     # 9  chopstick (far)
    (150, 104, 62),     # 10 board
    (110, 72, 42),      # 11 board shade
    (233, 116, 129),    # 12 blush
]
(T, CLAWD, EYE, WHITE, RICE, RICE_D,
 NORI, NORI_HI, STICK, STICK_D, BOARD, BOARD_D, BLUSH) = range(13)
PAL = bytes([c for rgb in COLORS for c in rgb] + [0] * (768 - 3 * len(COLORS)))

# ---- layout (world px) ------------------------------------------------
SCALE = 8                      # 12x8 art -> 96x64 sprite
CX = 54                        # nigiri centre column
CLAWD_TOP = 16

RICE_TOP = 64                  # level with row 6 of the art: swallows his legs
RICE_W, RICE_H = 88, 46
NORI_OFF = 28                  # band's top, measured down from the rice sprite

BOARD_Y0, BOARD_Y1 = 112, 128
BOARD_X0, BOARD_X1 = 0, 128

BUTT = (28, 127)               # chopsticks: shared pivot, out at the right edge
TIP = (98, 92)                 # where the tips close on the rice
BUTT_SPREAD = 10               # the two rods stay this far apart at the pivot
GAP_OPEN, GAP_SHUT = 18, 6
LIFT = 12                      # how far the nigiri comes off the board
BOB = 2                        # idle breath while it sits there
SWAY = 1.5                     # the sticks waver while they're still empty
DELIGHT = 0.2                  # lift fraction past which the happy face shows;
                               # at F=22 that is frames 8..16, clear of both edges

BLUSH_AT = ((27, 26), (27, 78))   # cheek centres in sprite px, one per eye
BLUSH_R = (5, 9)                  # half-height, half-width of each patch

PAD = 4                        # room for the white outline on every sprite

LIFT_KEYS = [(0.0, 0.0), (0.30, 0.0), (0.46, 1.0), (0.62, 1.0), (0.78, 0.0), (1.0, 0.0)]
GAP_KEYS = [(0.0, 1.0), (0.14, 1.0), (0.26, 0.0), (0.70, 0.0), (0.84, 1.0), (1.0, 1.0)]


def track(t, keys):
    """Piecewise-smoothstep keyframes. keys[0] and keys[-1] must share a value
    or the loop will jump."""
    for (t0, v0), (t1, v1) in zip(keys, keys[1:]):
        if t <= t1:
            u = 0.0 if t1 == t0 else (t - t0) / (t1 - t0)
            return v0 + (v1 - v0) * u * u * (3 - 2 * u)
    return keys[-1][1]


assert LIFT_KEYS[0][1] == LIFT_KEYS[-1][1] and GAP_KEYS[0][1] == GAP_KEYS[-1][1]


def fill_disk(A, cy, cx, r, color):
    H, W = A.shape
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            if dy * dy + dx * dx <= r * r:
                y, x = cy + dy, cx + dx
                if 0 <= y < H and 0 <= x < W:
                    A[y, x] = color


def blit(g, arr, y0, x0):
    ys, xs = np.nonzero(arr)
    for ry, rx in zip(ys, xs):
        y, x = y0 + ry, x0 + rx
        if 0 <= y < N and 0 <= x < N:
            g[y, x] = arr[ry, rx]


def build_body(delighted=False):
    """The sprite, optionally wearing the happy face. Both variants cover exactly
    the same pixels -- the eye cell is recoloured, never resized -- so the
    occlusion guard in save() still measures only what the chopsticks hide."""
    h, w = 8 * SCALE, 12 * SCALE
    A = np.zeros((h + 2 * PAD, w + 2 * PAD), dtype=np.uint8)
    for r, row in enumerate(ART):
        for c, ch in enumerate(row):
            if ch == ".":
                continue
            fill = CLAWD if (delighted or ch != "O") else EYE
            A[PAD + r * SCALE:PAD + (r + 1) * SCALE,
              PAD + c * SCALE:PAD + (c + 1) * SCALE] = fill

    if delighted:
        for r, row in enumerate(ART):
            for c, ch in enumerate(row):
                if ch == "O":
                    happy_eye(A, PAD + r * SCALE, PAD + c * SCALE, SCALE, EYE)
        ry, rx = BLUSH_R
        for cy, cx in BLUSH_AT:
            for dy in range(-ry, ry + 1):
                for dx in range(-rx, rx + 1):
                    y, x = cy + dy, cx + dx
                    if ((dy / ry) ** 2 + (dx / rx) ** 2 <= 1 and 0 <= y < A.shape[0]
                            and 0 <= x < A.shape[1] and A[y, x] == CLAWD):
                        A[y, x] = BLUSH

    A[border_mask(A > 0, pen_disk(2))] = WHITE
    return A


def build_rice():
    rad = 9
    A = np.zeros((RICE_H + 2 * PAD, RICE_W + 2 * PAD), dtype=np.uint8)
    for y in range(RICE_H):
        for x in range(RICE_W):
            cy = min(max(y, rad), RICE_H - 1 - rad)
            cx = min(max(x, rad), RICE_W - 1 - rad)
            if (y - cy) ** 2 + (x - cx) ** 2 <= rad * rad:
                A[PAD + y, PAD + x] = RICE

    rng = np.random.default_rng(7)             # seeded: the grain never flickers
    for _ in range(40):
        y, x = rng.integers(3, RICE_H - 3), rng.integers(4, RICE_W - 4)
        if A[PAD + y, PAD + x] == RICE:
            A[PAD + y, PAD + x:PAD + x + 3] = RICE_D

    under = A[PAD + NORI_OFF - 5:PAD + NORI_OFF, :]
    under[under == RICE] = RICE_D

    band = A[PAD + NORI_OFF:PAD + RICE_H, :]
    band[band != 0] = NORI
    A[PAD + NORI_OFF + 3:PAD + NORI_OFF + 9, PAD + 8:PAD + RICE_W - 24] = NORI_HI

    A[border_mask(A > 0, pen_disk(2))] = WHITE
    return A


BODY, HAPPY, RICEP = build_body(), build_body(delighted=True), build_rice()


def draw_board(g):
    g[BOARD_Y0:BOARD_Y1, BOARD_X0:BOARD_X1] = BOARD
    g[BOARD_Y0:BOARD_Y0 + 3, BOARD_X0:BOARD_X1] = BOARD_D
    g[BOARD_Y1 - 3:BOARD_Y1, BOARD_X0:BOARD_X1] = BOARD_D


FAR, NEAR = ((+1, STICK_D),), ((-1, STICK),)   # (side, colour); side picks
                                              # which way off the centre line


def draw_sticks(g, gap, dy, dx, rods):
    """Draw the rods in `rods` -- a sequence of (side, colour). Every rod shares
    the same pivot and its tip sits `gap`/2 off the centre line on its side.

    Offsets arrive unrounded: a diagonal rod re-rasterises on every fractional
    shift, which is what keeps neighbouring frames distinct."""
    A = np.zeros((N, N), dtype=np.uint8)
    by, bx = BUTT[0] + dy, BUTT[1] + dx
    ty, tx = TIP[0] + dy, TIP[1] + dx
    length = math.hypot(ty - by, tx - bx)
    py, px = (tx - bx) / length, -(ty - by) / length          # unit normal

    for side, color in rods:
        y0, x0 = by + py * side * BUTT_SPREAD / 2, bx + px * side * BUTT_SPREAD / 2
        y1, x1 = ty + py * side * gap / 2, tx + px * side * gap / 2
        steps = int(length) + 1
        for s in range(steps + 1):
            u = s / steps
            fill_disk(A, round(y0 + (y1 - y0) * u), round(x0 + (x1 - x0) * u),
                      max(1, round(3 - 1.7 * u)), color)

    A[border_mask(A > 0, pen_disk(1))] = WHITE
    blit(g, A, 0, 0)


def nigiri_offset(t):
    """How far the whole piece sits off its resting place, in whole pixels."""
    return round(BOB * math.sin(2 * math.pi * t) - LIFT * track(t, LIFT_KEYS))


def compose(f):
    t = f / F
    swing = 2 * math.pi * t
    lift = track(t, LIFT_KEYS)
    rise = LIFT * lift
    jaw = track(t, GAP_KEYS)
    bob = BOB * math.sin(swing)
    nigiri_dy = nigiri_offset(t)

    gap = GAP_SHUT + (GAP_OPEN - GAP_SHUT) * jaw
    stick_dy = bob * (1 - jaw) - rise
    stick_dx = SWAY * math.sin(swing) * jaw

    g = np.zeros((N, N), dtype=np.uint8)
    draw_board(g)
    draw_sticks(g, gap, stick_dy, stick_dx, FAR)      # rods straddle the piece:
                                                     # this one goes behind it
    face = HAPPY if lift > DELIGHT else BODY
    blit(g, face, CLAWD_TOP + nigiri_dy - PAD, CX - 6 * SCALE - PAD)
    blit(g, RICEP, RICE_TOP + nigiri_dy - PAD, CX - RICE_W // 2 - PAD)
    draw_sticks(g, gap, stick_dy, stick_dx, NEAR)    # and this one in front
    return g


def save():
    grids = [compose(f) for f in range(F)]
    frames = []
    for g in grids:
        im = Image.frombytes("P", (N, N), g.tobytes())
        im.putpalette(PAL)
        frames.append(im)

    frames[0].convert("RGBA").save(OUT / f"{NAME}_still.png")
    gif = OUT / f"{NAME}.gif"
    frames[0].save(gif, save_all=True, append_images=frames[1:], duration=DUR,
                   loop=0, transparency=T, disposal=2, optimize=False)

    kb = gif.stat().st_size / 1024
    assert kb <= 128, f"{gif.name} is {kb:.0f} KB -- over Slack's 128 KB cap"
    assert Image.open(gif).n_frames == F, (
        "Pillow dropped duplicate frames -- a stretch of the loop is frozen, "
        "and the surviving frames no longer carry the intended timing")

    assert np.array_equal(compose(F), grids[0]), "the loop does not wrap"

    def piece(dy):
        A = np.zeros((N, N), dtype=np.uint8)
        blit(A, BODY, CLAWD_TOP + dy - PAD, CX - 6 * SCALE - PAD)
        blit(A, RICEP, RICE_TOP + dy - PAD, CX - RICE_W // 2 - PAD)
        return A

    rest = piece(0)
    want = int(np.isin(rest, (CLAWD, EYE)).sum())
    whole = int((rest != 0).sum())                   # outline included
    for f, g in enumerate(grids):
        got = int(np.isin(g, (CLAWD, EYE, BLUSH)).sum())
        assert got == want, (
            f"frame {f} shows {got} px of the creature, not {want} -- a chopstick is "
            "crossing him and cutting a piece off")
        assert int((piece(nigiri_offset(f / F)) != 0).sum()) == whole, (
            f"frame {f} pushes the piece off the canvas -- his white outline is cropping")

    # measured against the piece, not the frame: the board bleeds to three edges
    # and would peg those margins at 0 whatever the nigiri did (CONTRIBUTING)
    FIGURE = (CLAWD, EYE, BLUSH, RICE, RICE_D, NORI, NORI_HI)
    pts = [np.nonzero(np.isin(g, FIGURE)) for g in grids]
    ys = np.concatenate([p[0] for p in pts]); xs = np.concatenate([p[1] for p in pts])
    print(f"{NAME}: {F} frames @ {DUR}ms, gif={kb:.0f} KB")
    print(f"piece margins  t {ys.min()}  b {127 - ys.max()}  l {xs.min()}  r {127 - xs.max()}")


if __name__ == "__main__":
    save()

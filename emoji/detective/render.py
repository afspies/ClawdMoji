#!/usr/bin/env python3
"""Clawdlock Holmes — Clawd in a deerstalker, peering through a magnifying glass.

He raises the glass over his right eye, squints the other one, leans side to
side while he studies you (feet planted), then lowers it. The lens resamples
the frame underneath it, so what you see in the glass is his eye, magnified.

NOTE: this one is deliberately not built on the shared ART grid. It is drawn on
its own 72-cell grid, read off the terminal splash's half-block glyphs (wide
body, one-row hands, tall eyes), then cropped and scaled up to the canvas. The
1 px white outline is applied at full resolution.
"""
import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from shared.clawd import WHITE_RGB, border_mask, pen_disk

OUT = Path(__file__).resolve().parent
NAME = "clawd_detective"

N = 128                 # canvas (Slack emoji size)
G = 72                  # drawing grid, before the crop
CROP = (4, 6, 60, 62)   # grid window scaled up to the canvas: 56 cells -> ~2.3 px each
F = 30                  # frames in the loop
DUR = 70                # ms per frame (multiple of 10: GIFs store centiseconds)
STILL = 15              # mid-peer frame for the gallery still

RAISE = (3, 9)          # frames over which the glass comes up
LOWER = (22, 28)        # ... and back down; frame 0 == frame F at rest
BOB = {1, 2, F - 2, F - 1}  # rest frames where he settles one cell
SWAY = 2.5              # cells his upper body leans either way while peering
SCAN = 1.5              # cells the lens drifts across his eye
ZOOM = 2.2              # lens magnification at the start of the peer
ZOOM_PULSE = 0.4        # extra magnification at the middle of it
LENS_R = (7.0, 9.0)     # lens radius at rest, raised
REST_HAND, UP_HAND = (55.0, 41.0), (52.0, 44.5)
REST_ANG, UP_ANG = 135, 225     # degrees: lens down in front of him, up over his eye
SQUINT_AT = 0.55        # how far up the glass is before the other eye squints
LEG_ROW = 50            # grid rows from here down stay planted while he leans

CLAWD = (215, 119, 87)
EYE = (20, 20, 20)
HAT = (196, 160, 118)
HAT_DARK = (122, 82, 48)
HAT_LINE = (150, 108, 70)
RING = (70, 70, 78)
RING_HI = (170, 170, 180)
HANDLE = (110, 70, 40)
HANDLE_HI = (150, 100, 60)
GLASS = (205, 232, 245)
GLINT = WHITE_RGB
TINT = 0.15             # how much the glass tints what it magnifies


def rect(a, x0, y0, x1, y1, c):
    a[max(y0, 0):max(y1 + 1, 0), max(x0, 0):max(x1 + 1, 0)] = c + (255,)


def line(a, p, q, w, c):
    (x0, y0), (x1, y1) = p, q
    n = int(max(abs(x1 - x0), abs(y1 - y0)) * 2) + 1
    for i in range(n + 1):
        t = i / n
        cx, cy = x0 + (x1 - x0) * t, y0 + (y1 - y0) * t
        for dy in range(-w, w + 1):
            for dx in range(-w, w + 1):
                if dx * dx + dy * dy <= w * w + 0.5:
                    x, y = round(cx + dx), round(cy + dy)
                    if 0 <= x < G and 0 <= y < G:
                        a[y, x] = c + (255,)


def draw_hat(a, oy):
    dome = {17: (26, 37), 18: (23, 40), 19: (21, 42), 20: (20, 43), 21: (19, 44),
            22: (19, 44), 23: (18, 45), 24: (18, 45), 25: (18, 45), 26: (18, 45)}
    for y, (x0, x1) in dome.items():
        for x in range(x0, x1 + 1):
            rect(a, x, y + oy, x, y + oy, HAT_LINE if (x % 5 == 0 or y % 4 == 0) else HAT)
    rect(a, 16, 27 + oy, 47, 29 + oy, HAT_DARK)
    rect(a, 10, 28 + oy, 16, 30 + oy, HAT_DARK)
    rect(a, 47, 28 + oy, 53, 30 + oy, HAT_DARK)
    rect(a, 29, 14 + oy, 30, 16 + oy, HAT_DARK)
    rect(a, 33, 14 + oy, 34, 16 + oy, HAT_DARK)
    rect(a, 31, 15 + oy, 32, 16 + oy, HAT_LINE)


def draw_clawd(a, oy, squint):
    rect(a, 14, 26 + oy, 49, 43 + oy, CLAWD)
    rect(a, 17, 44 + oy, 46, 49 + oy, CLAWD)
    rect(a, 8, 38 + oy, 13, 43 + oy, CLAWD)
    for lx in (17, 23, 38, 44):
        rect(a, lx, 50 + oy, lx + 2, 55 + oy, CLAWD)
    if squint:
        rect(a, 19, 35 + oy, 24, 36 + oy, EYE)
    else:
        rect(a, 20, 32 + oy, 22, 37 + oy, EYE)
    rect(a, 41, 32 + oy, 43, 37 + oy, EYE)
    rect(a, 42, 33 + oy, 42, 33 + oy, GLINT)
    draw_hat(a, oy - 4)


def ease(t):
    t = min(max(t, 0.0), 1.0)
    return t * t * (3 - 2 * t)


def lerp(a, b, t):
    return a + (b - a) * t


def raised(f):
    """0 at rest, 1 with the glass at his eye."""
    if f < RAISE[0] or f >= LOWER[1]:
        return 0.0
    if f < RAISE[1]:
        return ease((f - RAISE[0]) / (RAISE[1] - RAISE[0] - 1))
    if f < LOWER[0]:
        return 1.0
    return 1 - ease((f - LOWER[0]) / (LOWER[1] - LOWER[0] - 1))


def peer(f):
    """0 -> 1 across the frames the glass is fully up, else None."""
    if RAISE[1] <= f < LOWER[0]:
        return (f - RAISE[1]) / (LOWER[0] - RAISE[1])
    return None


def lean_dx(y, sway):
    return round(sway) if y < LEG_ROW else 0


def lean(a, sway):
    out = np.zeros_like(a)
    s = round(sway)
    top = a[:LEG_ROW]
    if s >= 0:
        out[:LEG_ROW, s:] = top[:, :G - s]
    else:
        out[:LEG_ROW, :s] = top[:, -s:]
    out[LEG_ROW:] = a[LEG_ROW:]
    return out


def magnify(scene, a, cx, cy, r, zoom):
    yy, xx = np.mgrid[:G, :G]
    inside = (xx - cx) ** 2 + (yy - cy) ** 2 <= r * r
    sx = np.clip(np.round(cx + (xx - cx) / zoom).astype(int), 0, G - 1)
    sy = np.clip(np.round(cy + (yy - cy) / zoom).astype(int), 0, G - 1)
    src = scene[sy, sx]
    tinted = np.round(src[..., :3] * (1 - TINT) + np.array(GLASS) * TINT).astype(np.uint8)
    empty = src[..., 3] == 0
    a[inside & empty] = GLASS + (255,)
    a[inside & ~empty, :3] = tinted[inside & ~empty]
    a[inside & ~empty, 3] = 255


def ring(a, cx, cy, r):
    yy, xx = np.mgrid[:G, :G]
    d = np.hypot(xx - cx, yy - cy)
    band = (d >= r - 0.4) & (d <= r + 1.3)
    hi = band & (xx < cx) & (yy < cy)
    a[band & ~hi] = RING + (255,)
    a[hi] = RING_HI + (255,)


def frame_rgba(f):
    f %= F
    r = raised(f)
    p = peer(f)
    sway = SWAY * math.sin(2 * math.pi * p) if p is not None else 0.0
    scan = round(SCAN * math.cos(2 * math.pi * p)) if p is not None else 0
    zoom = ZOOM + (ZOOM_PULSE * math.sin(math.pi * p) if p is not None else 0.0)
    bob = 1 if f in BOB else 0

    flat = np.zeros((G, G, 4), dtype=np.uint8)
    draw_clawd(flat, bob, squint=r > SQUINT_AT)
    scene = lean(flat, sway)

    hy = lerp(REST_HAND[1], UP_HAND[1], r) + bob
    hx = lerp(REST_HAND[0], UP_HAND[0], r) + lean_dx(hy, sway)
    ang = math.radians(lerp(REST_ANG, UP_ANG, r))
    lens_r = lerp(*LENS_R, r)
    reach = lens_r + 5
    lx = hx + reach * math.cos(ang) + scan
    ly = hy + reach * math.sin(ang)

    a = scene.copy()
    line(a, (49 + lean_dx(40.5, sway), 40.5 + bob), (hx, hy), 2, CLAWD)
    edge = (lx - (lens_r + 1) * math.cos(ang), ly - (lens_r + 1) * math.sin(ang))
    line(a, edge, (hx, hy), 1, HANDLE)
    line(a, (lerp(edge[0], hx, 0.4), lerp(edge[1], hy, 0.4)), (hx, hy), 1, HANDLE_HI)
    magnify(scene, a, lx, ly, lens_r, zoom)
    ring(a, lx, ly, lens_r)
    gx, gy = round(lx - 3), round(ly - 4)
    rect(a, gx, gy, gx + 1, gy, GLINT)
    rect(a, gx, gy, gx, gy + 1, GLINT)

    im = Image.fromarray(a, "RGBA").crop(CROP).resize((N, N), Image.NEAREST)
    return np.asarray(im)


def palette(rgba_frames):
    """One shared palette for every frame: index 0 transparent, 1 the outline."""
    colors = {WHITE_RGB}
    for a in rgba_frames:
        colors |= {tuple(int(v) for v in c) for c in a[a[..., 3] > 0][:, :3]}
    ordered = [WHITE_RGB] + sorted(colors - {WHITE_RGB})
    assert len(ordered) < 256, f"{len(ordered)} colours won't fit one GIF palette"
    return [(0, 0, 0)] + ordered


def compose(f, colors):
    a = frame_rgba(f)
    lut = {c: i for i, c in enumerate(colors)}
    g = np.zeros((N, N), dtype=np.uint8)
    solid = a[..., 3] > 0
    g[solid] = [lut[tuple(int(v) for v in c)] for c in a[solid][:, :3]]
    g[border_mask(g != 0, pen_disk(1))] = 1
    return g


def save():
    colors = palette(frame_rgba(f) for f in range(F))
    pal = bytes([c for rgb in colors for c in rgb] + [0] * (768 - 3 * len(colors)))
    grids = [compose(f, colors) for f in range(F)]
    assert np.array_equal(grids[0], compose(F, colors)), "loop seam: frame F must equal frame 0"

    frames = []
    for g in grids:
        im = Image.frombytes("P", (N, N), g.tobytes())
        im.putpalette(pal)
        frames.append(im)

    frames[STILL].convert("RGBA").save(OUT / f"{NAME}_still.png")

    gif = OUT / f"{NAME}.gif"
    frames[0].save(
        gif, save_all=True, append_images=frames[1:], duration=DUR, loop=0,
        transparency=0, disposal=2, optimize=False,
    )
    kb = gif.stat().st_size / 1024
    assert kb <= 128, f"{gif.name} is {kb:.0f} KB — over Slack's 128 KB cap"
    print(f"{NAME}: {F} frames @ {DUR}ms, {len(colors)} colours, gif={kb:.0f} KB")


if __name__ == "__main__":
    save()

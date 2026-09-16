#!/usr/bin/env python3
"""Shared Clawd definition + helpers for every emoji renderer.

The pixel-art grid (`ART`) and the canonical colours are the single source of
truth: every ``emoji/*/render.py`` imports them from here, so the creature is
identical across all variants. This module also provides the white-outline
dilation that each renderer used to carry its own copy of.

A renderer picks this up with a tiny shim (it lives two levels down, in
``emoji/<name>/render.py``)::

    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from shared.clawd import ART, CLAWD_RGB, EYE_RGB, WHITE_RGB, border_mask, pen_square
"""
from pathlib import Path
import numpy as np

ROOT   = Path(__file__).resolve().parent.parent      # ClawdMoji/
SOURCE = ROOT / "source"
EMOJI  = ROOT / "emoji"

# 12x8 grid recovered from the logo (see tools/analyze_grid.py):
#   '#' = orange body, 'O' = eye, '.' = empty.
ART = [
    "..########..",
    "..#O####O#..",
    "############",
    "############",
    "..########..",
    "..########..",
    "..#.#..#.#..",
    "..#.#..#.#..",
]
GY, GX = len(ART), len(ART[0])          # 8 rows, 12 cols

# Colours sampled from the source splash.
CLAWD_RGB = (218, 119, 88)              # #DA7758 body
EYE_RGB   = (0, 0, 0)
WHITE_RGB = (255, 255, 255)


def pen_square(r=1):
    """Chebyshev (square) dilation pen of radius r -> (2r+1)^2 offsets."""
    return [(dy, dx) for dy in range(-r, r + 1) for dx in range(-r, r + 1)]


def pen_disk(r):
    """Roughly circular dilation pen: offsets with dy^2 + dx^2 <= r^2 + 1."""
    lim = r * r + 1
    return [(dy, dx) for dy in range(-r, r + 1) for dx in range(-r, r + 1)
            if dy * dy + dx * dx <= lim]


def _arc_eye(A, ty, tx, scale, color, thick, origin, curve):
    """Draw one closed-eye arc across the eye cell at (ty, tx), `scale` wide.

    `curve` maps -1..+1 across the cell to a 0..1 drop below `origin`; that is
    the only thing separating the two closed eyes below. For scale >= 5 the arc
    stays inside the cell, which callers rely on: a closed eye has to be a
    recolour of the cell the open 'O' used, not a reshape of the creature.
    """
    depth = max(2, scale // 3)
    H, W = A.shape
    for i in range(scale):
        t = 2 * i / (scale - 1) - 1                  # -1 .. +1 across the cell
        y = int(round(origin + depth * curve(t)))
        for k in range(thick):
            if 0 <= y + k < H and 0 <= tx + i < W:
                A[y + k, tx + i] = color


def shut_eye(A, ty, tx, scale, color):
    """Draw a sleeping eyelid over one eye cell, at (ty, tx) with cell `scale`.

    The '\u203f' arc sits lowest in the middle and lifts at both ends, and occupies
    exactly the cell the open 'O' eye used -- so a sleeping Clawd is a costume
    change, not a reshape of the creature.

    Both the dip and the stroke are scale/3, deliberately fat: emoji are read at
    32 px, where a 2 px lid on a SCALE=10 sprite renders as half a pixel and
    disappears. Bold shapes over fine detail.
    """
    dip = max(2, scale // 3)
    _arc_eye(A, ty, tx, scale, color, max(2, scale // 3),
             ty + scale // 2 - dip // 2, lambda t: 1 - t * t)


def happy_eye(A, ty, tx, scale, color):
    """Draw a closed, smiling '^' eye over one eye cell, at (ty, tx) with cell
    `scale`. The mirror of shut_eye: the arc peaks in the middle and falls away
    at both ends, which is the anime delight eye rather than a sleeping lid.
    It keeps shut_eye's containment contract -- the arc stays inside the cell.

    Fatter than shut_eye's stroke, because a '^' carries less ink than a '\u203f':
    at 32 px a thin one reads as no eye at all.
    """
    rise = max(2, scale // 3)
    thick = max(2, round(scale / 2.5))
    _arc_eye(A, ty, tx, scale, color, thick,
             ty + scale // 2 - rise // 2 - thick // 3, lambda t: t * t)


def border_mask(body, pen):
    """Boolean outline ring around a body mask: dilate `body` by every (dy, dx)
    offset in `pen`, then subtract the body itself. This is exactly the
    dilation each renderer used inline for Clawd's white outline."""
    H, W = body.shape
    border = np.zeros_like(body)
    for dy, dx in pen:
        sh = np.zeros_like(body)
        ys = slice(max(0, dy), H + min(0, dy)); xs = slice(max(0, dx), W + min(0, dx))
        yt = slice(max(0, -dy), H + min(0, -dy)); xt = slice(max(0, -dx), W + min(0, -dx))
        sh[ys, xs] = body[yt, xt]; border |= sh
    return border & ~body

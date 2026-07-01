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

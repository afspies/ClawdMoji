#!/usr/bin/env python3
"""'This is fine' Clawd: calm Clawd in the foreground, room on fire.

Everything lives on one 16x16 pixel grid (cell=8px -> 128x128 emoji) so the
pixel size is consistent between the flames and Clawd.
"""
import random
from pathlib import Path
from PIL import Image

OUT = Path(__file__).resolve().parent.parent / "emoji"; OUT.mkdir(exist_ok=True)
random.seed(7)

N = 16
CELL = 8
CANVAS = N * CELL  # 128

# palette ---------------------------------------------------------------
CLAWD = (218, 119, 88, 255)   # #DA7758
EYE   = (0, 0, 0, 255)
YEL   = (255, 209, 74, 255)   # flame core
ORG   = (245, 130, 32, 255)   # flame mid
RED   = (214, 48, 32, 255)    # flame outer
EMB   = (140, 28, 18, 255)    # ember tip / dark
TRANS = (0, 0, 0, 0)

# Clawd 12x8 silhouette (#=body, O=eye) placed into the scene -----------
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
CW, CH = 12, 8
OX, OY = 2, 4  # top-left of Clawd in the 16x16 scene (head clear, legs in fire)

# --- flames: discrete tongues rising from a burning floor --------------
# per-column flame HEIGHT (rows tall, measured up from the bottom row).
# tall at the sides to frame Clawd, wavy short tongues across the floor.
heights = [13, 10, 6, 8, 5, 7, 5, 4, 5, 6, 5, 8, 6, 6, 10, 13]
tops = [N - h for h in heights]

def flame_color(depth, y):
    """depth = rows below this column's flame tip; y = absolute row."""
    if y >= N - 2:                       # white-hot floor
        return YEL if random.random() > 0.3 else ORG
    if depth <= 0:                        # flickering tip
        return EMB if random.random() > 0.45 else RED
    if depth == 1:
        return RED
    if depth <= 3:
        return ORG if random.random() > 0.25 else RED
    return YEL if random.random() > 0.4 else ORG

# build scene grid of RGBA --------------------------------------------
scene = [[TRANS for _ in range(N)] for _ in range(N)]
for x in range(N):
    for y in range(tops[x], N):
        scene[y][x] = flame_color(y - tops[x], y)

# dark ember outline so Clawd separates from the flames behind it -------
clawd_cells = {(OX + i, OY + j)
               for j in range(CH) for i in range(CW) if ART[j][i] in "#O"}
for (cx, cy) in list(clawd_cells):
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (-1, 1), (1, -1), (-1, -1)):
        nx, ny = cx + dx, cy + dy
        if 0 <= nx < N and 0 <= ny < N and (nx, ny) not in clawd_cells:
            if scene[ny][nx] != TRANS:        # only darken where flame touches Clawd
                scene[ny][nx] = EMB

# overlay Clawd (opaque, punches through the flames) -------------------
for j in range(CH):
    for i in range(CW):
        ch = ART[j][i]
        if ch == "#":
            scene[OY + j][OX + i] = CLAWD
        elif ch == "O":
            scene[OY + j][OX + i] = EYE

# render --------------------------------------------------------------
img = Image.new("RGBA", (CANVAS, CANVAS), TRANS)
px = img.load()
for y in range(N):
    for x in range(N):
        col = scene[y][x]
        if col[3] == 0:
            continue
        for dy in range(CELL):
            for dx in range(CELL):
                px[x*CELL+dx, y*CELL+dy] = col
img.save(OUT / "clawd_fine.png")
print(f"wrote emoji/clawd_fine.png {CANVAS}x{CANVAS}; flame tops={tops}")

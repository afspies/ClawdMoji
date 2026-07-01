#!/usr/bin/env python3
"""Parse the source logo, isolate the orange Clawd, and recover the underlying
pixel-art grid (cell size + boolean cell matrix), robust to anti-aliasing."""
from pathlib import Path
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent          # clawd-emoji/
SRC = ROOT / "source" / "clawd_source.png"
BUILD = ROOT / "build"; BUILD.mkdir(exist_ok=True)      # intermediate arrays (gitignored)

img = Image.open(SRC).convert("RGB")
arr = np.array(img)
H, W, _ = arr.shape

r, g, b = arr[..., 0].astype(int), arr[..., 1].astype(int), arr[..., 2].astype(int)
# Body (orange) OR eyes (near-black inside body region). First just the orange.
orange = (r > 150) & (r > g + 30) & (g > b) & (b < 160)
ys, xs = np.where(orange)
x0, x1, y0, y1 = xs.min(), xs.max(), ys.min(), ys.max()
cw, ch = x1 - x0 + 1, y1 - y0 + 1
print(f"image {W}x{H}; orange bbox {cw}w x {ch}h  at x[{x0}..{x1}] y[{y0}..{y1}]")

mask = orange.astype(np.uint8)
crop = mask[y0:y1+1, x0:x1+1]

# --- collect sub-pixel edge offsets (boundaries inside the crop) ---
def edges(lines):
    s = []
    for ln in lines:
        d = np.diff(ln.astype(int))
        s.extend((np.where(d != 0)[0] + 1).tolist())
    return s
col_e = edges(crop)        # vertical edges (x offsets)
row_e = edges(crop.T)      # horizontal edges (y offsets)

def cluster(vals, tol=3):
    vals = sorted(vals)
    out, cur = [], [vals[0]]
    for v in vals[1:]:
        if v - cur[-1] <= tol:
            cur.append(v)
        else:
            out.append(round(np.mean(cur)))
            cur = [v]
    out.append(round(np.mean(cur)))
    return out
xc = cluster(col_e); yc = cluster(row_e)
# include far boundaries (0 and width/height)
xb = sorted(set([0] + xc + [cw]))
yb = sorted(set([0] + yc + [ch]))
print("x boundaries:", xb)
print("y boundaries:", yb)

# --- find cell size: value that best divides all boundary positions ---
def score(cell, bounds):
    return sum(min(p % cell, cell - p % cell) for p in bounds)
best = None
for cell in range(8, 40):
    s = score(cell, xb) + score(cell, yb)
    # prefer cells where width & height are near-integer multiples
    s += min(cw % cell, cell - cw % cell) * 2 + min(ch % cell, cell - ch % cell) * 2
    if best is None or s < best[1]:
        best = (cell, s)
cell = best[0]
print(f"\nbest cell size: {cell}px  (residual {best[1]})")
gx, gy = round(cw / cell), round(ch / cell)
print(f"grid: {gx} x {gy} cells   (body bbox {cw}x{ch}, ideal {gx*cell}x{gy*cell})")

# --- sample grid by majority vote, anchored at bbox origin ---
grid = np.zeros((gy, gx), dtype=int)
for j in range(gy):
    for i in range(gx):
        ya, yb2 = round(j*cw/gx) if False else j*cell, (j+1)*cell
        block = crop[j*cell:(j+1)*cell, i*cell:(i+1)*cell]
        grid[j, i] = 1 if block.size and block.mean() > 0.5 else 0

print("\nrecovered body grid (# = orange):")
for row in grid:
    print("".join("#" if v else "." for v in row))

# --- locate eyes: dark squares inside the body ---
dark = (r < 80) & (g < 80) & (b < 80)
# restrict to body bbox
dcrop = dark[y0:y1+1, x0:x1+1]
eye = np.zeros((gy, gx), dtype=int)
for j in range(gy):
    for i in range(gx):
        block = dcrop[j*cell:(j+1)*cell, i*cell:(i+1)*cell]
        eye[j, i] = 1 if block.size and block.mean() > 0.4 else 0
print("\neye cells:")
for row in eye:
    print("".join("O" if v else "." for v in row))

np.save(BUILD / "grid.npy", grid); np.save(BUILD / "eye.npy", eye)
print(f"\ncell={cell}px  grid={gx}x{gy}  saved build/grid.npy, build/eye.npy")

#!/usr/bin/env python3
"""Validate every emoji against the Slack constraints — run by CI and by hand.

For each emoji/<name>/ (skipping _template):
  * meta.json exists, parses, and points at an existing output file
  * every committed .png/.gif is exactly 128x128
  * every file is <= 128 KB (Slack's custom-emoji cap)
  * GIFs actually animate (>= 2 frames) and loop forever
Exits non-zero on any violation.
"""
import json
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
CAP_KB = 128
SIZE = (128, 128)

META_KEYS = {"order", "title", "emoji", "slack", "file", "blurb", "author"}

failures = []


def fail(msg):
    failures.append(msg)
    print(f"  FAIL {msg}")


for folder in sorted((ROOT / "emoji").iterdir()):
    if not folder.is_dir() or folder.name.startswith("_"):
        continue
    print(f"== {folder.name}")

    meta_path = folder / "meta.json"
    if not meta_path.exists():
        fail(f"{folder.name}: missing meta.json")
    else:
        try:
            meta = json.loads(meta_path.read_text())
            missing = META_KEYS - set(meta)
            if missing:
                fail(f"{folder.name}: meta.json missing keys {sorted(missing)}")
            elif not (folder / meta["file"]).exists():
                fail(f"{folder.name}: meta.json points at missing file {meta['file']}")
        except json.JSONDecodeError as e:
            fail(f"{folder.name}: meta.json does not parse ({e})")

    for f in sorted(folder.glob("*.png")) + sorted(folder.glob("*.gif")):
        kb = f.stat().st_size / 1024
        if kb > CAP_KB:
            fail(f"{f.relative_to(ROOT)}: {kb:.0f} KB > {CAP_KB} KB cap")
        im = Image.open(f)
        # base ships a deliberately tight companion PNG; only the padded
        # square outputs must be exactly 128x128
        if "tight" not in f.name and im.size != SIZE:
            fail(f"{f.relative_to(ROOT)}: {im.size[0]}x{im.size[1]}, want 128x128")
        if f.suffix == ".gif":
            if getattr(im, "n_frames", 1) < 2:
                fail(f"{f.relative_to(ROOT)}: GIF has only one frame")
            if im.info.get("loop", None) != 0:
                fail(f"{f.relative_to(ROOT)}: GIF does not loop forever (loop=0)")
        print(f"  ok {f.name}: {im.size[0]}x{im.size[1]}, {kb:.0f} KB")

if failures:
    print(f"\n{len(failures)} failure(s)")
    sys.exit(1)
print("\nall emoji within Slack constraints")

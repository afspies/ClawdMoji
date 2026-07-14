# Contributing a Clawd

New variants are the whole point of this repo — and a variant is deliberately
tiny: **one folder, one `render.py`, one `meta.json`**, on top of the shared
sprite. If you can write a `sin()`, you can ship an emoji.

No code required either: open an
[emoji idea](https://github.com/afspies/ClawdMoji/issues/new?template=emoji-idea.yml)
and someone (possibly a passing Claude) may build it.

## The recipe

1. **Copy the template**

   ```bash
   cp -r emoji/_template emoji/myidea
   pip install pillow numpy
   python3 emoji/myidea/render.py    # renders a bobbing Clawd immediately
   ```

   [`emoji/_template/render.py`](emoji/_template/render.py) is ~110 lines and
   already does everything structural: rasterises the shared `ART` grid,
   builds a palette GIF with transparency, draws the white outline, loops
   seamlessly, and asserts the size cap. Mutate the `EDIT ME` spots.

2. **Build your idea in `compose(f)`** — props, scenery, motion. Look at the
   existing renderers for patterns worth stealing:
   - rigid prop attached to Clawd (sombrero: [`mariachi`](emoji/mariachi/render.py))
   - rotating limb assemblies (net swing: [`bugcatcher`](emoji/bugcatcher/render.py))
   - recolouring the sprite into a costume (tunic: [`robinhood`](emoji/robinhood/render.py))
   - full opaque scenes (meadow: [`bugcatcher`](emoji/bugcatcher/render.py))
   - simulations behind Clawd (Doom-fire: [`fire`](emoji/fire/render.py))

3. **Write `meta.json`** (copy one from any emoji folder):

   ```json
   {
     "order": 9,
     "title": "Clawd d'Idea",
     "emoji": "✨",
     "slack": "clawd-myidea",
     "file": "clawd_myidea.gif",
     "blurb": "One line for the gallery card.",
     "author": "yourhandle"
   }
   ```

4. **Regenerate the gallery** (rewrites the README table + docs site for you —
   never edit those by hand):

   ```bash
   python3 tools/gen_gallery.py
   ```

5. **Open a PR** with the folder, the committed `.gif`/`_still.png` outputs,
   and the regenerated README/docs. CI re-runs your renderer, checks the
   constraints below, and posts your GIF in the PR thread so review is just
   *looking at it*.

## Hard constraints (CI checks these)

- **128×128** pixels, **≤ 128 KB** — Slack's custom-emoji limits.
- `render.py` runs clean with only **Pillow + NumPy**, writes only into its
  own folder, and is **deterministic enough to loop**: drive all motion with
  `sin`/`cos` of `2π·f/F` (or pure functions of `f mod F`) so frame 0 and
  frame F match exactly. If you use randomness, seed it.
- **Stay authentic to Clawd.** Import the grid from
  [`shared/clawd.py`](shared/clawd.py) — costume him, recolour him, give him
  props, but don't reshape the creature. His little side-bumps are his hands;
  his 2 px white outline is sacred.

## Taste guidelines (reviewers will nudge, not block)

- Emoji are read at 32 px in Slack — favour **bold shapes over fine detail**,
  and test what your GIF looks like small.
- **Fill the frame — no padding.** Scale Clawd as large as the canvas allows:
  `SCALE=10` is a 120 px sprite spanning the full width, leaving exactly the
  4 px his outline needs. Shrink him only when something earns the space —
  props, motion range, or a full-frame scene (a meadow, a breaking wave) that
  itself reaches the edges. Empty margin around the whole composition is a
  bug, not a style. Whatever you do, **never crop**: no frame may push a
  pixel (outline included) past the canvas edge.
- **Measure the fit — don't eyeball it.** The still frame lies: what crops
  (or wastes margin) is the *animation extremes* — the far end of a sway,
  step, or swing. Take the union bounding box over the whole loop and grow
  `SCALE` / amplitudes until it sits within ~1–2 px of the canvas edge:

  ```python
  import numpy as np
  pts = [np.nonzero(np.asarray(compose(f))) for f in range(F)]
  ys = np.concatenate([p[0] for p in pts]); xs = np.concatenate([p[1] for p in pts])
  print(f"margins  t {ys.min()}  b {127 - ys.max()}  l {xs.min()}  r {127 - xs.max()}")
  ```

  (For opaque full-frame scenes, mask to Clawd's palette indices instead of
  `nonzero`.)
- Prefer the **full 128 grid** (`CELL=1`) for anything with curves or
  rotation; it halves the chunkiness.
- Keep tunables as named constants near the top with a comment — every
  renderer here is also documentation.
- One good gag beats three mediocre ones per loop.

## Credit

Your `meta.json` `author` shows up under your emoji in the README table and on
the gallery site, and your GitHub avatar joins the contributors strip in the
README. Add yourself — that's the fun part.

## Licence note

Code contributions are MIT like the rest of the repo. Clawd himself and the
Anthropic spark are Anthropic, PBC's — this is an unofficial fan project, so
keep variants tasteful and obviously fan-art.

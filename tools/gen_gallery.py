#!/usr/bin/env python3
"""Generate the README gallery table and the docs/ gallery site from
emoji/*/meta.json.

Each emoji folder owns a small meta.json:

    {
      "order": 7,                       # gallery position
      "title": "Clawdin Hood",          # display name
      "emoji": "\U0001f3f9",            # flair emoji ("" for none)
      "slack": "clawd-robinhood",       # suggested :name:
      "file": "clawd_robinhood.gif",    # the output to show
      "blurb": "one-liner",             # used on the docs site
      "author": "afspies"               # github handle — credited under the emoji
    }

The author is credited under each emoji (README table + docs cards) and in the
README contributors strip. The repo owner's credits render as "Clawd himself"
— self-crediting every card would be obnoxious — and he appears in the strip
as Clawd's pixel avatar.

So adding a variant never means hand-editing the README table — run

    python3 tools/gen_gallery.py          # rewrite README + docs/index.html
    python3 tools/gen_gallery.py --check  # exit 1 if anything is stale (CI)
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPO = "afspies/ClawdMoji"
RAW = f"https://raw.githubusercontent.com/{REPO}/main"
COLS = 4
BEGIN, END = "<!-- gallery:begin -->", "<!-- gallery:end -->"
C_BEGIN, C_END = "<!-- contributors:begin -->", "<!-- contributors:end -->"
OWNER = "afspies"  # the owner's credits render as Clawd himself (see docstring)
OWNER_CREDIT = "Clawd himself 🦀"


def load_metas():
    metas = []
    for meta_path in sorted((ROOT / "emoji").glob("*/meta.json")):
        name = meta_path.parent.name
        if name.startswith("_"):
            continue
        m = json.loads(meta_path.read_text())
        m["dir"] = name
        metas.append(m)
    metas.sort(key=lambda m: m["order"])
    return metas


def label(m):
    return f"**{m['title']}** {m['emoji']}".strip()


def credit_md(m):
    if m["author"] == OWNER:
        return f"<sub>by {OWNER_CREDIT}</sub>"
    return f"<sub>by [@{m['author']}](https://github.com/{m['author']})</sub>"


def readme_table(metas):
    rows = [metas[i:i + COLS] for i in range(0, len(metas), COLS)]
    lines = []
    for r, row in enumerate(rows):
        pad = [""] * (COLS - len(row))
        lines.append("| " + " | ".join([label(m) for m in row] + pad) + " |")
        if r == 0:
            lines.append("|" + ":---:|" * COLS)
        lines.append(
            "| "
            + " | ".join(
                [f"![{m['dir']}](emoji/{m['dir']}/{m['file']})" for m in row] + pad
            )
            + " |"
        )
        lines.append("| " + " | ".join([credit_md(m) for m in row] + pad) + " |")
    return "\n".join(lines)


def contributors_strip(metas):
    """One avatar per unique author, in gallery order; the owner is Clawd."""
    seen, cells = set(), []
    for m in metas:
        a = m["author"]
        if a in seen:
            continue
        seen.add(a)
        if a == OWNER:
            cells.append(
                '<a href="https://afspies.github.io/ClawdMoji/">'
                '<img src="emoji/base/clawd_emoji.png" width="64" height="64" '
                'alt="Clawd himself" title="Clawd himself"></a>'
            )
        else:
            cells.append(
                f'<a href="https://github.com/{a}">'
                f'<img src="https://github.com/{a}.png?size=128" width="64" height="64" '
                f'alt="@{a}" title="@{a}"></a>'
            )
    return "\n".join(cells)


def splice(text, begin, end, body):
    try:
        head, rest = text.split(begin, 1)
        _, tail = rest.split(end, 1)
    except ValueError:
        sys.exit(f"README.md is missing the {begin} / {end} markers")
    return head + begin + "\n" + body + "\n" + end + tail


def render_readme(metas, text):
    text = splice(text, BEGIN, END, readme_table(metas))
    return splice(text, C_BEGIN, C_END, contributors_strip(metas))


def render_docs(metas):
    cards = []
    for m in metas:
        flair = f" {m['emoji']}" if m["emoji"] else ""
        if m["author"] == OWNER:
            credit = f"by {OWNER_CREDIT}"
        else:
            credit = f'by <a href="https://github.com/{m["author"]}">@{m["author"]}</a>'
        cards.append(f"""\
      <div class="card">
        <img src="{RAW}/emoji/{m['dir']}/{m['file']}" alt="{m['title']}" width="128" height="128">
        <h2>{m['title']}{flair}</h2>
        <p class="by">{credit}</p>
        <p>{m['blurb']}</p>
        <button class="name" data-name=":{m['slack']}:" title="click to copy">:{m['slack']}:</button>
        <a class="dl" href="{RAW}/emoji/{m['dir']}/{m['file']}" download>download</a>
      </div>""")
    cards = "\n".join(cards)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ClawdMoji — pixel-art Clawd Slack emoji</title>
<meta name="description" content="Programmatically generated pixel-art Slack emoji of Clawd, Claude's crab-like mascot. No image editor involved.">
<style>
  :root {{ --clawd: #DA7758; --bg: #16141f; --card: #201d2b; --ink: #f0ece4; --dim: #9b93a9; }}
  * {{ box-sizing: border-box; margin: 0; }}
  body {{ background: var(--bg); color: var(--ink); font: 16px/1.5 ui-monospace, "SF Mono", Menlo, monospace; padding: 2rem 1rem 4rem; }}
  header {{ text-align: center; margin-bottom: 2.5rem; }}
  header img {{ image-rendering: pixelated; width: 96px; height: 96px; }}
  h1 {{ color: var(--clawd); font-size: 2rem; margin-top: .5rem; }}
  header p {{ color: var(--dim); max-width: 34rem; margin: .5rem auto 0; }}
  header a {{ color: var(--clawd); }}
  .grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 1rem; max-width: 64rem; margin: 0 auto; }}
  .card {{ background: var(--card); border-radius: 12px; padding: 1.25rem 1rem; text-align: center; }}
  .card img {{ image-rendering: pixelated; width: 128px; height: 128px; }}
  .card h2 {{ font-size: 1.05rem; margin-top: .6rem; }}
  .card p {{ color: var(--dim); font-size: .8rem; margin: .35rem 0 .7rem; min-height: 3.6em; }}
  .card p.by {{ font-size: .7rem; margin: .15rem 0 0; min-height: 0; }}
  .card p.by a {{ color: var(--clawd); text-decoration: none; }}
  .name {{ background: #2c2839; color: var(--clawd); border: 1px solid #3a3550; border-radius: 6px; font: inherit; font-size: .85rem; padding: .25rem .6rem; cursor: pointer; }}
  .name.copied::after {{ content: " ✓"; }}
  .dl {{ display: block; color: var(--dim); font-size: .75rem; margin-top: .5rem; }}
  .how {{ max-width: 40rem; margin: 3rem auto 0; background: var(--card); border-radius: 12px; padding: 1.5rem; }}
  .how h2 {{ color: var(--clawd); font-size: 1.1rem; }}
  .how ol {{ padding-left: 1.4rem; margin-top: .6rem; color: var(--dim); }}
  .how code {{ color: var(--ink); }}
  footer {{ text-align: center; color: var(--dim); font-size: .75rem; margin-top: 3rem; }}
  footer a {{ color: var(--clawd); }}
</style>
</head>
<body>
  <header>
    <img src="{RAW}/emoji/base/clawd_emoji.png" alt="Clawd">
    <h1>ClawdMoji</h1>
    <p>Pixel-art Slack emoji of <strong>Clawd</strong>, generated entirely with
       Python + math — no image editor involved.
       <a href="https://github.com/{REPO}">Star it / add your own on GitHub</a>.</p>
  </header>
  <div class="grid">
{cards}
  </div>
  <div class="how">
    <h2>Add to Slack</h2>
    <ol>
      <li>Download an emoji above (or grab the <a href="https://github.com/{REPO}/releases">full pack</a>).</li>
      <li>In Slack: <strong>Settings &rarr; Customize &rarr; Emoji &rarr; Add Custom Emoji</strong>.</li>
      <li>Upload the file and use the suggested <code>:name:</code> (click a name above to copy it).</li>
    </ol>
  </div>
  <footer>
    <p>Unofficial fan project — Clawd and the Anthropic spark are Anthropic, PBC's.
       Code is <a href="https://github.com/{REPO}/blob/main/LICENSE">MIT</a>.
       Want a variant that doesn't exist? <a href="https://github.com/{REPO}/issues/new?template=emoji-idea.yml">Suggest it</a>
       or <a href="https://github.com/{REPO}/blob/main/CONTRIBUTING.md">build it</a>.</p>
  </footer>
<script>
  document.querySelectorAll(".name").forEach(function (b) {{
    b.addEventListener("click", function () {{
      navigator.clipboard.writeText(b.dataset.name).then(function () {{
        b.classList.add("copied");
        setTimeout(function () {{ b.classList.remove("copied"); }}, 1200);
      }});
    }});
  }});
</script>
</body>
</html>
"""


def main():
    check = "--check" in sys.argv
    metas = load_metas()
    readme_path = ROOT / "README.md"
    docs_path = ROOT / "docs" / "index.html"

    new_readme = render_readme(metas, readme_path.read_text())
    new_docs = render_docs(metas)

    stale = []
    if readme_path.read_text() != new_readme:
        stale.append("README.md")
    if not docs_path.exists() or docs_path.read_text() != new_docs:
        stale.append("docs/index.html")

    if check:
        if stale:
            sys.exit(f"stale (run python3 tools/gen_gallery.py): {', '.join(stale)}")
        print("gallery up to date")
        return

    docs_path.parent.mkdir(exist_ok=True)
    readme_path.write_text(new_readme)
    docs_path.write_text(new_docs)
    print(f"regenerated: README.md gallery + docs/index.html ({len(metas)} emoji)")


if __name__ == "__main__":
    main()

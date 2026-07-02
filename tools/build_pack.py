#!/usr/bin/env python3
"""Bundle every emoji into build/clawdmoji-pack.zip, ready for Slack.

Each file is renamed to its suggested Slack name (clawd-fine.gif etc., from
meta.json) so uploading is just drag + accept the default name. A README.txt
with the two-click install steps rides along. Pure stdlib — no deps.
"""
import json
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "build" / "clawdmoji-pack.zip"

metas = []
for meta_path in sorted((ROOT / "emoji").glob("*/meta.json")):
    if meta_path.parent.name.startswith("_"):
        continue
    m = json.loads(meta_path.read_text())
    m["path"] = meta_path.parent / m["file"]
    metas.append(m)
metas.sort(key=lambda m: m["order"])

lines = [
    "ClawdMoji — pixel-art Clawd Slack emoji",
    "https://github.com/afspies/ClawdMoji",
    "",
    "Install: Slack → Settings → Customize → Emoji → Add Custom Emoji,",
    "upload a file; its filename is the suggested :name:.",
    "",
]
OUT.parent.mkdir(exist_ok=True)
with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as z:
    for m in metas:
        arc = f"{m['slack']}{m['path'].suffix}"
        z.write(m["path"], arc)
        flair = f" {m['emoji']}" if m["emoji"] else ""
        lines.append(f":{m['slack']}:  {m['title']}{flair} — {m['blurb']}")
    lines += [
        "",
        "Unofficial fan project — Clawd and the Anthropic spark are",
        "Anthropic, PBC's. Code is MIT.",
    ]
    z.writestr("README.txt", "\n".join(lines) + "\n")

kb = OUT.stat().st_size / 1024
print(f"wrote {OUT.relative_to(ROOT)}: {len(metas)} emoji, {kb:.0f} KB")

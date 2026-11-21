#!/usr/bin/env python3
"""Build a standalone, browser-presentable HTML (and optionally a PDF) from the deck sources.

The sources (deck.json, deck.css, slides/*.html) are the Slides artifact's files. Its custom
elements (<x-shape kind="arrow-right">, <x-icon>) are replaced by inline SVG here, so the page
works in any browser.

Usage: python3 presentation/build.py [--pdf]
  → presentation/prezentacio.html   (← → / Space / PgUp PgDn: lapozás, F: teljes képernyő, N: jegyzetek)
  → presentation/prezentacio.pdf    (--pdf: headless Google Chrome, one 1920×1080 page per slide)
"""
import argparse
import html
import json
import re
import shutil
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent

ARROW = ('<svg class="xarrow" width="36" height="20" viewBox="0 0 36 20" aria-hidden="true">'
         '<path d="M0 6h22V0l14 10-14 10v-6H0z" fill="currentColor"/></svg>')
ICONS = {  # minimal line icons in the spirit of the editor's set
    "Lightbulb": '<path d="M9 18h6M10 21h4M12 3a6 6 0 0 0-3.5 10.9c.6.5 1 1.2 1 2V16h5v-.1c0-.8.4-1.5 1-2A6 6 0 0 0 12 3z"/>',
    "Check": '<path d="M20 6L9 17l-5-5"/>',
    "Search": '<circle cx="11" cy="11" r="7"/><path d="M20 20l-4-4"/>',
    "Tool": '<path d="M14.7 6.3a4 4 0 0 0 5 5L21 13l-8 8-3-3 8-8-1.3-1.3a4 4 0 0 1-5-5L13 2l1.7 1.7z"/><path d="M3 21l6-6"/>',
}


def icon(m: re.Match) -> str:
    name, style = m.group(1), m.group(2) or ""
    body = ICONS.get(name, '<circle cx="12" cy="12" r="8"/>')
    return (f'<svg class="xicon" style="{style}" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
            f'stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{body}</svg>')


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pdf", action="store_true")
    args = ap.parse_args()

    deck = json.loads((HERE / "deck.json").read_text())
    css = (HERE / "deck.css").read_text()
    slides = []
    for sid in deck["order"]:
        s = (HERE / "slides" / f"{sid}.html").read_text()
        s = re.sub(r'<x-shape kind="arrow-right"[^>]*></x-shape>', ARROW, s)
        s = re.sub(r'<x-icon name="(\w+)"(?: style="([^"]*)")?></x-icon>', icon, s)
        slides.append(s.strip())
    fonts = "\n".join(f'<link rel="stylesheet" href="{html.escape(f["href"])}">'
                      for f in deck["faces"].values() if "href" in f)

    page = f"""<!doctype html>
<html lang="hu">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(deck["title"])}</title>
{fonts}
<style>
{css}
/* --- standalone player --- */
html, body {{ margin: 0; height: 100%; background: #0B0D11; overflow: hidden; }}
#stage {{ position: absolute; left: 50%; top: 50%; width: 1920px; height: 1080px; transform-origin: 0 0; }}
#stage > section {{ position: absolute; inset: 0; width: 1920px; height: 1080px; overflow: hidden; display: none; }}
#stage > section.on {{ display: flex; }}
section aside {{ display: none; }}
body.notes section.on aside {{ display: block; position: absolute; left: 0; right: 0; bottom: 0; padding: 24px 128px;
  background: rgba(10,12,16,.92); color: #E8ECF1; font: 24px/1.45 Inter, Arial, sans-serif; }}
.xarrow {{ display: block; }}
.flow .xarrow {{ color: var(--accent); }}
.cycle .xarrow {{ color: var(--soft-on-light); width: 32px; height: 18px; }}
.xicon {{ display: block; }}
table.plain {{ border-collapse: collapse; }}
table.plain td, table.plain th {{ padding: .5em .6em; border-bottom: 2px solid #0002; text-align: left; vertical-align: top; }}
#count {{ position: fixed; right: 16px; bottom: 12px; color: #8891; font: 14px Inter, Arial, sans-serif; }}
@media print {{
  @page {{ size: 1920px 1080px; margin: 0; }}
  html, body {{ height: auto; overflow: visible; background: none; }}
  #stage {{ position: static; transform: none !important; width: auto; height: auto; }}
  #stage > section {{ position: relative; display: flex !important; break-after: page; }}
  .rise {{ animation: none !important; }}
  #count {{ display: none; }}
}}
</style>
</head>
<body>
<div id="stage">
{chr(10).join(slides)}
</div>
<div id="count"></div>
<script>
const s = [...document.querySelectorAll('#stage > section')], stage = document.getElementById('stage');
let i = Math.max(0, Math.min(s.length - 1, (parseInt(location.hash.slice(7)) || 1) - 1));
function fit() {{ const k = Math.min(innerWidth / 1920, innerHeight / 1080);
  stage.style.transform = `scale(${{k}}) translate(-50%, -50%)`; }}
function show(n) {{ i = Math.max(0, Math.min(s.length - 1, n));
  s.forEach((x, j) => x.classList.toggle('on', j === i));
  document.getElementById('count').textContent = (i + 1) + ' / ' + s.length;
  history.replaceState(null, '', '#slide-' + (i + 1)); }}
addEventListener('resize', fit);
addEventListener('keydown', e => {{
  if (['ArrowRight', 'PageDown', ' ', 'Enter'].includes(e.key)) show(i + 1);
  else if (['ArrowLeft', 'PageUp', 'Backspace'].includes(e.key)) show(i - 1);
  else if (e.key === 'Home') show(0); else if (e.key === 'End') show(s.length - 1);
  else if (e.key === 'n' || e.key === 'N') document.body.classList.toggle('notes');
  else if (e.key === 'f' || e.key === 'F') document.fullscreenElement ? document.exitFullscreen() : document.documentElement.requestFullscreen();
}});
addEventListener('click', e => show(e.clientX > innerWidth / 3 ? i + 1 : i - 1));
fit(); show(i);
</script>
</body>
</html>
"""
    out = HERE / "prezentacio.html"
    out.write_text(page)
    print(f"→ {out.relative_to(HERE.parent)}  ({len(slides)} dia)")

    if args.pdf:
        chrome = shutil.which("google-chrome") or shutil.which("chromium")
        if not chrome:
            raise SystemExit("Nincs Google Chrome / Chromium a PDF-hez.")
        pdf = HERE / "prezentacio.pdf"
        subprocess.run([chrome, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
                        "--virtual-time-budget=8000", f"--print-to-pdf={pdf}", out.as_uri()],
                       check=True, capture_output=True)
        print(f"→ {pdf.relative_to(HERE.parent)}")


if __name__ == "__main__":
    main()

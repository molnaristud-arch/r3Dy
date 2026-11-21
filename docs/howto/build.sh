#!/usr/bin/env bash
# HowToUse.pdf (repo root) from docs/howto/HowToUse.html, with headless Google Chrome.
# The HTML is the source: edit it, then re-run this. Fonts come from Google Fonts (needs internet).
set -euo pipefail
cd "$(dirname "$0")"
chrome=$(command -v google-chrome || command -v chromium || true)
[[ -n $chrome ]] || { echo "Nincs Google Chrome / Chromium a PDF-hez." >&2; exit 1; }
out=$(realpath ../../HowToUse.pdf)
"$chrome" --headless=new --disable-gpu --no-pdf-header-footer --virtual-time-budget=10000 \
  --print-to-pdf="$out" "file://$PWD/HowToUse.html" 2>/dev/null
echo "→ HowToUse.pdf"

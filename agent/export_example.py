"""Copy a finished scan's agent artefacts into examples/<name>/ for the repo (no photos, no local paths).

Usage: .venv/bin/python agent/export_example.py data/modell_1 scan-1-handheld
Copies: agent_log.jsonl (decision log), qa.json (quality verdict), preview/view_*.png
"""

import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def scrub(text: str) -> str:
    return text.replace(str(ROOT) + "/", "").replace(str(ROOT), ".").replace(str(Path.home()), "~")


def main() -> None:
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    src, dst = Path(sys.argv[1]).resolve(), ROOT / "examples" / sys.argv[2]
    (dst / "preview").mkdir(parents=True, exist_ok=True)
    for name in ("agent_log.jsonl", "qa.json"):
        if (src / name).is_file():
            (dst / name).write_text(scrub((src / name).read_text()))
    for v in sorted((src / "preview").glob("view_*.png")):
        shutil.copy2(v, dst / "preview" / v.name)
    # a short, human-readable transcript of the decisions next to the raw log
    lines = []
    for raw in (dst / "agent_log.jsonl").read_text().splitlines():
        e = json.loads(raw)
        if e["kind"] in ("vezérlő", "eszköz", "eredmény", "kész", "hiba"):
            lines.append(f"[{e['t'][11:]}] {e['kind']:<9} {e['text'].strip()}")
    (dst / "transcript.txt").write_text("\n".join(lines) + "\n")
    print(f"→ {dst.relative_to(ROOT)}")


if __name__ == "__main__":
    main()

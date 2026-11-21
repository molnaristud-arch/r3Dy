#!/usr/bin/env python3
"""Remove the background from every image (rembg), writing JPEGs on white.

Use this when the static background is visible: a rotating object in front of a
non-rotating background confuses structure-from-motion.
"""
import argparse
from pathlib import Path

from PIL import Image
from rembg import new_session, remove


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("in_dir")
    ap.add_argument("out_dir")
    args = ap.parse_args()

    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    session = new_session("u2net")
    files = sorted(p for p in Path(args.in_dir).iterdir() if p.suffix.lower() in {".jpg", ".jpeg", ".png"})
    for i, p in enumerate(files, 1):
        cut = remove(Image.open(p), session=session)
        bg = Image.new("RGB", cut.size, (255, 255, 255))
        bg.paste(cut, mask=cut.split()[3])
        bg.save(out / f"{p.stem}.jpg", quality=95)
        print(f"[{i}/{len(files)}] {p.name}")


if __name__ == "__main__":
    main()

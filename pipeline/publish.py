#!/usr/bin/env python3
"""Put a finished GLB on the website: copy it to web/models/ and add it to models.json.

Usage: python pipeline/publish.py data/bogre/model.glb --name "Kerámia bögre" --tags kerámia konyha \
           [--description "Fehér, kézzel festett kerámia bögre."]
       (a .blend next to the GLB is published too, if present)
"""
import argparse
import json
import re
import shutil
import struct
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MODELS = ROOT / "web" / "models"
INDEX = MODELS / "models.json"


def slug(text: str) -> str:
    t = unicodedata.normalize("NFD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", t.lower()).strip("-") or "modell"


def glb_stats(path: Path):
    """Face count and bounding-box size (metres) from the GLB's JSON chunk."""
    data = path.read_bytes()
    length = struct.unpack_from("<I", data, 12)[0]
    gltf = json.loads(data[20:20 + length])
    faces, lo, hi = 0, [float("inf")] * 3, [float("-inf")] * 3
    for mesh in gltf.get("meshes", []):
        for prim in mesh["primitives"]:
            pos = gltf["accessors"][prim["attributes"]["POSITION"]]
            lo = [min(a, b) for a, b in zip(lo, pos["min"])]
            hi = [max(a, b) for a, b in zip(hi, pos["max"])]
            if "indices" in prim:
                faces += gltf["accessors"][prim["indices"]]["count"] // 3
    dims = [h - l for l, h in zip(lo, hi)]
    return faces, dims


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("glb")
    ap.add_argument("--name", required=True)
    ap.add_argument("--tags", nargs="*", default=[])
    ap.add_argument("--description", default="", help="one or two sentences shown on the card")
    args = ap.parse_args()

    src = Path(args.glb)
    base = slug(args.name)
    faces, (x, y, z) = glb_stats(src)  # glTF is Y-up: y is the height
    MODELS.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, MODELS / f"{base}.glb")
    entry = {
        "name": args.name,
        "file": f"{base}.glb",
        "tags": args.tags,
        "faces": faces,
        "size": f"{x * 100:.1f} × {z * 100:.1f} × {y * 100:.1f} cm (sz × m × mag)",
    }
    if args.description.strip():
        entry["description"] = " ".join(args.description.split())
    blend = src.with_suffix(".blend")
    if blend.exists():
        shutil.copy2(blend, MODELS / f"{base}.blend")
        entry["blend"] = f"{base}.blend"

    models = json.loads(INDEX.read_text()) if INDEX.exists() else []
    models = [m for m in models if m.get("file") != entry["file"]] + [entry]
    INDEX.write_text(json.dumps(models, ensure_ascii=False, indent=2) + "\n")
    print(f"→ web/models/{base}.glb  ({faces} lap, {entry['size']})")


if __name__ == "__main__":
    main()

"""Tools of the controller agent: thin wrappers around the existing pipeline scripts.

Every tool works on ONE scan directory (data/<scan>), fixed when the agent starts – the model
can't point a tool at an arbitrary path. Each tool returns a short, model-readable result
(dict → JSON text, optionally plus images) and appends the full output to <scan>/agent_run.log.

Manual test without the API:
    .venv/bin/python agent/tools.py data/modell_1 scan_info
    .venv/bin/python agent/tools.py data/modell_1 reconstruct '{"max_image_size": 1600}'
"""

from __future__ import annotations

import base64
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY = str(ROOT / ".venv" / "bin" / "python")
MICROMAMBA = os.environ.get("MICROMAMBA", str(Path.home() / ".local" / "bin" / "micromamba"))
os.environ.setdefault("MAMBA_ROOT_PREFIX", str(Path.home() / ".local" / "share" / "micromamba"))
IMAGE_EXT = {".jpg", ".jpeg", ".png"}
VIDEO_EXT = {".mp4", ".mov", ".mkv", ".webm", ".3gp"}


class ToolError(Exception):
    """A tool failed in a way the agent should see (returned as is_error=True)."""


# ---------------------------------------------------------------- tool schemas (sent to Claude)

def _schema(props: dict, required: list[str] | None = None) -> dict:
    return {"type": "object", "properties": props, "required": required or [], "additionalProperties": False}


TOOL_SCHEMAS = [
    {
        "name": "scan_info",
        "description": "Állapot: hány fotó/videó van a szkennelésben, van-e maszkolt képsor, "
                       "milyen köztes eredmények készültek már (modell, GLB, előnézet). Bármikor hívható, gyors.",
        "input_schema": _schema({}),
    },
    {
        "name": "extract_frames",
        "description": "Videóból a legélesebb képkockák kivágása az images/ mappába (videónként elosztva). "
                       "Csak akkor kell, ha a szkennelés videóból áll. ~30 s / perc 4K videó.",
        "input_schema": _schema({"count": {"type": "integer", "minimum": 30, "maximum": 400,
                                           "description": "összes kocka (alap 150)"}}, ["count"]),
    },
    {
        "name": "mask_background",
        "description": "Háttér kivágása minden képről (rembg, GPU) a masked/ mappába; ezután a reconstruct a "
                       "maszkolt képeket használja. Zavaros, mintás háttérnél segít, ha kevés kép regisztrálódik. "
                       "Hátrány: a mintás korong is eltűnik, ami a COLMAP-nak is támpont. ~1–2 s/kép.",
        "input_schema": _schema({}),
    },
    {
        "name": "remove_mask",
        "description": "A masked/ mappa törlése: a reconstruct újra az eredeti képeket használja.",
        "input_schema": _schema({}),
    },
    {
        "name": "reconstruct",
        "description": "Fotogrammetria: COLMAP (kamerahelyzetek) + OpenMVS (sűrű felhő, háló, textúra) → model/model.obj. "
                       "A leglassabb lépés: 80–110 képnél 8–20 perc. Visszaadja: siker, regisztrált képek száma / összes, "
                       "részmodellek száma (1-nél több = a körök nem illeszkedtek), hibakategória, napló vége.",
        "input_schema": _schema({"max_image_size": {"type": "integer", "enum": [1200, 1600, 2000],
                                                    "description": "max képméret px; 2000 az alap, CUDA OOM esetén kisebb"}},
                                ["max_image_size"]),
    },
    {
        "name": "cleanup_model",
        "description": "Blender: a legnagyobb összefüggő rész megtartása, egyszerűsítés, méretezés (leghosszabb oldal = size_m), "
                       "talp z=0-ra, GLB + .blend export → model.glb. Gyors (~5–20 s). Újrafuttatható más paraméterekkel.",
        "input_schema": _schema({
            "size_m": {"type": "number", "minimum": 0.01, "maximum": 3, "description": "a tárgy leghosszabb mérete méterben"},
            "faces": {"type": "integer", "minimum": 5000, "maximum": 300000, "description": "célzott lapszám (alap 50000)"},
            # Z / NEGATIVE_Z are not offered: the importer's forward axis is Z, and forward == up is invalid
            "up_axis": {"type": "string", "enum": ["NEGATIVE_Y", "Y", "X", "NEGATIVE_X"],
                        "description": "melyik tengely a 'fel' az OBJ-ban; alap NEGATIVE_Y (a COLMAP-igazítás után ez a helyes)"},
        }, ["size_m"]),
    },
    {
        "name": "render_preview",
        "description": "4 előnézeti kép renderelése a GLB-ről (elölről, majd 90°-onként körbe), és egy eredeti fotó "
                       "összehasonlításnak. A képeket meg is kapod: nézd meg, áll-e a tárgy, teljes-e, maradt-e rajta háttér.",
        "input_schema": _schema({}),
    },
    {
        "name": "quality_check",
        "description": "Független minőségellenőrző ágens (külön Claude-hívás): az előnézetek és egy eredeti fotó alapján "
                       "ítéletet ad (jo / gyanus / hibas), felsorolja a hibákat, javaslatot tesz, és megírja a modell "
                       "nevét, leírását, címkéit a weboldalhoz. render_preview után hívd; publish_model előtt kötelező.",
        "input_schema": _schema({}),
    },
    {
        "name": "publish_model",
        "description": "A kész GLB feltöltése a weboldalra (web/models + models.json), commit és push. "
                       "Csak akkor hívd, ha az előnézet alapján a modell rendben van. Ha a futás nem engedélyezi "
                       "a közzétételt, a hívás ezt jelzi, és nem tölt fel semmit.",
        "input_schema": _schema({
            "name": {"type": "string", "maxLength": 60, "description": "magyar név, legfeljebb 4 szó"},
            "tags": {"type": "array", "items": {"type": "string", "maxLength": 24}, "maxItems": 6},
            "description": {"type": "string", "maxLength": 400, "description": "1–2 mondat, csak a tárgyról"},
        }, ["name", "tags", "description"]),
    },
    {
        "name": "finish",
        "description": "A futás lezárása. status=ok, ha a modell kész (és ha engedélyezett, feltöltve); "
                       "status=failed, ha a lehetőségek elfogytak – ilyenkor a summary-ban írd le, mit kell másképp fotózni.",
        "input_schema": _schema({
            "status": {"type": "string", "enum": ["ok", "failed"]},
            "summary": {"type": "string", "description": "2–4 mondatos magyar összefoglaló a felhasználónak"},
        }, ["status", "summary"]),
    },
]


# ---------------------------------------------------------------- helpers

class Scan:
    def __init__(self, path: str | Path, allow_publish: bool = False):
        self.dir = Path(path).resolve()
        if not self.dir.is_dir():
            raise SystemExit(f"Nincs ilyen mappa: {self.dir}")
        if ROOT / "data" not in self.dir.parents:
            raise SystemExit(f"A szkennelésnek a data/ alatt kell lennie: {self.dir}")
        self.allow_publish = allow_publish
        self.log = self.dir / "agent_run.log"

    # -- shell
    def run(self, cmd: list[str], timeout: int, cwd: Path = ROOT) -> tuple[int, str, float]:
        t0 = time.time()
        with self.log.open("a") as f:
            f.write(f"\n$ {' '.join(cmd)}   [{time.strftime('%H:%M:%S')}]\n")
            f.flush()
            try:
                p = subprocess.run(cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                   text=True, errors="replace", timeout=timeout)
                out, rc = p.stdout, p.returncode
            except subprocess.TimeoutExpired as e:
                out, rc = (e.stdout or "") if isinstance(e.stdout, str) else "", 124
                out += f"\nTIMEOUT after {timeout} s"
            f.write(out)
        return rc, out, round(time.time() - t0, 1)

    def files(self, sub: str, exts: set[str]) -> list[Path]:
        d = self.dir / sub
        return sorted(p for p in d.rglob("*") if p.suffix.lower() in exts) if d.is_dir() else []


def tail(text: str, n: int = 25) -> str:
    lines = [l for l in text.splitlines() if l.strip()]
    return "\n".join(lines[-n:])


def classify_error(log: str) -> str | None:
    low = log.lower()
    if "out of memory" in low or "cudaerrormemoryallocation" in low:
        return "cuda_oom"
    if "could not register" in low:
        return "registration_failed"
    if "timeout after" in low:
        return "timeout"
    if "no module named" in low:
        return "environment"
    return None


def image_block(path: Path, max_side: int, fmt: str = "PNG", bg: tuple | None = None) -> dict:
    from PIL import Image  # from .venv

    im = Image.open(path)
    im.thumbnail((max_side, max_side))
    if bg is not None and im.mode in ("RGBA", "LA"):
        base = Image.new("RGB", im.size, bg)
        base.paste(im, mask=im.getchannel("A"))
        im = base
    elif im.mode not in ("RGB", "L"):
        im = im.convert("RGB")
    buf = io.BytesIO()
    im.save(buf, fmt, quality=85) if fmt == "JPEG" else im.save(buf, fmt)
    media = "image/jpeg" if fmt == "JPEG" else "image/png"
    return {"type": "image", "source": {"type": "base64", "media_type": media,
                                        "data": base64.standard_b64encode(buf.getvalue()).decode()}}


def _md5(p: Path) -> str:
    return hashlib.md5(p.read_bytes()).hexdigest()


def uses_sample_images(scan: Scan) -> bool:
    """The test set is AGPL: models built from it must never be published."""
    sample = ROOT / "data" / "sample" / "images"
    if not sample.is_dir():
        return False
    known = {_md5(p) for p in sample.iterdir() if p.is_file()}
    return any(_md5(p) in known for p in scan.files("images", IMAGE_EXT)[:200])


# ---------------------------------------------------------------- tool implementations

def scan_info(scan: Scan) -> dict:
    imgs = scan.files("images", IMAGE_EXT)
    size = None
    if imgs:
        from PIL import Image
        with Image.open(imgs[0]) as im:
            size = f"{im.width}×{im.height}"
    return {
        "scan": scan.dir.name,
        "images": len(imgs),
        "image_size": size,
        "videos": len(scan.files("video", VIDEO_EXT)),
        "masked_images": len(scan.files("masked", IMAGE_EXT)),
        "model_obj": (scan.dir / "model" / "model.obj").is_file(),
        "glb": (scan.dir / "model.glb").is_file(),
        "previews": len(list((scan.dir / "preview").glob("view_*.png"))) if (scan.dir / "preview").is_dir() else 0,
        "publish_allowed": scan.allow_publish,
    }


def extract_frames(scan: Scan, count: int) -> dict:
    videos = scan.files("video", VIDEO_EXT)
    if not videos:
        raise ToolError("Nincs videó a video/ mappában.")
    per = -(-count // len(videos))
    total_t = 0.0
    for k, v in enumerate(videos, 1):
        rc, out, t = scan.run([PY, "pipeline/extract_frames.py", str(v), str(scan.dir / "images"),
                               "--count", str(per), "--prefix", f"video{k}"], timeout=1800)
        total_t += t
        if rc:
            raise ToolError(f"extract_frames hiba ({v.name}):\n{tail(out)}")
    return {"ok": True, "images": len(scan.files("images", IMAGE_EXT)), "seconds": total_t}


def mask_background(scan: Scan) -> dict:
    rc, out, t = scan.run([PY, "pipeline/mask.py", str(scan.dir / "images"), str(scan.dir / "masked")], timeout=3600)
    if rc:
        raise ToolError(f"mask hiba:\n{tail(out)}")
    return {"ok": True, "masked_images": len(scan.files("masked", IMAGE_EXT)), "seconds": t}


def remove_mask(scan: Scan) -> dict:
    shutil.rmtree(scan.dir / "masked", ignore_errors=True)
    return {"ok": True}


def _sparse_stats(scan: Scan) -> dict:
    sparse = scan.dir / "work" / "sparse"
    models = sorted(p for p in sparse.iterdir() if p.is_dir()) if sparse.is_dir() else []
    stats = {"sparse_models": len(models), "registered_images": None}
    if models:
        _, out, _ = scan.run([MICROMAMBA, "run", "-n", "scan", "colmap", "model_analyzer",
                              "--path", str(models[0])], timeout=120)
        m = re.search(r"Registered images:\s*(\d+)", out)
        if m:
            stats["registered_images"] = int(m.group(1))
    return stats


def reconstruct(scan: Scan, max_image_size: int) -> dict:
    used = "masked" if scan.files("masked", IMAGE_EXT) else "images"
    total = len(scan.files(used, IMAGE_EXT))
    rc, out, t = scan.run(["./pipeline/reconstruct.sh", str(scan.dir), str(max_image_size)], timeout=3 * 3600)
    res = {"ok": rc == 0, "input": used, "total_images": total, "max_image_size": max_image_size,
           "seconds": t, **_sparse_stats(scan)}
    if rc:
        res["error_category"] = classify_error(out)
        res["log_tail"] = tail(out)
    return res


def cleanup_model(scan: Scan, size_m: float, faces: int = 50000, up_axis: str = "NEGATIVE_Y") -> dict:
    obj = scan.dir / "model" / "model.obj"
    if not obj.is_file():
        raise ToolError("Nincs model/model.obj – előbb reconstruct kell.")
    rc, out, t = scan.run(["./blender/run.sh", "cleanup", str(obj), str(scan.dir / "model.glb"),
                           "--faces", str(faces), "--size", str(size_m), "--up", up_axis, "--blend"], timeout=900)
    if rc:
        raise ToolError(f"Blender cleanup hiba ({classify_error(out)}):\n{tail(out)}")
    glb = scan.dir / "model.glb"
    return {"ok": True, "glb_mb": round(glb.stat().st_size / 1e6, 1), "size_m": size_m, "faces": faces,
            "up_axis": up_axis, "seconds": t, "blender_log": tail(out, 8)}


def render_preview(scan: Scan) -> tuple[dict, list[dict]]:
    glb = scan.dir / "model.glb"
    if not glb.is_file():
        raise ToolError("Nincs model.glb – előbb cleanup_model kell.")
    rc, out, t = scan.run(["./blender/run.sh", "preview", str(glb), str(scan.dir / "preview")], timeout=600)
    if rc:
        raise ToolError(f"Előnézet hiba:\n{tail(out)}")
    views = sorted((scan.dir / "preview").glob("view_*.png"))
    blocks: list[dict] = []
    for v in views:
        blocks.append({"type": "text", "text": f"Előnézet: {v.name}"})
        blocks.append(image_block(v, 512, "PNG", bg=(225, 225, 225)))
    imgs = scan.files("images", IMAGE_EXT)
    if imgs:
        photo = imgs[len(imgs) // 4]
        blocks.append({"type": "text", "text": f"Eredeti fotó összehasonlításnak: {photo.name}"})
        blocks.append(image_block(photo, 768, "JPEG"))
    return {"ok": True, "views": [v.name for v in views], "seconds": t}, blocks


def quality_check(scan: Scan) -> dict:
    from qa import assess  # needs the API key; the controller has loaded it

    try:
        res = assess(scan.dir)
    except RuntimeError as e:
        raise ToolError(str(e))
    (scan.dir / "qa.json").write_text(json.dumps(res, ensure_ascii=False, indent=2))
    return res


def publish_model(scan: Scan, name: str, tags: list[str], description: str) -> dict:
    if not scan.allow_publish:
        return {"ok": False, "published": False,
                "reason": "A közzététel ebben a futásban ki van kapcsolva (--publish nélkül indult). Zárd le a futást."}
    if uses_sample_images(scan):
        return {"ok": False, "published": False,
                "reason": "A képek az AGPL-es tesztkészletből valók – ebből készült modellt tilos közzétenni."}
    glb = scan.dir / "model.glb"
    if not glb.is_file():
        raise ToolError("Nincs model.glb.")
    rc, out, _ = scan.run([PY, "pipeline/publish.py", str(glb), "--name", name, "--tags", *tags,
                           "--description", description], timeout=120)
    if rc:
        raise ToolError(f"publish.py hiba:\n{tail(out)}")
    rc1, out1, _ = scan.run(["git", "add", "--", "web/models"], timeout=60)
    rc2, out2, _ = scan.run(["git", "commit", "-q", "-m", f"Add: {name}", "--", "web/models"], timeout=60)
    if rc1 or rc2:
        raise ToolError(f"git commit hiba:\n{tail(out1 + out2)}")
    rc3, out3, _ = scan.run(["git", "push", "-q"], timeout=180)
    return {"ok": rc3 == 0, "published": True, "committed": True, "pushed": rc3 == 0,
            **({"push_error": tail(out3)} if rc3 else {})}


IMPLS = {
    "scan_info": scan_info,
    "extract_frames": extract_frames,
    "mask_background": mask_background,
    "remove_mask": remove_mask,
    "reconstruct": reconstruct,
    "cleanup_model": cleanup_model,
    "render_preview": render_preview,
    "quality_check": quality_check,
    "publish_model": publish_model,
}


def execute(scan: Scan, name: str, args: dict) -> tuple[dict, list[dict]]:
    """Run one tool → (result dict, extra content blocks such as images)."""
    fn = IMPLS.get(name)
    if fn is None:
        raise ToolError(f"Ismeretlen eszköz: {name}")
    out = fn(scan, **args)
    return out if isinstance(out, tuple) else (out, [])


if __name__ == "__main__":
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    s = Scan(sys.argv[1], allow_publish=False)
    result, extra = execute(s, sys.argv[2], json.loads(sys.argv[3]) if len(sys.argv) > 3 else {})
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if extra:
        print(f"(+{sum(b['type'] == 'image' for b in extra)} kép)")

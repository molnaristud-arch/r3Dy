"""Headless Blender cleanup: import a scan, tidy it, export GLB.

Usage:
  blender -b -P blender/cleanup.py -- <in.ply|in.obj|in.glb> <out.glb> [--faces 50000] [--size 0.2]

--faces  target face count (decimate); 0 = keep
--size   scale so the longest dimension is this many metres; 0 = keep
         (COLMAP output has arbitrary scale unless a known-size marker was used)
"""
import argparse
import sys
from pathlib import Path

import bpy
from mathutils import Vector


def parse_args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("dst")
    ap.add_argument("--faces", type=int, default=50000)
    ap.add_argument("--size", type=float, default=0.2)
    ap.add_argument("--blend", action="store_true", help="also save a .blend next to the GLB")
    ap.add_argument("--up", default="NEGATIVE_Y",
                    help="up axis of an OBJ/PLY input; reconstruct.sh levels the scan so that "
                         "gravity points along +Y (COLMAP camera convention), hence -Y is up")
    return ap.parse_args(argv)


def import_mesh(path: Path, up: str):
    ext = path.suffix.lower()
    if ext == ".ply":
        bpy.ops.wm.ply_import(filepath=str(path), forward_axis="Z", up_axis=up)
    elif ext == ".obj":
        bpy.ops.wm.obj_import(filepath=str(path), forward_axis="Z", up_axis=up)
    elif ext in {".glb", ".gltf"}:
        bpy.ops.import_scene.gltf(filepath=str(path))
    else:
        raise SystemExit(f"Unsupported input: {ext}")
    meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    if not meshes:
        raise SystemExit("No mesh imported")
    bpy.ops.object.select_all(action="DESELECT")
    for o in meshes:
        o.select_set(True)
    bpy.context.view_layer.objects.active = meshes[0]
    if len(meshes) > 1:
        bpy.ops.object.join()
    return bpy.context.view_layer.objects.active


def keep_largest_part(obj):
    """Poisson meshes come with floating debris; keep the biggest connected piece."""
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="DESELECT")
    bpy.ops.mesh.separate(type="LOOSE")
    bpy.ops.object.mode_set(mode="OBJECT")
    parts = [o for o in bpy.context.selected_objects if o.type == "MESH"]
    biggest = max(parts, key=lambda o: len(o.data.polygons))
    for o in parts:
        if o is not biggest:
            bpy.data.objects.remove(o, do_unlink=True)
    return biggest


def main():
    args = parse_args()
    bpy.ops.wm.read_factory_settings(use_empty=True)
    obj = keep_largest_part(import_mesh(Path(args.src), args.up))
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)

    if args.faces and len(obj.data.polygons) > args.faces:
        mod = obj.modifiers.new("decimate", "DECIMATE")
        mod.ratio = args.faces / len(obj.data.polygons)
        bpy.ops.object.modifier_apply(modifier=mod.name)

    # Origin at the bottom centre, object standing on the ground plane at (0,0,0).
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    corners = [obj.matrix_world @ Vector(c) for c in obj.bound_box]
    lo = Vector(min(c[i] for c in corners) for i in range(3))
    hi = Vector(max(c[i] for c in corners) for i in range(3))
    if args.size:
        s = args.size / max(hi - lo)
        obj.scale = (s, s, s)
        bpy.ops.object.transform_apply(scale=True)
        lo, hi = lo * s, hi * s
    obj.location = Vector(((lo.x + hi.x) / -2, (lo.y + hi.y) / -2, -lo.z))
    bpy.ops.object.transform_apply(location=True)
    bpy.ops.object.shade_smooth()

    dst = Path(args.dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.export_scene.gltf(filepath=str(dst), export_format="GLB", use_selection=True)
    if args.blend:
        bpy.ops.wm.save_as_mainfile(filepath=str(dst.with_suffix(".blend")))
    print(f"→ {dst} ({len(obj.data.polygons)} faces)")


main()

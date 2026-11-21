"""Render preview images of a GLB from several angles (thumbnail + AI quality check).

Usage: ./blender/run.sh preview <model.glb> <out_dir> [--views 4] [--size 800]
Writes <out_dir>/view_0.png … view_N.png (3/4 view from above, evenly around the object).
"""
import argparse
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("out_dir")
    ap.add_argument("--views", type=int, default=4)
    ap.add_argument("--size", type=int, default=800)
    args = ap.parse_args(argv)

    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=args.src)
    meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    corners = [o.matrix_world @ Vector(c) for o in meshes for c in o.bound_box]
    lo = Vector(min(c[i] for c in corners) for i in range(3))
    hi = Vector(max(c[i] for c in corners) for i in range(3))
    centre, radius = (lo + hi) / 2, (hi - lo).length / 2

    sc = bpy.context.scene
    sc.render.engine = "BLENDER_WORKBENCH"
    sc.display.shading.color_type = "TEXTURE"
    sc.display.shading.light = "STUDIO"
    sc.render.film_transparent = True
    sc.render.resolution_x = sc.render.resolution_y = args.size
    cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
    cam.data.lens = 50
    sc.collection.objects.link(cam)
    sc.camera = cam

    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    dist = radius * 2.4
    for i in range(args.views):
        a = 2 * math.pi * i / args.views - math.pi / 2  # view_0 looks from -Y (the "front")
        cam.location = centre + Vector((math.cos(a) * dist, math.sin(a) * dist, dist * 0.45))
        cam.rotation_euler = (centre - cam.location).to_track_quat("-Z", "Y").to_euler()
        sc.render.filepath = str(out / f"view_{i}.png")
        bpy.ops.render.render(write_still=True)
    print(f"→ {out}/view_0..{args.views - 1}.png")


main()

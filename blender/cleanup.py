"""Headless Blender cleanup: import a scan, tidy it, export GLB.

Usage:
  blender -b -P blender/cleanup.py -- <in.ply|in.obj|in.glb> <out.glb> [--faces 50000] [--size 0.2]

--faces  target face count (decimate); 0 = keep
--size   scale so the longest dimension is this many metres; 0 = keep
         (COLMAP output has arbitrary scale unless a known-size marker was used)
"""
import argparse
import json
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
    ap.add_argument("--remove-disc", action="store_true",
                    help="turntable scan: level on the printed disc, scale from its diameter, cut it off")
    ap.add_argument("--disc-diameter", type=float, default=0.19, help="printed disc diameter in metres")
    ap.add_argument("--cut-mm", type=float, default=1.0, help="also delete this much above the disc plane")
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


def delete_verts(obj, mask):
    """Delete the vertices where mask is True with one edit-mode delete (no Python object per vertex)."""
    if not mask.any():
        return
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_mode(type="VERT")
    bpy.ops.mesh.select_all(action="DESELECT")
    bpy.ops.object.mode_set(mode="OBJECT")
    obj.data.vertices.foreach_set("select", mask.astype(bool))
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.delete(type="VERT")
    bpy.ops.object.mode_set(mode="OBJECT")


def keep_largest_part(obj):
    """Poisson meshes come with floating debris; keep the biggest connected piece.

    Connected components via scipy instead of separate(LOOSE): after the disc is cut off there can be
    thousands of islands, and one Blender object per island ran the machine out of memory (OOM, 12 GB).
    """
    import numpy as np
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components

    me = obj.data
    nv, ne = len(me.vertices), len(me.edges)
    e = np.empty(ne * 2, dtype=np.int32)
    me.edges.foreach_get("vertices", e)
    e = e.reshape(-1, 2)
    graph = coo_matrix((np.ones(ne, dtype=np.int8), (e[:, 0], e[:, 1])), shape=(nv, nv))
    count, labels = connected_components(graph, directed=False)
    if count > 1:
        delete_verts(obj, labels != np.bincount(labels).argmax())
    print(f"parts: {count}, kept {len(me.vertices)}/{nv} vertices")
    return obj


def remove_disc(obj, disc_diameter: float, cut: float):
    """Find the turntable disc (the dominant plane), level the scan on it, scale it from the disc's
    known diameter, and delete the disc and everything below / outside it.

    Returns a dict for the log. Raises RuntimeError when no convincing plane is found.
    """
    import numpy as np
    from mathutils import Matrix

    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    me = obj.data
    n = len(me.vertices)
    co = np.empty(n * 3, dtype=np.float64)
    me.vertices.foreach_get("co", co)
    pts = co.reshape(-1, 3)
    rng = np.random.default_rng(0)
    sample = pts[rng.choice(n, size=min(n, 150_000), replace=False)]
    diag = float(np.linalg.norm(sample.max(0) - sample.min(0)))
    thr = 0.004 * diag

    # RANSAC: the plane supported by the most points is the disc
    best_count, best = 0, None
    for _ in range(500):
        a, b, c = sample[rng.choice(len(sample), 3, replace=False)]
        nrm = np.cross(b - a, c - a)
        ln = np.linalg.norm(nrm)
        if ln < 1e-12:
            continue
        nrm /= ln
        count = int((np.abs((sample - a) @ nrm) < thr).sum())
        if count > best_count:
            best_count, best = count, (a, nrm)
    if best is None or best_count < 0.08 * len(sample):
        raise RuntimeError(f"no dominant plane found (best support {best_count}/{len(sample)})")
    a, nrm = best
    inl = sample[np.abs((sample - a) @ nrm) < thr]
    centroid = inl.mean(0)
    d = inl - centroid
    nrm = np.linalg.eigh(d.T @ d)[1][:, 0]  # least-squares refinement (3x3; a full SVD of d would be N x N)
    dist = (sample - centroid) @ nrm
    if (dist > 3 * thr).sum() < (dist < -3 * thr).sum():  # normal must point towards the object
        nrm = -nrm
    sigma = float(np.std((inl - centroid) @ nrm))

    # rotate the normal onto +Z, disc plane to z = 0
    z = np.array([0.0, 0.0, 1.0])
    v, c = np.cross(nrm, z), float(nrm @ z)
    vx = np.array([[0, -v[2], v[1]], [v[2], 0, -v[0]], [-v[1], v[0], 0]])
    rot = np.eye(3) + vx + vx @ vx / (1 + c) if c > -0.999 else np.diag([1.0, -1.0, -1.0])
    tilt = float(np.degrees(np.arccos(np.clip(c, -1, 1))))
    inl_r = (inl - centroid) @ rot.T
    center_xy = np.median(inl_r[:, :2], axis=0)
    radius = float(np.percentile(np.linalg.norm(inl_r[:, :2] - center_xy, axis=1), 98))
    s = disc_diameter / (2 * radius)

    m = np.eye(4)
    m[:3, :3] = s * rot
    m[:3, 3] = -s * (rot @ centroid) - s * np.array([center_xy[0], center_xy[1], 0.0])
    obj.matrix_world = Matrix(m.tolist())
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

    cut = max(cut, 3 * sigma * s)
    r_keep = disc_diameter / 2 * 1.02
    me.vertices.foreach_get("co", co)
    p = co.reshape(-1, 3)
    delete_verts(obj, (p[:, 2] < cut) | (p[:, 0] ** 2 + p[:, 1] ** 2 > r_keep ** 2))
    left = len(me.vertices)
    if left < 100:
        raise RuntimeError(f"nothing left above the disc (cut {cut * 1000:.1f} mm)")
    return {"tilt_corrected_deg": round(tilt, 1), "disc_support": round(best_count / len(sample), 2),
            "plane_noise_mm": round(sigma * s * 1000, 2), "cut_mm": round(cut * 1000, 1),
            "scale_from_disc": True}


def main():
    args = parse_args()
    bpy.ops.wm.read_factory_settings(use_empty=True)
    obj = import_mesh(Path(args.src), args.up)
    disc = None
    if args.remove_disc:
        try:
            disc = remove_disc(obj, args.disc_diameter, args.cut_mm / 1000)
            args.size = 0  # true scale already comes from the disc
        except RuntimeError as e:
            print(f"DISC: {json.dumps({'error': str(e)})}")
            sys.exit(3)
    obj = keep_largest_part(obj)
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
    if disc is not None:
        disc["object_size_cm"] = [round((hi[i] - lo[i]) * 100, 1) for i in range(3)]
        print(f"DISC: {json.dumps(disc)}")

    dst = Path(args.dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.export_scene.gltf(filepath=str(dst), export_format="GLB", use_selection=True)
    if args.blend:
        bpy.ops.wm.save_as_mainfile(filepath=str(dst.with_suffix(".blend")))
    print(f"→ {dst} ({len(obj.data.polygons)} faces)")


main()

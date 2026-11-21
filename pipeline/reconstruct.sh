#!/usr/bin/env bash
# Photogrammetry: COLMAP (camera poses, GPU SIFT) → OpenMVS (dense cloud, mesh, texture).
#   <scan_dir>/images (or <scan_dir>/masked)  →  <scan_dir>/model/model.obj (+ .mtl, texture .png)
#
# Usage: ./pipeline/reconstruct.sh <scan_dir> [max_image_size]
# Needs the micromamba env "scan" (colmap + openmvs, CUDA builds); see README.
set -euo pipefail

scan="$(realpath "${1:?usage: reconstruct.sh <scan_dir> [max_image_size]}")"
max_size="${2:-2000}"   # 6 GB VRAM: stay around 2000

export MAMBA_ROOT_PREFIX="${MAMBA_ROOT_PREFIX:-$HOME/.local/share/micromamba}"
run() { "${MICROMAMBA:-$HOME/.local/bin/micromamba}" run -n scan "$@"; }
step() { printf '\n== %s  [%(%H:%M:%S)T]\n' "$1" -1; }

images="$scan/images"
[[ -d "$scan/masked" ]] && images="$scan/masked"
work="$scan/work"
rm -rf "$work"
mkdir -p "$work/sparse" "$scan/model"
start=$SECONDS

step "1/7 feature extraction"
run colmap feature_extractor \
  --database_path "$work/db.db" --image_path "$images" \
  --ImageReader.single_camera 1 --FeatureExtraction.max_image_size "$max_size"

step "2/7 matching"
run colmap exhaustive_matcher --database_path "$work/db.db"

step "3/7 sparse reconstruction (camera poses)"
run colmap mapper --database_path "$work/db.db" --image_path "$images" --output_path "$work/sparse"
[[ -d "$work/sparse/0" ]] || { echo "COLMAP could not register the images (too little overlap/texture?)" >&2; exit 1; }
# COLMAP's frame is arbitrary; level it using the photos' own "up" (phone held upright).
mkdir -p "$work/aligned"
run colmap model_orientation_aligner --image_path "$images" --input_path "$work/sparse/0" \
  --output_path "$work/aligned" --method IMAGE-ORIENTATION

step "4/7 undistort"
run colmap image_undistorter --image_path "$images" --input_path "$work/aligned" \
  --output_path "$work/dense" --output_type COLMAP --max_image_size "$max_size"

step "5/7 dense point cloud (OpenMVS)"
cd "$work/dense"
run InterfaceCOLMAP -i . -o scene.mvs --image-folder images
run DensifyPointCloud scene.mvs --resolution-level 1 --max-resolution "$max_size"

step "6/7 mesh"
run ReconstructMesh scene_dense.mvs

step "7/7 texture"
# Seam leveling stays off: with it on, OpenMVS 2.4 painted dark blotches all over the atlas (tested).
run TextureMesh scene_dense.mvs --mesh-file scene_dense_mesh.ply --export-type obj --max-texture-size 4096 \
  --global-seam-leveling 0 --local-seam-leveling 0 -o "$scan/model/model.mvs"

[[ -f "$scan/model/model.obj" ]] || { echo "Texturing produced no $scan/model/model.obj" >&2; exit 1; }
echo
echo "→ $scan/model/model.obj   ($(( (SECONDS - start) / 60 )) min $(( (SECONDS - start) % 60 )) s)"

#!/usr/bin/env bash
# Run one of the Blender scripts headless.
#
#   ./blender/run.sh cleanup <in.obj|in.ply|in.glb> <out.glb> [--faces N] [--size M] [--blend] [--up AXIS]
#   ./blender/run.sh preview <model.glb> <out_dir> [--views 4] [--size 800]
#
# Ubuntu's Blender runs on the system Python, which has no numpy (the glTF
# exporter needs it). The project .venv is the same Python version (3.14), so
# its site-packages go on PYTHONPATH; Blender only honours PYTHONPATH with
# --python-use-system-env. Alternative: sudo apt install python3-numpy
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
script="$root/blender/${1:?usage: run.sh cleanup|preview <args>}.py"
shift
[[ -f "$script" ]] || { echo "No such script: $script" >&2; exit 1; }
site="$(echo "$root"/.venv/lib/python3.*/site-packages)"
[[ -d "$site" ]] || { echo "Missing $root/.venv — run ./setup.sh first" >&2; exit 1; }
# Memory cap (BLENDER_MEM, default 6G): if Blender overruns it, only Blender is killed – not the
# terminal / editor it was started from (a global OOM once took the whole session down).
cap=()
if command -v systemd-run >/dev/null && systemd-run --user --scope -q -p MemoryMax=1G true 2>/dev/null; then
  cap=(systemd-run --user --scope -q -p "MemoryMax=${BLENDER_MEM:-6G}" -p MemorySwapMax=0)
fi
PYTHONPATH="$site${PYTHONPATH:+:$PYTHONPATH}" exec "${cap[@]}" blender -b --factory-startup --python-use-system-env --python-exit-code 1 -P "$script" -- "$@"

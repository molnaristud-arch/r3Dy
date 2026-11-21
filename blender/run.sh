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
PYTHONPATH="$site${PYTHONPATH:+:$PYTHONPATH}" exec blender -b --factory-startup --python-use-system-env --python-exit-code 1 -P "$script" -- "$@"

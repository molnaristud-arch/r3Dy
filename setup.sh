#!/usr/bin/env bash
# One-time setup, idempotent. Checks the system tools and builds the two environments:
#   - micromamba env "scan": COLMAP + OpenMVS (CUDA builds from conda-forge)
#   - .venv: Python tools (OpenCV, rembg) – also lends numpy to Ubuntu's Blender
set -euo pipefail
cd "$(dirname "$0")"

ok=1
for c in ffmpeg blender python3; do
  command -v "$c" >/dev/null || { echo "MISSING: $c  →  sudo apt install -y ffmpeg blender"; ok=0; }
done
mm="${MICROMAMBA:-$HOME/.local/bin/micromamba}"
if [[ ! -x "$mm" ]]; then
  echo "MISSING: micromamba  →  curl -sSfL https://micro.mamba.pm/api/micromamba/linux-64/latest | tar -xj -C ~/.local bin/micromamba"
  ok=0
fi
[[ $ok == 1 ]] || exit 1

export MAMBA_ROOT_PREFIX="${MAMBA_ROOT_PREFIX:-$HOME/.local/share/micromamba}"
if ! "$mm" env list | grep -qE '^\s*scan\s'; then
  "$mm" create -y -n scan -c conda-forge "colmap=*=cuda*" "openmvs=*=cuda*"
fi

if [[ ! -x .venv/bin/python ]]; then
  python3 -m venv .venv
fi
.venv/bin/pip install -q -r pipeline/requirements.txt
mkdir -p data/bejovo   # auto.sh watches it; a fresh clone has only data/sample

echo
"$mm" run -n scan colmap -h 2>&1 | head -1
(cd "${TMPDIR:-/tmp}" && "$mm" run -n scan DensifyPointCloud --help 2>&1 | grep -m1 OpenMVS; rm -f DensifyPointCloud-*.log) || true   # OpenMVS writes a log into the cwd
blender --version | head -1
.venv/bin/python -c "import cv2, onnxruntime as o; print('opencv', cv2.__version__, '| onnxruntime', o.get_available_providers()[:2])"
echo "setup ok"

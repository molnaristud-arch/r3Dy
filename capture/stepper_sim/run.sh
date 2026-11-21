#!/usr/bin/env bash
# Compile turntable_stepper.ino on the PC against a tiny Arduino stub and simulate it:
# stop positions in STEP mode, exact RPM in CONT mode, serial commands, the button.
set -euo pipefail
cd "$(dirname "$0")"
tmp=$(mktemp -d); trap 'rm -rf "$tmp"' EXIT
cp ../turntable_stepper/turntable_stepper.ino "$tmp/sketch.inc"
g++ -std=c++17 -Wall -include vector -include algorithm -I. -I"$tmp" -o "$tmp/sim" test.cpp
"$tmp/sim"

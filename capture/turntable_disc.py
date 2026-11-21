#!/usr/bin/env python3
"""Printable turntable disc (SVG): degree ring + high-contrast random pattern.

The ring tells you where to stop when rotating by hand (default every 10°, a
long tick + number every 30°). The pattern in the middle rotates with the object
and gives COLMAP plenty of features to lock on to - a plain white disc does not.
The scale bar (exactly 5 cm when printed at 100 %) lets you fix the model's real size.

Usage: python capture/turntable_disc.py capture/disc.svg --diameter 190 --step 10
       Print at 100 % ("actual size"); A4 fits up to 190 mm, A3 up to 280 mm.
"""
import argparse
import math
import random


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("out")
    ap.add_argument("--diameter", type=float, default=190, help="mm")
    ap.add_argument("--step", type=int, default=10, help="degrees between stops")
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()

    d = args.diameter
    r = d / 2
    c = r + 5  # 5 mm page margin
    rnd = random.Random(args.seed)
    el = []

    el.append(f'<circle cx="{c}" cy="{c}" r="{r}" fill="#fff" stroke="#000" stroke-width="0.6"/>')
    # Degree ticks + labels
    for deg in range(0, 360, args.step):
        a = math.radians(deg - 90)
        major = deg % 30 == 0
        r1 = r - (9 if major else 5)
        x0, y0 = c + r * math.cos(a), c + r * math.sin(a)
        x1, y1 = c + r1 * math.cos(a), c + r1 * math.sin(a)
        el.append(f'<line x1="{x0:.2f}" y1="{y0:.2f}" x2="{x1:.2f}" y2="{y1:.2f}" '
                  f'stroke="#000" stroke-width="{1.2 if major else 0.6}"/>')
        if major:
            xt, yt = c + (r - 14) * math.cos(a), c + (r - 14) * math.sin(a)
            el.append(f'<text x="{xt:.2f}" y="{yt:.2f}" font-size="4.5" font-family="sans-serif" '
                      f'text-anchor="middle" dominant-baseline="central">{deg}</text>')
    # Random pattern inside the ring (blobs of varying size and grey level)
    inner = r - 20
    for _ in range(int(inner * inner / 6)):
        rr = inner * math.sqrt(rnd.random())
        a = rnd.random() * 2 * math.pi
        x, y = c + rr * math.cos(a), c + rr * math.sin(a)
        size = rnd.uniform(0.8, 3.5)
        g = rnd.choice(["#000", "#000", "#444", "#888"])
        if rnd.random() < 0.5:
            el.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="{size:.2f}" fill="{g}"/>')
        else:
            el.append(f'<rect x="{x:.2f}" y="{y:.2f}" width="{size * 1.6:.2f}" height="{size:.2f}" fill="{g}" '
                      f'transform="rotate({rnd.uniform(0, 180):.0f} {x:.2f} {y:.2f})"/>')
    # Clear centre spot for the object + 5 cm scale bar below the disc
    el.append(f'<circle cx="{c}" cy="{c}" r="{min(30, inner / 3):.1f}" fill="#fff" stroke="#000" '
              f'stroke-width="0.3" stroke-dasharray="2 2"/>')
    yb = 2 * c + 6
    el.append(f'<rect x="{c - 25}" y="{yb}" width="50" height="3" fill="#000"/>')
    el.append(f'<text x="{c}" y="{yb + 8}" font-size="4" font-family="sans-serif" text-anchor="middle">'
              f'5 cm – 100 %-os méretben nyomtasd</text>')

    w, h = 2 * c, 2 * c + 16
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}mm" height="{h}mm" viewBox="0 0 {w} {h}">'
           + "".join(el) + "</svg>\n")
    with open(args.out, "w") as f:
        f.write(svg)
    print(f"→ {args.out} ({d:.0f} mm, {360 // args.step} stops of {args.step}°)")


if __name__ == "__main__":
    main()

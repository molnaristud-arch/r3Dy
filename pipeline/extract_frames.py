#!/usr/bin/env python3
"""Pick the sharpest, evenly spaced frames from a turntable video.

The video is split into `count` equal time windows; from each window the frame
with the highest Laplacian variance (a standard sharpness measure) is kept.
This gives even angular coverage while skipping motion-blurred frames.
"""
import argparse
from pathlib import Path

import cv2


def sharpness(frame) -> float:
    # Measured at half resolution: ~4x faster on 4K and ranks frames the same way.
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    gray = cv2.resize(gray, None, fx=0.5, fy=0.5, interpolation=cv2.INTER_AREA)
    return cv2.Laplacian(gray, cv2.CV_64F).var()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("video")
    ap.add_argument("out_dir")
    ap.add_argument("--count", type=int, default=150, help="frames to keep")
    ap.add_argument("--prefix", default="frame", help="output file name prefix (keeps several videos apart)")
    ap.add_argument("--max-side", type=int, default=2400,
                    help="downscale so the longer side is at most this (0 = keep)")
    args = ap.parse_args()

    cap = cv2.VideoCapture(args.video)
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    if total <= 0:
        raise SystemExit(f"Cannot read video: {args.video}")
    count = min(args.count, total)
    window = total / count

    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)

    def save(w, frame):
        h, wd = frame.shape[:2]
        if args.max_side and max(h, wd) > args.max_side:
            s = args.max_side / max(h, wd)
            frame = cv2.resize(frame, (round(wd * s), round(h * s)), interpolation=cv2.INTER_AREA)
        cv2.imwrite(str(out / f"{args.prefix}_{w:04d}.jpg"), frame, [cv2.IMWRITE_JPEG_QUALITY, 95])

    # Windows come in order, so only the current window's best frame is kept in memory
    # (holding all of them took ~4 GB for 150 frames of 4K video).
    cur, best_score, best_frame, saved, idx = 0, -1.0, None, 0, 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        w = min(int(idx / window), count - 1)
        if w != cur and best_frame is not None:
            save(cur, best_frame)
            saved += 1
            best_score, best_frame = -1.0, None
        cur = w
        score = sharpness(frame)
        if score > best_score:
            best_score, best_frame = score, frame
        idx += 1
    cap.release()
    if best_frame is not None:
        save(cur, best_frame)
        saved += 1

    print(f"{saved} frames from {idx} → {out}")


if __name__ == "__main__":
    main()

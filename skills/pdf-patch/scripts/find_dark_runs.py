#!/usr/bin/env python3
"""Find dark-pixel runs in a rendered PDF crop to locate characters."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from PIL import Image


def parse_box(value: str) -> tuple[int, int, int, int]:
    parts = [int(part.strip()) for part in value.split(",")]
    if len(parts) != 4:
        raise argparse.ArgumentTypeError("box must be x0,y0,x1,y1")
    return tuple(parts)


def grouped(values: list[int], max_gap: int, min_width: int) -> list[tuple[int, int]]:
    if not values:
        return []
    runs = []
    start = prev = values[0]
    for value in values[1:]:
        if value <= prev + max_gap:
            prev = value
        else:
            if prev - start + 1 >= min_width:
                runs.append((start, prev))
            start = prev = value
    if prev - start + 1 >= min_width:
        runs.append((start, prev))
    return runs


def main() -> int:
    parser = argparse.ArgumentParser(description="Find dark-pixel horizontal and vertical runs in an image crop.")
    parser.add_argument("--image", required=True, type=Path)
    parser.add_argument("--box", required=True, type=parse_box, help="Crop box in image pixels: x0,y0,x1,y1.")
    parser.add_argument("--threshold", type=int, default=180)
    parser.add_argument("--min-count", type=int, default=2)
    parser.add_argument("--max-gap", type=int, default=2)
    parser.add_argument("--min-width", type=int, default=2)
    args = parser.parse_args()

    image = Image.open(args.image).convert("L")
    x0, y0, x1, y1 = args.box
    crop = image.crop(args.box)
    arr = np.asarray(crop)
    dark = arr < args.threshold

    cols = [x0 + x for x in range(dark.shape[1]) if int(dark[:, x].sum()) >= args.min_count]
    rows = [y0 + y for y in range(dark.shape[0]) if int(dark[y, :].sum()) >= args.min_count]
    col_runs = grouped(cols, args.max_gap, args.min_width)
    row_runs = grouped(rows, args.max_gap, args.min_width)

    print("column_runs", col_runs)
    print("row_runs", row_runs)
    for left, right in col_runs:
        sub = dark[:, left - x0 : right - x0 + 1]
        ys, xs = np.where(sub)
        if len(xs) == 0:
            continue
        print("run_box", (left, y0 + int(ys.min()), right, y0 + int(ys.max())))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

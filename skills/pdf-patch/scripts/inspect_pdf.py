#!/usr/bin/env python3
"""Inspect and render a PDF before patching."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import fitz


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect PDF text layer, images, and optional renders.")
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--page", type=int, default=None, help="1-based page number to render or inspect in detail.")
    parser.add_argument("--scale", type=float, default=2.0)
    parser.add_argument("--render", type=Path, default=None, help="Optional output PNG for the selected page.")
    parser.add_argument("--crop", default=None, help="Optional crop x0,y0,x1,y1 in rendered pixels.")
    parser.add_argument("--crop-out", type=Path, default=None, help="Optional crop PNG output.")
    parser.add_argument("--text-out", type=Path, default=None, help="Optional extracted text output.")
    args = parser.parse_args()

    doc = fitz.open(args.input)
    pages = []
    for i, page in enumerate(doc):
        text = page.get_text()
        images = page.get_images(full=True)
        pages.append(
            {
                "page": i + 1,
                "rect": [round(v, 2) for v in page.rect],
                "text_length": len(text),
                "image_count": len(images),
                "first_text": text[:120],
            }
        )

    print(json.dumps({"file": str(args.input), "page_count": doc.page_count, "pages": pages}, ensure_ascii=False, indent=2))

    if args.text_out:
        args.text_out.write_text("\n\n".join(doc[i].get_text() for i in range(doc.page_count)), encoding="utf-8")

    if args.page is not None:
        page = doc[args.page - 1]
        pix = page.get_pixmap(matrix=fitz.Matrix(args.scale, args.scale), alpha=False)
        if args.render:
            pix.save(args.render)
            print(str(args.render.resolve()))
        if args.crop_out:
            if not args.crop:
                raise ValueError("--crop is required with --crop-out")
            from PIL import Image

            x0, y0, x1, y1 = [int(x.strip()) for x in args.crop.split(",")]
            image = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
            image.crop((x0, y0, x1, y1)).save(args.crop_out)
            print(str(args.crop_out.resolve()))

    doc.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

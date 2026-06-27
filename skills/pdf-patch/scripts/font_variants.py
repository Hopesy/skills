#!/usr/bin/env python3
"""Generate replacement glyph/font variants on the real target crop."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont


def parse_box(value: str) -> tuple[int, int, int, int]:
    parts = [int(part.strip()) for part in value.split(",")]
    if len(parts) != 4:
        raise argparse.ArgumentTypeError("box must be x0,y0,x1,y1")
    return tuple(parts)


def parse_point(value: str) -> tuple[int, int]:
    parts = [int(part.strip()) for part in value.split(",")]
    if len(parts) != 2:
        raise argparse.ArgumentTypeError("point must be x,y")
    return tuple(parts)


def parse_rgba(value: str) -> tuple[int, int, int, int]:
    parts = [int(part.strip()) for part in value.split(",")]
    if len(parts) != 4:
        raise argparse.ArgumentTypeError("rgba must be r,g,b,a")
    return tuple(parts)


def local_patch(image: Image.Image, cover: tuple[int, int, int, int], noise_sigma: float = 1.5) -> Image.Image:
    x0, y0, x1, y1 = cover
    region = image.crop((max(0, x0 - 25), max(0, y0 - 25), min(image.width, x1 + 25), min(image.height, y1 + 25)))
    arr = np.asarray(region.convert("RGB"))
    light = arr[(arr[:, :, 0] > 235) & (arr[:, :, 1] > 235) & (arr[:, :, 2] > 235)]
    base = np.array([253, 254, 254], dtype=np.uint8) if len(light) == 0 else np.median(light, axis=0).astype(np.uint8)
    rng = np.random.default_rng(1234)
    width, height = x1 - x0, y1 - y0
    noise = rng.normal(0, noise_sigma, (height, width, 1))
    return Image.fromarray(np.clip(base.reshape(1, 1, 3) + noise, 0, 255).astype(np.uint8), "RGB")


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a contact sheet of font/size variants for a PDF patch.")
    parser.add_argument("--image", required=True, type=Path, help="Rendered original page image.")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--preview-crop", required=True, type=parse_box, help="Output preview crop x0,y0,x1,y1.")
    parser.add_argument("--cover", required=True, type=parse_box, help="Patch rectangle x0,y0,x1,y1.")
    parser.add_argument("--text", required=True)
    parser.add_argument("--position", required=True, type=parse_point)
    parser.add_argument("--fonts", nargs="+", required=True, help="Font files to test.")
    parser.add_argument("--sizes", nargs="+", type=int, required=True)
    parser.add_argument("--fill", default="22,25,30,250", type=parse_rgba)
    parser.add_argument("--blur", type=float, default=0.16)
    args = parser.parse_args()

    base_image = Image.open(args.image).convert("RGB")
    rows = []
    label_font = ImageFont.truetype(r"C:\Windows\Fonts\msyh.ttc", 16) if Path(r"C:\Windows\Fonts\msyh.ttc").exists() else None

    for font_path in args.fonts:
        font_file = Path(font_path)
        if not font_file.exists():
            continue
        for size in args.sizes:
            image = base_image.copy()
            image.paste(local_patch(image, args.cover), args.cover)
            layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
            draw = ImageDraw.Draw(layer)
            font = ImageFont.truetype(str(font_file), size)
            draw.text(args.position, args.text, font=font, fill=args.fill)
            if args.blur > 0:
                layer = layer.filter(ImageFilter.GaussianBlur(args.blur))
            image = Image.alpha_composite(image.convert("RGBA"), layer).convert("RGB")
            crop = image.crop(args.preview_crop)
            label = Image.new("RGB", (220, crop.height), (255, 255, 255))
            label_draw = ImageDraw.Draw(label)
            label_draw.text((8, max(4, crop.height // 2 - 10)), f"{font_file.name} {size}", font=label_font, fill=(0, 0, 0))
            row = Image.new("RGB", (label.width + crop.width, crop.height), (255, 255, 255))
            row.paste(label, (0, 0))
            row.paste(crop, (label.width, 0))
            rows.append(row)

    if not rows:
        raise ValueError("no variants generated")
    sheet = Image.new("RGB", (max(row.width for row in rows), sum(row.height for row in rows)), (255, 255, 255))
    y = 0
    for row in rows:
        sheet.paste(row, (0, y))
        y += row.height
    sheet.save(args.output)
    print(str(args.output.resolve()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Repair short text in a scanned/image-only PDF page.

Coordinates are in rendered image pixels at the chosen scale, not PDF points.
The script rebuilds the target page from the original render. By default it
preserves the other pages from the source PDF.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

import fitz  # PyMuPDF
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont


def parse_int_tuple(value: str, expected: int, name: str) -> tuple[int, ...]:
    parts = [part.strip() for part in value.split(",")]
    if len(parts) != expected:
        raise argparse.ArgumentTypeError(f"{name} must contain {expected} comma-separated integers")
    try:
        return tuple(int(part) for part in parts)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"{name} must contain integers") from exc


def parse_float_tuple(value: str, expected: int, name: str) -> tuple[float, ...]:
    parts = [part.strip() for part in value.split(",")]
    if len(parts) != expected:
        raise argparse.ArgumentTypeError(f"{name} must contain {expected} comma-separated numbers")
    try:
        return tuple(float(part) for part in parts)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"{name} must contain numbers") from exc


def local_paper_patch(image: Image.Image, cover: tuple[int, int, int, int], seed: int, noise_sigma: float) -> Image.Image:
    x0, y0, x1, y1 = cover
    sample_margin = 25
    sx0 = max(0, x0 - sample_margin)
    sy0 = max(0, y0 - sample_margin)
    sx1 = min(image.width, x1 + sample_margin)
    sy1 = min(image.height, y1 + sample_margin)
    region = image.crop((sx0, sy0, sx1, sy1)).convert("RGB")
    arr = np.asarray(region)
    light = arr[(arr[:, :, 0] > 235) & (arr[:, :, 1] > 235) & (arr[:, :, 2] > 235)]
    base = np.array([253, 254, 254], dtype=np.uint8) if len(light) == 0 else np.median(light, axis=0).astype(np.uint8)
    width = x1 - x0
    height = y1 - y0
    rng = np.random.default_rng(seed)
    noise = rng.normal(0, noise_sigma, (height, width, 1))
    patch = np.clip(base.reshape(1, 1, 3) + noise, 0, 255).astype(np.uint8)
    return Image.fromarray(patch, "RGB")


def render_original_page(pdf_path: Path, page_index: int, scale: float) -> tuple[fitz.Document, fitz.Page, Image.Image]:
    doc = fitz.open(pdf_path)
    if page_index < 0 or page_index >= doc.page_count:
        raise ValueError(f"page index out of range: {page_index + 1}; document has {doc.page_count} page(s)")
    page = doc[page_index]
    pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
    mode = "RGB"
    image = Image.frombytes(mode, (pix.width, pix.height), pix.samples)
    return doc, page, image


def save_pdf(
    source_doc: fitz.Document,
    source_page: fitz.Page,
    image_path: Path,
    output_path: Path,
    page_index: int,
    single_page: bool,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    new_doc = fitz.open()
    if single_page:
        new_page = new_doc.new_page(width=source_page.rect.width, height=source_page.rect.height)
        new_page.insert_image(new_page.rect, filename=image_path)
    else:
        for i, page in enumerate(source_doc):
            if i == page_index:
                new_page = new_doc.new_page(width=page.rect.width, height=page.rect.height)
                new_page.insert_image(new_page.rect, filename=image_path)
            else:
                new_doc.insert_pdf(source_doc, from_page=i, to_page=i)
    new_doc.set_metadata(source_doc.metadata)
    new_doc.save(output_path, garbage=4, deflate=True)
    new_doc.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Repair short text in a scanned/image-only PDF page.")
    parser.add_argument("--input", required=True, type=Path, help="Original PDF path.")
    parser.add_argument("--output", required=True, type=Path, help="Repaired PDF path.")
    parser.add_argument("--page", type=int, default=1, help="1-based page number. Default: 1.")
    parser.add_argument("--scale", type=float, default=2.0, help="Render scale for image-coordinate editing. Default: 2.")
    parser.add_argument("--cover", required=True, help="Patch rectangle in rendered pixels: x0,y0,x1,y1.")
    parser.add_argument("--text", required=True, help="Replacement text.")
    parser.add_argument("--position", required=True, help="Replacement text top-left position in rendered pixels: x,y.")
    parser.add_argument("--font", required=True, type=Path, help="TrueType/OpenType font path.")
    parser.add_argument("--size", required=True, type=int, help="Font size in rendered pixels.")
    parser.add_argument("--fill", default="22,25,30,250", help="RGBA text color. Default: 22,25,30,250.")
    parser.add_argument("--blur", type=float, default=0.16, help="Gaussian blur radius for text layer. Default: 0.16.")
    parser.add_argument("--noise", type=float, default=1.5, help="Paper patch noise sigma. Default: 1.5.")
    parser.add_argument("--seed", type=int, default=1234, help="Deterministic noise seed. Default: 1234.")
    parser.add_argument("--stroke-width", type=int, default=0, help="Optional glyph stroke width. Default: 0.")
    parser.add_argument("--stroke-fill", default=None, help="RGBA stroke color, e.g. 22,25,30,120.")
    parser.add_argument("--image-out", type=Path, default=None, help="Optional repaired page image output path.")
    parser.add_argument("--render-check", type=Path, default=None, help="Optional rendered final PDF PNG path.")
    parser.add_argument("--crop-check", type=Path, default=None, help="Optional target crop PNG path.")
    parser.add_argument("--crop", default=None, help="Crop rectangle for --crop-check in rendered pixels: x0,y0,x1,y1.")
    parser.add_argument("--single-page", action="store_true", help="Write only the repaired page instead of preserving all pages.")
    args = parser.parse_args()

    cover = parse_int_tuple(args.cover, 4, "--cover")
    position = parse_int_tuple(args.position, 2, "--position")
    fill = parse_int_tuple(args.fill, 4, "--fill")
    stroke_fill = parse_int_tuple(args.stroke_fill, 4, "--stroke-fill") if args.stroke_fill else None
    crop = parse_int_tuple(args.crop, 4, "--crop") if args.crop else None

    if not args.input.exists():
        raise FileNotFoundError(args.input)
    if not args.font.exists():
        raise FileNotFoundError(args.font)

    source_doc, source_page, image = render_original_page(args.input, args.page - 1, args.scale)
    patch = local_paper_patch(image, cover, args.seed, args.noise)
    image.paste(patch, cover)

    layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    font = ImageFont.truetype(str(args.font), args.size)
    draw.text(
        position,
        args.text,
        font=font,
        fill=fill,
        stroke_width=args.stroke_width,
        stroke_fill=stroke_fill,
    )
    if args.blur > 0:
        layer = layer.filter(ImageFilter.GaussianBlur(args.blur))
    repaired = Image.alpha_composite(image.convert("RGBA"), layer).convert("RGB")

    image_out = args.image_out or args.output.with_suffix(".page.png")
    repaired.save(image_out)
    save_pdf(source_doc, source_page, image_out, args.output, args.page - 1, args.single_page)

    if args.render_check or args.crop_check:
        check_doc = fitz.open(args.output)
        check_pix = check_doc[0].get_pixmap(matrix=fitz.Matrix(args.scale, args.scale), alpha=False)
        check_image = Image.frombytes("RGB", (check_pix.width, check_pix.height), check_pix.samples)
        if args.render_check:
            check_image.save(args.render_check)
        if args.crop_check:
            if not crop:
                raise ValueError("--crop is required when --crop-check is set")
            check_image.crop(crop).save(args.crop_check)
        check_doc.close()

    source_doc.close()
    print(os.path.abspath(args.output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

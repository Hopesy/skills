---
name: pdf-patch
description: Repair or replace short text in scanned or image-only PDF pages while preserving the visual appearance. Use when Codex needs to edit a PDF that has no text layer, replace one Chinese character or a short phrase, cover old pixels, match font size, weight, baseline, gray level, blur, and verify the rendered result with screenshots.
license: MIT
metadata:
  author: Hopesy
  version: "1.0.0"
---

# Scanned PDF Text Repair

Use this skill for image-only PDFs where text extraction returns empty or does not contain the target text. The goal is visual repair: rebuild the page image with a small localized patch, not semantic PDF text editing.

## Workflow

1. Inspect the PDF before editing.
   - Count pages with PyMuPDF.
   - Extract text with `page.get_text()`.
   - If the target text is absent and the page has one or more images, treat it as scanned/image-only.
   - Render the page at 2x or 3x scale and inspect the target area.
   - Prefer `scripts/inspect_pdf.py` for this step.

2. Locate the exact patch.
   - Use rendered pixel coordinates, not guessed PDF point coordinates.
   - Crop the target line and identify dark-pixel runs for each character.
   - Patch only the old character/phrase plus a tiny margin.
   - Do not repaint surrounding text unless the user explicitly wants phrase-level replacement.
   - Use `scripts/find_dark_runs.py` on the rendered page or crop when exact character bounds are unclear.

3. Rebuild from the original PDF every time.
   - Never edit on top of a previous repaired PDF during iterations.
   - Re-render the original page, apply one patch, and create the final PDF from that result.
   - This prevents cumulative blur, halos, and dirty paper blocks.

4. Match visual style.
   - Use nearby original characters as the reference for font family, size, baseline, weight, and gray level.
   - For Chinese official documents, test `simfang.ttf`, `STFANGSO.TTF`, `simsun.ttc`, `STSONG.TTF`, and `simkai.ttf` when available.
   - Prefer FangSong/simfang when the body text resembles Chinese official-document FangSong.
   - Match the replacement glyph's bottom alignment to adjacent characters before judging top alignment.
   - If the user says the glyph is too thin, increase stroke weight or opacity before changing font family.
   - If the user says the glyph is too small, increase font size and adjust baseline downward as needed.
   - Use `scripts/font_variants.py` to generate a contact sheet when visual matching is not obvious.

5. Preserve the paper background.
   - Build the cover patch from local bright pixels around the target area.
   - Add slight deterministic noise instead of a flat white rectangle.
   - Apply small Gaussian blur to replacement text only when needed to match scan softness.

6. Verify output.
   - Render the repaired PDF.
   - Crop the target line and inspect it visually.
   - Check page count and page size are unchanged.
   - For gray/weight checks, compare dark-pixel count and mean grayscale against adjacent original characters.
   - Report the output file and the specific text that changed.

## Script

Use these scripts instead of rewriting one-off Python snippets:

- `scripts/inspect_pdf.py`: inspect text layer, image count, page size, render a page, and make a crop.
- `scripts/find_dark_runs.py`: locate dark-pixel runs inside a rendered image area to estimate character boxes.
- `scripts/font_variants.py`: generate font/size preview sheets on the real target crop.
- `scripts/repair_scanned_pdf_text.py`: apply the final localized repair. It preserves other PDF pages by default; pass `--single-page` only when a one-page output is desired.

Do not preserve every exploratory command as a script. Keep only reusable steps: inspect, locate, preview, repair, verify.

## Repair Script

Typical use:

```powershell
py -X utf8 C:\Users\zhouh\.codex\skills\pdf-patch\scripts\repair_scanned_pdf_text.py `
  --input .\source.pdf `
  --output .\source_已修改.pdf `
  --page 1 `
  --cover 651,518,688,561 `
  --text 为 `
  --position 654,525 `
  --font C:\Windows\Fonts\simfang.ttf `
  --size 30 `
  --fill 22,25,30,250 `
  --blur 0.16
```

Render and crop after writing:

```powershell
py -X utf8 C:\Users\zhouh\.codex\skills\pdf-patch\scripts\repair_scanned_pdf_text.py `
  --input .\source.pdf `
  --output .\source_已修改.pdf `
  --page 1 `
  --cover 651,518,688,561 `
  --text 为 `
  --position 654,525 `
  --font C:\Windows\Fonts\simfang.ttf `
  --size 30 `
  --render-check .\check.png `
  --crop-check .\check-crop.png `
  --crop 620,505,1015,585
```

Inspect and crop before editing:

```powershell
py -X utf8 C:\Users\zhouh\.codex\skills\pdf-patch\scripts\inspect_pdf.py `
  --input .\source.pdf `
  --page 1 `
  --render .\page-1.png `
  --crop 620,505,1015,585 `
  --crop-out .\target-crop.png
```

Find candidate character runs:

```powershell
py -X utf8 C:\Users\zhouh\.codex\skills\pdf-patch\scripts\find_dark_runs.py `
  --image .\page-1.png `
  --box 620,505,1015,585 `
  --threshold 180
```

Generate font/size previews:

```powershell
py -X utf8 C:\Users\zhouh\.codex\skills\pdf-patch\scripts\font_variants.py `
  --image .\page-1.png `
  --output .\font-variants.png `
  --preview-crop 620,505,1015,585 `
  --cover 651,518,688,561 `
  --text 为 `
  --position 654,525 `
  --fonts C:\Windows\Fonts\simfang.ttf C:\Windows\Fonts\STFANGSO.TTF C:\Windows\Fonts\simsun.ttc `
  --sizes 28 29 30 31
```

## Coordinate Notes

- `--cover`, `--position`, and `--crop` are rendered image coordinates, not PDF points.
- The default render scale is `2`, matching a standard A4-ish PDF render near `1191 x 1685`.
- If the source page has a different resolution or orientation, render first and locate coordinates on that rendered image.
- For single-character Chinese repair, cover about the original character bounding box plus 2-5 pixels of margin.

## Failure Modes

- Visible font mismatch: test nearby system Chinese fonts and use adjacent characters to score shape similarity.
- Flat white block: use local paper sampling and noise; reduce cover size.
- Glyph too high or low: adjust only `--position` y first.
- Glyph too thin or light: increase alpha, add `--stroke-width 1`, or use a darker fill.
- Glyph too bold: remove stroke, lower alpha, or add a small blur.
- Repeated artifacts after iterations: confirm the script input is the original PDF, not the previous output.

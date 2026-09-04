#!/usr/bin/env python3
"""Convert source-prepped.png into an animated ASCII-art portrait SVG.

Usage: python scripts/make_ascii_svg.py
Reads:  <repo>/source-prepped.png
Writes: <repo>/avi-ascii.svg

Env:
  STATIC=1   emit a frozen, fully-drawn frame (no animation) for previewing.
"""
import os
from pathlib import Path

import numpy as np
from PIL import Image

REPO = Path(__file__).resolve().parent.parent

COLS = 100
ROWS = 53
RAMP = " .`:-=+*cs#%@"
FILL = "#c9d1d9"
GAMMA = 0.85  # <1 pushes midtones darker -> denser glyphs, more face detail

FONT_SIZE = 6.17         # px; monospace advance is ~0.6em, so this makes
                         # one glyph advance ~= CHAR_W (3.7px)
CHAR_W = 3.7             # advance per column
LINE_H = 6.6             # row height (monospace cells are taller than wide)
RENDER_WIDTH = 370        # target rendered width in px per the spec

ROW_DURATION = 0.55       # seconds for one row's wipe to complete
ROW_STAGGER = 0.045       # seconds between successive row start times


def load_grid():
    img = Image.open(REPO / "source-prepped.png").convert("L")
    img = img.resize((COLS, ROWS), Image.LANCZOS)
    arr = np.asarray(img).astype(np.float32) / 255.0

    mask_path = REPO / "source-mask.png"
    if mask_path.exists():
        m = Image.open(mask_path).convert("L").resize((COLS, ROWS), Image.LANCZOS)
        mask = np.asarray(m).astype(np.float32) / 255.0
    else:
        # Fallback: treat near-white as background.
        mask = (arr < 0.97).astype(np.float32)
    return arr, mask


def brightness_to_char(v: float) -> str:
    """Map subject brightness to a glyph.

    The ramp runs sparse -> dense. On a DARK README background these glyphs
    are light-on-dark, so more ink reads as BRIGHTER -- the opposite of ink
    on white paper. So bright pixels must get the DENSE end of the ramp, or
    the face renders as a photographic negative (hollow cheeks, glowing hair).

    Index 0 (space) is reserved for background, so the subject maps into
    [1, len-1] and never punches holes in the face.
    """
    v = max(0.0, min(1.0, v)) ** (1.0 / GAMMA)
    lo, hi = 1, len(RAMP) - 1
    idx = int(round(lo + v * (hi - lo)))
    return RAMP[max(lo, min(hi, idx))]


def xml_escape(ch: str) -> str:
    return {"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;"}.get(ch, ch)


def build_rows(arr, mask):
    # Normalize brightness across the SUBJECT's own range only. The white
    # background would otherwise pin the top of the range and crush all the
    # real facial tone into the bottom few glyphs.
    inside = mask >= 0.5
    if inside.any():
        vals = arr[inside]
        lo, hi = float(vals.min()), float(vals.max())
    else:
        lo, hi = 0.0, 1.0
    span = max(hi - lo, 1e-6)

    rows = []
    for r in range(ROWS):
        chars = []
        for c in range(COLS):
            if mask[r, c] < 0.5:
                chars.append(" ")
            else:
                chars.append(brightness_to_char((arr[r, c] - lo) / span))
        rows.append("".join(chars))
    return rows


def main():
    static = os.environ.get("STATIC") == "1"
    arr, mask = load_grid()
    rows = build_rows(arr, mask)

    width = COLS * CHAR_W
    height = ROWS * LINE_H
    total_duration = ROW_STAGGER * (ROWS - 1) + ROW_DURATION

    svg_parts = []
    svg_parts.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width:.1f} {height:.1f}" '
        f'width="{RENDER_WIDTH}" role="img" aria-label="ASCII art portrait">'
    )

    style = f"""
<style>
  .ascii-row {{
    font-family: "SFMono-Regular", Consolas, "Liberation Mono", Menlo, Courier, monospace;
    font-size: {FONT_SIZE}px;
    fill: {FILL};
    white-space: pre;
  }}
  .cursor {{
    fill: {FILL};
  }}
</style>"""
    svg_parts.append(style)

    # Opaque background. A GitHub profile renders in LIGHT mode for logged-out
    # visitors, and these glyphs are light-gray -- on a transparent background
    # the portrait is invisible to anyone not signed in. The info card and the
    # heatmap already bake in their own dark ground; this matches them.
    svg_parts.append(
        f'<rect x="0" y="0" width="{width:.1f}" height="{height:.1f}" '
        f'fill="#0d1117" rx="6"/>'
    )

    defs = ['<defs>']
    body = []

    for r, row_text in enumerate(rows):
        y = (r + 1) * LINE_H - (LINE_H - FONT_SIZE) / 2
        row_width = COLS * CHAR_W
        clip_id = f"clip{r}"
        start_time = r * ROW_STAGGER
        escaped = "".join(xml_escape(c) for c in row_text)

        if static:
            defs.append(
                f'<clipPath id="{clip_id}"><rect x="0" y="{r * LINE_H:.2f}" width="{row_width:.1f}" '
                f'height="{LINE_H:.1f}"/></clipPath>'
            )
            body.append(
                f'<g clip-path="url(#{clip_id})">'
                f'<text class="ascii-row" xml:space="preserve" x="0" y="{y:.2f}" '
                f'textLength="{row_width:.1f}" lengthAdjust="spacing">{escaped}</text>'
                f'</g>'
            )
            continue

        # Animated: clip rect grows from width 0 to full row width, then
        # freezes (fill="freeze") at the fully-drawn state. A small cursor
        # block rides the leading edge of the wipe and disappears once done.
        defs.append(f'<clipPath id="{clip_id}">')
        defs.append(
            f'  <rect x="0" y="{r * LINE_H:.2f}" width="0" height="{LINE_H:.1f}">'
            f'<animate attributeName="width" from="0" to="{row_width:.1f}" '
            f'begin="{start_time:.3f}s" dur="{ROW_DURATION:.3f}s" '
            f'fill="freeze" calcMode="linear"/>'
            f'</rect>'
        )
        defs.append('</clipPath>')

        body.append(
            f'<g clip-path="url(#{clip_id})">'
            f'<text class="ascii-row" xml:space="preserve" x="0" y="{y:.2f}" '
                f'textLength="{row_width:.1f}" lengthAdjust="spacing">{escaped}</text>'
            f'</g>'
        )

        # Cursor block: a thin solid rect that tracks the wipe edge via the
        # same x animation, then hides itself (opacity 0) once the row
        # finishes drawing.
        cursor_w = CHAR_W * 0.9
        cursor_h = LINE_H * 0.78
        cursor_y = y - FONT_SIZE + (LINE_H - cursor_h) / 2 + 0.3
        body.append(
            f'<rect class="cursor" x="{-cursor_w:.2f}" y="{cursor_y:.2f}" '
            f'width="{cursor_w:.2f}" height="{cursor_h:.2f}">'
            f'<animate attributeName="x" from="{-cursor_w:.2f}" to="{row_width - cursor_w:.2f}" '
            f'begin="{start_time:.3f}s" dur="{ROW_DURATION:.3f}s" '
            f'fill="freeze" calcMode="linear"/>'
            f'<set attributeName="opacity" to="0" '
            f'begin="{start_time + ROW_DURATION:.3f}s" fill="freeze"/>'
            f'</rect>'
        )

    defs.append('</defs>')

    svg_parts.extend(defs)
    svg_parts.extend(body)
    svg_parts.append('</svg>')

    out_path = REPO / "avi-ascii.svg"
    out_path.write_text("\n".join(svg_parts), encoding="utf-8")
    mode = "static" if static else f"animated (total ~{total_duration:.2f}s)"
    print(f"wrote {out_path} [{mode}], grid {COLS}x{ROWS}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Prep a photo for ASCII-art conversion: remove background, boost local
contrast, composite onto white, write grayscale PNG.

Usage: python scripts/prep_photo.py <path-to-source-photo>
Writes: <repo>/source-prepped.png
"""
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image
from rembg import remove

REPO = Path(__file__).resolve().parent.parent
CLAHE_CLIP_LIMIT = 5.0
CLAHE_TILE_GRID = (10, 10)

# Fraction of the subject's height to keep, measured down from the top of the
# head. A full-body crop leaves the face only ~15 of the grid's 53 rows, which
# is not enough character resolution to resolve glasses or expression.
# 1.0 = whole subject, ~0.6 = head and shoulders.
HEAD_CROP = 0.62
# The ASCII grid is 100 cols x 53 rows with cell aspect 3.7x6.6px, so the
# target image aspect is 370/349.8.
TARGET_ASPECT = 370.0 / 349.8


def main():
    if len(sys.argv) != 2:
        sys.exit("usage: prep_photo.py <source-photo>")
    src_path = Path(sys.argv[1])
    if not src_path.is_absolute():
        src_path = REPO / src_path

    raw = src_path.read_bytes()

    # 1. Background removal -> RGBA with subject isolated on transparent bg.
    cutout_bytes = remove(raw)
    cutout = Image.open(__import__("io").BytesIO(cutout_bytes)).convert("RGBA")

    # 2. Local contrast boost via CLAHE on the L channel of LAB.
    rgb = np.array(cutout.convert("RGB"))
    lab = cv2.cvtColor(rgb, cv2.COLOR_RGB2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=CLAHE_CLIP_LIMIT, tileGridSize=CLAHE_TILE_GRID)
    l_eq = clahe.apply(l)
    lab_eq = cv2.merge([l_eq, a, b])
    rgb_eq = cv2.cvtColor(lab_eq, cv2.COLOR_LAB2RGB)

    # 3. Composite the contrast-boosted subject onto pure white using the
    # cutout's alpha as the mask, so removed background maps to white.
    alpha = np.array(cutout.convert("RGBA"))[:, :, 3].astype(np.float32) / 255.0
    alpha = alpha[:, :, None]
    white = np.full_like(rgb_eq, 255, dtype=np.float32)
    composited = rgb_eq.astype(np.float32) * alpha + white * (1 - alpha)
    composited = composited.astype(np.uint8)

    # 3b. Crop to head-and-shoulders using the subject mask, then pad out to
    # the ASCII grid's aspect so the face fills the character grid.
    a2 = alpha[:, :, 0]
    ys, xs = np.where(a2 >= 0.5)
    if len(ys):
        top, bot = ys.min(), ys.max()
        keep_h = max(1, int((bot - top + 1) * HEAD_CROP))
        y0, y1 = top, min(a2.shape[0], top + keep_h)
        # Horizontal extent of the subject within the kept band only.
        band = a2[y0:y1]
        bxs = np.where(band.max(axis=0) >= 0.5)[0]
        x0, x1 = (bxs.min(), bxs.max() + 1) if len(bxs) else (0, a2.shape[1])
        cx, cy = (x0 + x1) / 2.0, (y0 + y1) / 2.0
        h = y1 - y0
        w = max(x1 - x0, h * TARGET_ASPECT)
        h = w / TARGET_ASPECT
        pad = 1.08  # a little breathing room around the head
        w, h = w * pad, h * pad
        cx0, cy0 = int(round(cx - w / 2)), int(round(cy - h / 2))
        cx1, cy1 = int(round(cx + w / 2)), int(round(cy + h / 2))
        # Pad with white rather than clamping, so the head stays centred.
        ph, pw = composited.shape[:2]
        px0, py0 = max(0, -cx0), max(0, -cy0)
        px1, py1 = max(0, cx1 - pw), max(0, cy1 - ph)
        if px0 or py0 or px1 or py1:
            composited = np.pad(composited, ((py0, py1), (px0, px1), (0, 0)),
                                mode="constant", constant_values=255)
            a2 = np.pad(a2, ((py0, py1), (px0, px1)), mode="constant",
                        constant_values=0.0)
            cx0, cy0, cx1, cy1 = cx0 + px0, cy0 + py0, cx1 + px0, cy1 + py0
        composited = composited[cy0:cy1, cx0:cx1]
        a2 = a2[cy0:cy1, cx0:cx1]
        alpha = a2[:, :, None]

    # 4. Grayscale output.
    gray = cv2.cvtColor(composited, cv2.COLOR_RGB2GRAY)
    out_path = REPO / "source-prepped.png"
    Image.fromarray(gray).save(out_path)

    # Keep the subject mask. Without it the ASCII stage cannot tell a bright
    # skin highlight from the pure-white background -- both are ~255 -- and
    # the face comes out hollow.
    mask_path = REPO / "source-mask.png"
    Image.fromarray((alpha[:, :, 0] * 255).astype(np.uint8)).save(mask_path)
    print(f"wrote {out_path} ({gray.shape[1]}x{gray.shape[0]})")
    print(f"wrote {mask_path}")


if __name__ == "__main__":
    main()

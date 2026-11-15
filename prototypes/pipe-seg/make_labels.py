"""Per-pixel line-style labels for pic-det's renders (pipe-seg, train = bsc-clinic only).

    python3 make_labels.py <render root> <out dir> clinic-hvac clinic-plumbing clinic-electrical

Label = palette index of the renderer's line colours (plan_picture.COLOURS 1..8, OTHER grey 9),
0 elsewhere, read from the clean render (lines are drawn without anti-aliasing, so exact colours),
then moved into each variant's geometry: scan = the same rotation (expand, about the centre) the
renderer applied (`rotation_deg`), photo = the same perspective (`corners_px`). Writes
<out>/<set>/<variant>/<stem>.png (image, RGB) + <stem>.lbl.png (uint8 labels).
"""

import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

COLOURS = ("#d62728", "#1f77b4", "#2ca02c", "#9467bd", "#ff7f0e", "#8c564b", "#e377c2", "#17becf")
OTHER = "#7f7f7f"
PALETTE = np.array([[int(c[i : i + 2], 16) for i in (1, 3, 5)] for c in (*COLOURS, OTHER)])
TOL = 6


def clean_label(rgb: np.ndarray) -> np.ndarray:
    label = np.zeros(rgb.shape[:2], np.uint8)
    px = rgb.astype(np.int16)
    for k, colour in enumerate(PALETTE, start=1):
        label[np.all(np.abs(px - colour) <= TOL, axis=2)] = k
    return label


def homography(src: np.ndarray, dst: np.ndarray) -> np.ndarray:
    rows, rhs = [], []
    for (x, y), (u, v) in zip(src, dst, strict=True):
        rows += [[x, y, 1, 0, 0, 0, -u * x, -u * y], [0, 0, 0, x, y, 1, -v * x, -v * y]]
        rhs += [u, v]
    return np.append(np.linalg.solve(np.array(rows), np.array(rhs)), 1.0).reshape(3, 3)


def moved(label: Image.Image, truth: dict) -> Image.Image:
    if truth["variant"] == "scan":
        return label.rotate(
            truth["rotation_deg"], resample=Image.Resampling.NEAREST, expand=True, fillcolor=0
        )
    if truth["variant"] == "photo":
        w, h = label.size
        page = np.array([(0, 0), (w, 0), (w, h), (0, h)], dtype=float)
        back = homography(np.array(truth["corners_px"]), page)
        return label.transform(
            (w, h),
            Image.Transform.PERSPECTIVE,
            tuple((back / back[2, 2]).flatten()[:8]),
            Image.Resampling.NEAREST,
            fillcolor=0,
        )
    return label


def main() -> None:
    root, out = Path(sys.argv[1]), Path(sys.argv[2])
    for name in sys.argv[3:]:
        for png in sorted((root / name / "clean-150").glob("*.png")):
            base = clean_label(np.array(Image.open(png).convert("RGB")))
            for variant in ("clean", "scan", "photo"):
                folder = root / name / f"{variant}-150"
                image = folder / (png.stem + (".png" if variant == "clean" else ".jpg"))
                truth = json.loads((folder / (png.stem + ".json")).read_text())
                label = moved(Image.fromarray(base), truth)
                img = Image.open(image).convert("RGB")
                assert img.size == label.size, (image, img.size, label.size)
                dest = out / name / variant
                dest.mkdir(parents=True, exist_ok=True)
                img.save(dest / f"{png.stem}.png")
                label.save(dest / f"{png.stem}.lbl.png")
                lab = np.array(label)
                print(name, variant, png.stem[-40:], img.size, "line px", int((lab > 0).sum()))


if __name__ == "__main__":
    main()

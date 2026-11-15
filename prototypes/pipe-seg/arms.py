"""pipe-seg A/B arms on pic-det's renders, all through local-dec's runs graph (frozen at c307319e).

    cd <Junction26-pipe-seg-ref>/backend && <python> arms.py <render root> <class maps root> \
        <sets comma> <variants comma> <out prefix>

Inputs held equal (as #603's bench): legend = the truth's `legend_lines` boxes, scale = the truth's
px_per_m. Arms, one emit file each (pic-det runs_score.py format):
- M: `read_graph` (colour mask per legend line colour; #603 as frozen).
- P: learned palette class. A style's class = the most common predicted line class among the learned
  line pixels in its legend box; its mask = the page's pixels predicted that class, legend boxes off.
- P1: P, except a page with one legend line style gives it every learned line pixel (amendment 2).
- L: learned line mask (class > 0) split by the sample's look: each learned line pixel goes to the
  style whose legend sample (median RGB of the learned pixels in its box) is nearest in RGB
  (ties within TIE: to every style of that look, which _own_pieces then splits by dash).
P and L then do what read_graph does to a colour mask: a dashed style (dash_pattern of the sample's
pieces) that shares its class/look with another style keeps its own pieces (_own_pieces), a dashed
style's dashes are closed (MAX_CLOSE_PX), then graph_of_masks (thinning, bridges, joins).
A style with no learned pixel in its legend box is refused (no run).
"""

import json
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

sys.path.insert(0, ".")
from app.adapters.discipline_pictures import dash_pattern, pixels
from app.adapters.discipline_pictures.runs_graph import (
    MAX_CLOSE_PX,
    PAD,
    _own_pieces,
    _pieces,
    graph_of_masks,
    read_graph,
)
from app.core.picture_facts import LegendEntry

TIE = 1.0  # RGB distance: two legend samples this close are one look (L)


def _alike(a, b) -> bool:
    return float(np.sqrt(((np.asarray(a, float) - np.asarray(b, float)) ** 2).sum())) <= TIE


def styles_of(cls: np.ndarray, rgb: np.ndarray, legend, arm: str):
    """(entry, key, dashes) per legend line style; key = palette class (P) or sample RGB (L)."""
    h, w = cls.shape
    found = []
    for entry in legend:
        x0, y0, x1, y1 = pixels(entry.box, w, h)
        box = cls[y0:y1, x0:x1]
        line = box > 0
        if not line.any():
            continue
        if arm == "P":
            key = int(np.bincount(box[line]).argmax())
            sample = box == key
        else:
            key = np.median(rgb[y0:y1, x0:x1][line].reshape(-1, 3), axis=0)
            sample = line
        pieces = [p for p, _ in _pieces(sample.astype(np.uint8))]
        found.append((entry, key, dash_pattern(pieces)))
    return found


def learned_masks(cls: np.ndarray, rgb: np.ndarray, legend, arm: str) -> dict[str, np.ndarray]:
    h, w = cls.shape
    lines = [e for e in legend if e.line and e.box is not None]
    if arm == "P1":
        if len(lines) == 1:  # one style: every learned line pixel is it
            mask = (cls > 0).astype(np.uint8)
            for e in legend:
                x0, y0, x1, y1 = pixels(e.box, w, h, PAD)
                mask[y0:y1, x0:x1] = 0
            return {lines[0].label: mask}
        arm = "P"
    styles = styles_of(cls, rgb, legend, arm)
    if not styles:
        return {}
    line = cls > 0
    if arm == "L":
        samples = np.array([k for _, k, _ in styles], dtype=np.float32)
        px = rgb[line].astype(np.float32)
        dist = np.sqrt(((px[:, None, :] - samples[None]) ** 2).sum(axis=2))
        near = dist <= dist.min(axis=1, keepdims=True) + TIE  # styles of one look share pixels
    masks = {}
    for i, (entry, key, dashes) in enumerate(styles):
        if arm == "P":
            mask = (cls == key).astype(np.uint8)
        else:
            mask = np.zeros(cls.shape, np.uint8)
            mask[line] = near[:, i]
        for e in legend:
            x0, y0, x1, y1 = pixels(e.box, w, h, PAD)
            mask[y0:y1, x0:x1] = 0
        same = [d for e, k, d in styles if e is not entry and _alike(k, key)]
        ink = _own_pieces(mask, dashes, [dashes, *same]) if same else mask
        if dashes is not None:
            k = min(MAX_CLOSE_PX, round(dashes.gap) + 2)
            ink = cv2.morphologyEx(ink, cv2.MORPH_CLOSE, np.ones((k, k), np.uint8))
        masks[entry.label] = ink
    return masks


def main() -> None:
    root, maps = Path(sys.argv[1]), Path(sys.argv[2])
    sets, variants, prefix = sys.argv[3].split(","), sys.argv[4].split(","), sys.argv[5]
    arms = sys.argv[6].split(",") if len(sys.argv) > 6 else ["M", "P", "L"]
    outs = {a: open(f"{prefix}-{a}.jsonl", "w") for a in arms}  # noqa: SIM115 (closed at exit)
    for name in sets:
        for variant in variants:
            folder = root / name / f"{variant}-150"
            for truth_path in sorted(folder.glob("*.json")):
                if truth_path.name.endswith(".graph.json"):
                    continue
                truth = json.loads(truth_path.read_text())
                if not truth.get("legend_lines"):
                    continue
                rgb = np.asarray(Image.open(folder / truth["picture"]).convert("RGB"))
                h, w = rgb.shape[:2]
                legend = tuple(
                    LegendEntry(
                        label=r["label"], group=None, line=True,
                        box=(r["box"][0] / w, r["box"][1] / h, r["box"][2] / w, r["box"][3] / h),
                    )
                    for r in truth["legend_lines"]
                )  # fmt: skip
                m_per_px = 1.0 / truth["px_per_m"]
                stem = Path(truth["picture"]).stem
                cls_path = maps / name / f"{variant}-150" / f"{stem}.cls.png"
                cls = np.array(Image.open(cls_path)) if cls_path.exists() else None
                for arm in arms:
                    if arm == "M":
                        runs = read_graph(rgb, legend, m_per_px)[0].runs
                    else:
                        masks = learned_masks(cls, rgb, legend, arm)
                        runs = graph_of_masks(masks, (w, h), m_per_px)[0] if masks else ()
                    sums: dict[str, float] = {}
                    for run in runs:
                        sums[run.label] = sums.get(run.label, 0.0) + run.length_m
                    line = {
                        "picture": f"{name}/{variant}-150/{truth['picture']}",
                        "runs": [
                            {"label": k, "length_m": round(v, 3)} for k, v in sorted(sums.items())
                        ],
                        "terminals": [],
                    }
                    outs[arm].write(json.dumps(line) + "\n")
                    outs[arm].flush()
                print(name, variant, stem[-35:], flush=True)


if __name__ == "__main__":
    main()

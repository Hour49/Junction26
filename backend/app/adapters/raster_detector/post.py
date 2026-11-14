"""From a detector's raw output to page fractions: the letterbox frame, the decoding of the two
export formats, duplicate suppression, per-class thresholds and plans. It mirrors
prototypes/detector/common.py (`Letterbox`, `letterbox`, `open_rgb`) and counts.py
(`dedup`, `group_plans`, `extraction`), so the runtime gives what core's arm files give.
"""

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Literal

import numpy as np
from PIL import Image
from pydantic import BaseModel, ConfigDict, Field

from app.core.drawing.model import ElementClass

type Box = tuple[float, float, float, float]


class DetectorConfig(BaseModel):
    """What the component runs with: core's `detector.json` (`counts.py config`), or ModelFacts
    plus a tune run (`ModelFacts.with_tuned`)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    # rfdetr: one input (normalised with mean/std), outputs `dets` (cx, cy, w, h as canvas
    # fractions) and `labels` (logits, one column per class, then the unused no-object column).
    # dfine: inputs `images` (0-1) and `orig_target_sizes` (w, h), outputs `labels`, `boxes`
    # (x0, y0, x1, y1 in canvas pixels) and `scores`.
    format: Literal["rfdetr", "dfine"]
    side: int = Field(gt=0)  # the square canvas the page is letterboxed onto
    classes: tuple[str, ...] = Field(min_length=1)  # training classes, in output column order
    element_class: dict[str, ElementClass | None]  # what each training class is written as
    read: tuple[ElementClass, ...]  # the classes the arm says it looked for
    thresholds: dict[str, float]  # minimum score per training class
    dedup: Literal["none", "iou", "ios"] = "ios"
    dedup_limit: float = Field(default=0.6, ge=0, le=1)
    groups: tuple[tuple[str, ...], ...] = (("door", "door_none", "door_wide"),)
    plans: Literal["detector", "grouping", "constant"] = "detector"
    plan_class: str = "plan"
    gap: float = Field(default=0.08, ge=0)  # grouping: gap between elements, share of the side
    min_items: int = Field(default=3, ge=1)  # grouping: elements a cluster needs to be a plan
    mean: tuple[float, float, float] | None = None
    std: tuple[float, float, float] | None = None
    top_k: int = Field(default=300, ge=1)  # rfdetr: detections kept, as rfdetr's post-process


DOOR_FAMILY = ("door", "door_none", "door_wide")  # counts.py: one opening is one kind of door


class ModelFacts(BaseModel):
    """core's `model.json` as export_onnx.py / export_yolo_onnx.py write it. Its prose keys
    (`model`, `licence`, `input`, `outputs`, `decode`, `head`) are ignored."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    format: Literal["rfdetr", "dfine"] = "rfdetr"  # an RF-DETR export has no `format` key
    side: int = Field(gt=0)
    classes: tuple[str, ...] = Field(min_length=1)
    element_class: dict[str, ElementClass | None]
    mean: tuple[float, float, float] | None = None
    std: tuple[float, float, float] | None = None

    def disagrees(self, config: "DetectorConfig") -> str | None:
        """The first model fact a detector.json states differently, or None."""
        for name in ("format", "side", "classes", "element_class", "mean", "std"):
            if getattr(self, name) != getattr(config, name):
                return name
        return None

    def with_tuned(self, tuned: dict[str, Any]) -> dict[str, Any]:
        """A DetectorConfig body: these facts plus `counts.py tune` output, with `counts.py
        write`'s defaults (plans by the detector, door kinds compete when tuned that way)."""
        rule, _, limit = str(tuned["dedup"]).partition(":")
        door_family = tuple(name for name in DOOR_FAMILY if name in self.classes)
        read = [name for name in dict.fromkeys(self.element_class.values()) if name is not None]
        return {
            **self.model_dump(),
            "read": read,
            "thresholds": {name: row["threshold"] for name, row in tuned["classes"].items()},
            "dedup": rule,
            "dedup_limit": float(limit or 0.6),
            "groups": [door_family] if tuned.get("door_family", True) and door_family else [],
            "plans": "detector" if "plan" in self.classes else "constant",
        }


@dataclass(frozen=True)
class Detection:
    name: str  # training class
    score: float
    box: Box  # canvas pixels


@dataclass(frozen=True)
class Letterbox:
    """How a page was placed on the square canvas: scaled to new size, pasted at (dx, dy)."""

    side: int
    width: int
    height: int
    new_width: int
    new_height: int
    dx: int
    dy: int

    @classmethod
    def fit(cls, width: int, height: int, side: int) -> "Letterbox":
        scale = side / max(width, height)
        new_width = max(1, min(side, round(width * scale)))
        new_height = max(1, min(side, round(height * scale)))
        return cls(
            side, width, height, new_width, new_height, (side - new_width) // 2,
            (side - new_height) // 2,
        )  # fmt: skip

    def to_page(self, box: Box) -> Box:
        """Canvas pixels to page fractions, clamped to the page."""
        x0, y0, x1, y1 = box

        def clamp(value: float) -> float:
            return min(1.0, max(0.0, value))

        return (
            clamp((x0 - self.dx) / self.new_width),
            clamp((y0 - self.dy) / self.new_height),
            clamp((x1 - self.dx) / self.new_width),
            clamp((y1 - self.dy) / self.new_height),
        )


def open_rgb(image: Image.Image) -> Image.Image:
    """The page as RGB on white (some CubiCasa PNGs carry alpha or a palette)."""
    if image.mode in ("RGBA", "LA", "PA") or "transparency" in image.info:
        rgba = image.convert("RGBA")
        white = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
        return Image.alpha_composite(white, rgba).convert("RGB")
    return image.convert("RGB")


def letterbox(image: Image.Image, side: int) -> tuple[Image.Image, Letterbox]:
    """The page scaled (Lanczos) so its long side is `side`, centred on white."""
    frame = Letterbox.fit(image.width, image.height, side)
    scaled = image.resize((frame.new_width, frame.new_height), Image.Resampling.LANCZOS)
    canvas = Image.new("RGB", (side, side), (255, 255, 255))
    canvas.paste(scaled, (frame.dx, frame.dy))
    return canvas, frame


def pixels(canvas: Image.Image, config: DetectorConfig) -> np.ndarray:
    """The canvas as the model's input: float32, 1 x 3 x side x side, 0-1 or normalised."""
    array = np.asarray(canvas, dtype=np.float32) / 255.0
    if config.mean is not None and config.std is not None:
        array = (array - np.asarray(config.mean, np.float32)) / np.asarray(config.std, np.float32)
    return np.ascontiguousarray(array.transpose(2, 0, 1)[None])


def decode_rfdetr(dets: np.ndarray, logits: np.ndarray, config: DetectorConfig) -> list[Detection]:
    """rfdetr's post-process as core's export describes it (model.json `decode`): sigmoid of the
    class columns (the extra no-object column is dropped), the top_k (query, class) pairs, boxes
    from the query's (cx, cy, w, h) fractions scaled to the canvas."""
    columns = len(config.classes)
    scores = 1.0 / (1.0 + np.exp(-logits[0, :, :columns].astype(np.float64)))
    flat = scores.reshape(-1)
    order = np.argsort(-flat, kind="stable")[: config.top_k]
    found = []
    for index in order:
        query, column = divmod(int(index), columns)
        cx, cy, w, h = (float(v) * config.side for v in dets[0, query])
        box = (cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2)
        found.append(Detection(config.classes[column], float(flat[index]), box))
    return found


def decode_dfine(
    labels: np.ndarray, boxes: np.ndarray, scores: np.ndarray, config: DetectorConfig
) -> list[Detection]:
    found = []
    for label, box, score in zip(labels[0], boxes[0], scores[0], strict=True):
        # A row the model did not fill has score 0 (YOLO exports in this format): no detection.
        if 0 <= int(label) < len(config.classes) and float(score) > 0:
            x0, y0, x1, y1 = (float(v) for v in box)
            found.append(Detection(config.classes[int(label)], float(score), (x0, y0, x1, y1)))
    return found


def _area(box: Box) -> float:
    return max(0.0, box[2] - box[0]) * max(0.0, box[3] - box[1])


def overlap(a: Box, b: Box, rule: str) -> float:
    """`iou`: intersection over union. `ios`: intersection over the smaller box."""
    inter = _area((max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])))
    if inter <= 0:
        return 0.0
    if rule == "iou":
        return inter / (_area(a) + _area(b) - inter)
    return inter / max(1e-9, min(_area(a), _area(b)))


def dedup(found: Sequence[Detection], config: DetectorConfig) -> list[Detection]:
    """Greedy suppression from the highest score down, inside a class and across the classes of
    one of `groups` (the door kinds: one opening is one kind of door)."""
    ranked = sorted(found, key=lambda d: -d.score)
    if config.dedup == "none":
        return ranked
    family = {name: index for index, names in enumerate(config.groups) for name in names}
    kept: list[Detection] = []
    for det in ranked:
        key = family.get(det.name, det.name)
        rivals = (k for k in kept if family.get(k.name, k.name) == key)
        if all(overlap(det.box, k.box, config.dedup) < config.dedup_limit for k in rivals):
            kept.append(det)
    return kept


def group_plans(boxes: Sequence[Box], gap: float, min_items: int) -> list[Box]:
    """Plans as clusters of elements: two join when the gap between their boxes is under `gap`;
    a cluster of at least `min_items` is a plan (its box: the union)."""
    parent = list(range(len(boxes)))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for i, a in enumerate(boxes):
        for j in range(i):
            b = boxes[j]
            dx = max(0.0, max(a[0], b[0]) - min(a[2], b[2]))
            dy = max(0.0, max(a[1], b[1]) - min(a[3], b[3]))
            if max(dx, dy) < gap:
                parent[find(i)] = find(j)
    clusters: dict[int, list[Box]] = defaultdict(list)
    for i, box in enumerate(boxes):
        clusters[find(i)].append(box)
    return sorted(
        (
            min(b[0] for b in members), min(b[1] for b in members),
            max(b[2] for b in members), max(b[3] for b in members),
        )
        for members in clusters.values()
        if len(members) >= min_items
    )  # fmt: skip


def kept(found: Sequence[Detection], config: DetectorConfig) -> list[Detection]:
    """Deduplicated, then each class's threshold (a class without one keeps nothing)."""
    return [d for d in dedup(found, config) if d.score >= config.thresholds.get(d.name, 2.0)]


def plan_boxes(found: Sequence[Detection], frame: Letterbox, config: DetectorConfig) -> list[Box]:
    """The plans in canvas pixels, by the config's rule."""
    if config.plans == "detector":
        return sorted(d.box for d in found if d.name == config.plan_class)
    if config.plans == "grouping":
        members = [d.box for d in found if d.name != config.plan_class]
        return group_plans(members, config.gap * config.side, config.min_items)
    return [
        (
            float(frame.dx), float(frame.dy), float(frame.dx + frame.new_width),
            float(frame.dy + frame.new_height),
        )
    ]  # fmt: skip

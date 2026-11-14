"""The region arm (`RASTER_COMPONENTS` source `region:<detector arm>`): core's element detector,
read the way the region track scored it on val (.agents/exp/region.md). arms.json holds, per
detector arm, the knobs and the all-val thresholds that were scored: C-yolo26s-nms with eight
views and plan windows (+1.3 pp [+0.6, +2.1] against C-yolo26s-v8), C-yolo26s-1536 with one view
and no windows (+0.5 pp [+0.1, +0.9] against C-yolo26s-1536). Another arm is refused.

1. The page is letterboxed (as `detector:<arm>`) and the detector reads it in the arm's views
   (the rotations and mirrors of the canvas; view 0 is the canvas as is).
2. With windows on, a sheet with two or more plans (view 0's plan boxes) gets one window per plan,
   cut from the page with a margin and letterboxed on its own, so small symbols are not shrunk
   with the whole sheet; the windows' element boxes replace the whole page's.
3. A segmenter (data/models/region/<model>/model.onnx, U-Net, eight views averaged) predicts the
   annotated flat on the page; element boxes whose centre is off it (neighbouring flats, legends)
   are dropped. Plans are kept.
4. The views are fused into one detection per object, then core's duplicate rule and the arm's
   per-class thresholds give the elements. Core's detector.json is not used: its thresholds were
   tuned without the region filter.

ONNX Runtime on the CPU only. The pure steps are in steps.py. Weights are never committed.
"""

import json
from io import BytesIO
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image
from pydantic import BaseModel, ConfigDict, Field

from app.adapters.raster_detector import Session, onnx_session, post
from app.adapters.raster_detector.views import (
    MIN_SCORE,
    VIEWS,
    Det,
    as_found,
    fuse_views,
    read_views,
)
from app.adapters.raster_region import steps
from app.adapters.raster_region.steps import Frame, Window
from app.core.drawing.model import Element, Plan, Scale
from app.core.errors import InvalidInputError, NotFoundError
from app.core.pipeline.model import DrawingFile, Extracted, Sheet
from app.core.pipeline.ports import DrawingFiles

ARMS = Path(__file__).with_name("arms.json")
MARGIN = 0.04  # a window's crop: the plan box grown by this share of its long side
OWN = 0.02  # the box whose detections a window keeps: the plan box grown by this share
MIN_SHARE = 0.02  # a region mask covering no more of the page keeps every box


class RegionFacts(BaseModel):
    """The segmenter's model.json (prototypes/region/export_onnx.py); prose keys ignored."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    side: int = Field(gt=0)
    mean: tuple[float, float, float]
    std: tuple[float, float, float]


class ArmKnobs(BaseModel):
    """One detector arm in arms.json: how it was read on val and its all-val thresholds
    (`counts.py tune` output, thresholds only)."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    views: int = Field(ge=1, le=len(VIEWS))
    windows: bool
    plan_score: float = Field(ge=0, le=1)  # a view-0 plan box this sure gets a window
    tuned: dict[str, Any]


def _read_json(path: Path) -> object:
    if not path.is_file():
        raise NotFoundError(f"{path} is missing")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise InvalidInputError(f"{path}: {error}") from error


def load_arm(detector: Path) -> tuple[ArmKnobs, post.DetectorConfig]:
    """The knobs of the detector arm in `detector` (its folder name) and its config: core's
    model.json facts plus the arm's thresholds from arms.json."""
    arms = _read_json(ARMS)
    assert isinstance(arms, dict)
    if detector.name not in arms:
        raise InvalidInputError(
            f"region:{detector.name}: no knobs for this detector arm; arms.json has {sorted(arms)}"
        )
    try:
        knobs = ArmKnobs.model_validate(arms[detector.name])
        facts = post.ModelFacts.model_validate(_read_json(detector / "model.json"))
        config = post.DetectorConfig.model_validate(facts.with_tuned(knobs.tuned))
    except (ValueError, KeyError, TypeError, AttributeError) as error:
        raise InvalidInputError(f"region:{detector.name}: {error}") from error
    return knobs, config


def load_region(folder: Path) -> tuple[RegionFacts, Session]:
    path = folder / "model.json"
    if not path.is_file():
        raise NotFoundError(f"{path} is missing (weights live only in data/models/region/)")
    try:
        facts = RegionFacts.model_validate(json.loads(path.read_text(encoding="utf-8")))
    except ValueError as error:
        raise InvalidInputError(f"{path}: {error}") from error
    return facts, onnx_session(folder / "model.onnx")


class RegionDetector:
    def __init__(
        self,
        files: DrawingFiles,
        config: post.DetectorConfig,
        detector: Session,
        region: tuple[RegionFacts, Session] | None,
        name: str,
        views: int = 8,
        windows: bool = True,
        plan_score: float = 0.43,
    ) -> None:
        if config.format != "dfine":
            raise InvalidInputError("region:<arm> runs a YOLO/D-FINE export (format dfine) only")
        if not 1 <= views <= len(VIEWS):
            raise InvalidInputError(f"views must be 1 to {len(VIEWS)}, not {views}")
        self._files = files
        self._config = config
        self._detector = detector
        self._region = region
        self._name = name
        self._views = views
        self._windows = windows
        self._plan_score = plan_score

    @classmethod
    def from_folders(
        cls, files: DrawingFiles, detector: Path, region: Path | None
    ) -> "RegionDetector":
        """The detector export's folder (data/models/detector/<arm>, an arm of arms.json) and
        the segmenter's (None: no region filter, the whole page counts)."""
        knobs, config = load_arm(detector)
        session = onnx_session(detector / "model.onnx")
        segmenter = load_region(region) if region is not None else None
        return cls(
            files, config, session, segmenter, detector.name, knobs.views, knobs.windows,
            knobs.plan_score,
        )  # fmt: skip

    def extract(self, source: DrawingFile, sheet: Sheet) -> Extracted:
        config = self._config
        with Image.open(BytesIO(self._files.read(source.path))) as image:
            page = post.open_rgb(image)
        canvas, box = post.letterbox(page, config.side)
        frame = _frame(box)
        whole = self._read(canvas)
        windows: list[Window] = []
        if self._windows:
            first = [d for d in whole if d.view == 0]
            windows = steps.plan_windows(
                first, frame, config.plan_class, self._plan_score, MARGIN, OWN
            )
        found = whole
        cut = len(windows) if len(windows) >= 2 else 0
        if cut:
            found = steps.merge_windows(
                whole, frame, [self._window(page, w) for w in windows], config.plan_class
            )
        if self._region is not None:
            mask, mask_frame = predict_mask(page, *self._region)
            found = steps.keep_in_region(
                found, frame, mask, mask_frame, config.plan_class, MIN_SHARE
            )
        fused = fuse_views(found, self._views)
        kept = post.kept([post.Detection(d.name, d.score, d.box) for d in fused], config)
        elements = []
        for det in kept:
            name = config.element_class.get(det.name)
            if name is None:
                continue
            elements.append(
                Element.model_validate(
                    {
                        "id": f"e{len(elements) + 1}",
                        "class": name,
                        "page": 1,
                        "box": tuple(round(v, 5) for v in box.to_page(det.box)),
                        "attrs": {"score": det.score, "detector_class": det.name},
                    }
                )
            )
        plans = tuple(
            Plan(id=f"p{index}", page=1, box=tuple(round(v, 5) for v in box.to_page(b)))  # type: ignore[arg-type]
            for index, b in enumerate(post.plan_boxes(kept, box, config), start=1)
        )
        return Extracted(
            method="detector",
            scale=Scale(status="no_scale"),
            plans=plans,
            elements=tuple(elements),
            read=config.read,
            notes=(
                f"region {self._name} ({self._views} views, {cut} plan windows, region "
                f"{'on' if self._region else 'off'}): {len(elements)} elements, {len(plans)} plans",
            ),
        )

    def _read(self, canvas: Image.Image) -> list[Det]:
        """Every detection of the canvas's views, in the canvas as is, view by view."""
        return read_views(canvas, self._views, self._config.side, self._detect)

    def _detect(self, canvas: Image.Image) -> list[Det]:
        config, session = self._config, self._detector
        sizes = np.asarray([[config.side, config.side]], dtype=np.int64)
        names = ["labels", "boxes", "scores"]
        labels, boxes, scores = session.run(
            names, {"images": post.pixels(canvas, config), "orig_target_sizes": sizes}
        )
        return [
            as_found(d.name, d.score, d.box, config.side)
            for d in post.decode_dfine(labels, boxes, scores, config)
            if d.score >= MIN_SCORE
        ]

    def _window(self, page: Image.Image, window: Window) -> tuple[Window, Frame, list[Det]]:
        canvas, box = post.letterbox(page.crop(window.crop), self._config.side)
        return window, _frame(box), self._read(canvas)


def predict_mask(
    page: Image.Image, facts: RegionFacts, session: Session
) -> tuple[np.ndarray, Frame]:
    """The annotated flat of an RGB page (`post.open_rgb`): a bool mask on the segmenter's own
    side x side canvas, and how the page sits on that canvas. The eight-view mean probability is
    stored as 0-255 like the prototype's mask files; region where it is at least 128. `facts`
    and `session` as `load_region` returns them."""
    canvas, box = post.letterbox(page, facts.side)
    x = np.asarray(canvas, dtype=np.float32) / 255.0
    x = (x - np.asarray(facts.mean, np.float32)) / np.asarray(facts.std, np.float32)
    x = x.transpose(2, 0, 1)[None]
    name = session.get_inputs()[0].name
    total = np.zeros((facts.side, facts.side), dtype=np.float32)
    for flip in (False, True):
        for k in range(4):
            v = np.rot90(x, k, axes=(2, 3))
            v = v[..., ::-1] if flip else v
            logits = np.asarray(session.run(None, {name: np.ascontiguousarray(v)})[0])
            p = 1.0 / (1.0 + np.exp(-logits))
            p = p[..., ::-1] if flip else p
            total += np.rot90(p, -k, axes=(2, 3))[0, 0]
    stored = np.round(total / 8 * 255).astype(np.uint8)
    return stored >= 128, _frame(box)


def _frame(box: post.Letterbox) -> Frame:
    return Frame(box.side, box.width, box.height, box.new_width, box.new_height, box.dx, box.dy)

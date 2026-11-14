"""The raster composite's detector component (`RASTER_COMPONENTS` source `detector:<arm>`): core's
trained element detector, run with ONNX Runtime on the CPU, so the demo needs no GPU.

data/models/detector/<arm>/ holds core's export as it writes it: `model.onnx` and `model.json`
(format, canvas side, classes, element classes, mean and std; prose keys are ignored). The counting
knobs (per-class thresholds, duplicate rule, plan rule) come from, in this order: `detector.json`
in the folder (`counts.py config`, which must agree with model.json), `thresholds.json` in the
folder, or the tune run the source names (`detector:<arm>:<run>` reads
data/stoa/exp/detector/raw/<run>.thresholds.json); the last two are `counts.py tune` output as is,
with `counts.py write`'s defaults. Weights are never committed.

The page is put on a white square canvas (Lanczos, long side = `side`), the model runs once,
and post.py turns the detections into elements and plans as page fractions, the same way
prototypes/detector/counts.py writes the arm's files. It reads no rooms and no scale.
"""

import json
from collections.abc import Sequence
from io import BytesIO
from pathlib import Path
from typing import Any, Protocol

import numpy as np
from PIL import Image
from pydantic import BaseModel

from app.adapters.raster_detector import post
from app.core.drawing.model import Element, Plan, Scale
from app.core.errors import InvalidInputError, NotFoundError
from app.core.pipeline.model import DrawingFile, Extracted, Sheet
from app.core.pipeline.ports import DrawingFiles

THREADS = 4  # the host is shared; one sheet at a time needs no more


class Session(Protocol):
    """What we use of `onnxruntime.InferenceSession` (tests pass a fake)."""

    def get_inputs(self) -> Sequence[Any]: ...

    def run(self, output_names: Any, input_feed: Any) -> Sequence[Any]: ...

    def get_outputs(self) -> Sequence[Any]: ...


def load_config(folder: Path, thresholds: Path | None = None) -> post.DetectorConfig:
    """The arm's config from core's export (module docstring says where each part comes from)."""
    facts = _valid(folder / "model.json", post.ModelFacts, _json(folder / "model.json"))
    knobs = folder / "detector.json"
    if knobs.is_file():
        config = _valid(knobs, post.DetectorConfig, _json(knobs))
        if (wrong := facts.disagrees(config)) is not None:
            raise InvalidInputError(f"{knobs} and model.json disagree on {wrong}")
        return config
    tuned = thresholds or folder / "thresholds.json"
    if not tuned.is_file():
        raise NotFoundError(
            f"{folder} has no detector.json or thresholds.json, and no tune run was named: give "
            "detector:<arm>:<run> (data/stoa/exp/detector/raw/<run>.thresholds.json)"
        )
    try:
        body = facts.with_tuned(_json(tuned))
    except (KeyError, TypeError, AttributeError, ValueError) as error:
        raise InvalidInputError(f"{tuned}: not counts.py tune output ({error!r})") from error
    return _valid(tuned, post.DetectorConfig, body)


def _json(path: Path) -> Any:
    if not path.is_file():
        raise NotFoundError(f"{path} is missing")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise InvalidInputError(f"{path}: {error}") from error


def _valid[T: BaseModel](path: Path, kind: type[T], body: Any) -> T:
    try:
        return kind.model_validate(body)
    except ValueError as error:
        raise InvalidInputError(f"{path}: {error}") from error


def onnx_session(model: Path) -> Session:
    if not model.is_file():
        raise NotFoundError(f"{model} is missing (weights live only in data/models/detector/)")
    import onnxruntime

    options = onnxruntime.SessionOptions()
    options.intra_op_num_threads = THREADS
    options.inter_op_num_threads = 1
    return onnxruntime.InferenceSession(str(model), options, providers=["CPUExecutionProvider"])


class OnnxDetector:
    def __init__(
        self, files: DrawingFiles, config: post.DetectorConfig, session: Session, name: str
    ) -> None:
        self._files = files
        self._config = config
        self._session = session
        self._name = name

    @classmethod
    def from_folder(
        cls, files: DrawingFiles, folder: Path, thresholds: Path | None = None
    ) -> "OnnxDetector":
        config = load_config(folder, thresholds)
        return cls(files, config, onnx_session(folder / "model.onnx"), folder.name)

    def extract(self, source: DrawingFile, sheet: Sheet) -> Extracted:
        config = self._config
        with Image.open(BytesIO(self._files.read(source.path))) as image:
            canvas, frame = post.letterbox(post.open_rgb(image), config.side)
        found = post.kept(self._detections(post.pixels(canvas, config)), config)
        elements = []
        for det in found:
            name = config.element_class.get(det.name)
            if name is None:
                continue
            elements.append(
                Element.model_validate(
                    {
                        "id": f"e{len(elements) + 1}",
                        "class": name,
                        "page": 1,
                        "box": tuple(round(v, 5) for v in frame.to_page(det.box)),
                        "attrs": {"score": round(det.score, 4), "detector_class": det.name},
                    }
                )
            )
        plans = tuple(
            Plan(id=f"p{index}", page=1, box=tuple(round(v, 5) for v in frame.to_page(box)))  # type: ignore[arg-type]
            for index, box in enumerate(post.plan_boxes(found, frame, config), start=1)
        )
        return Extracted(
            method="detector",
            scale=Scale(status="no_scale"),
            plans=plans,
            elements=tuple(elements),
            read=config.read,
            notes=(
                f"detector {self._name} ({config.format}, {config.side} px, onnxruntime CPU): "
                f"{len(elements)} elements, {len(plans)} plans by {config.plans}",
            ),
        )

    def _detections(self, x: np.ndarray) -> list[post.Detection]:
        config, session = self._config, self._session
        names = [output.name for output in session.get_outputs()]
        if config.format == "dfine":
            sizes = np.asarray([[config.side, config.side]], dtype=np.int64)
            outputs = dict(
                zip(
                    names,
                    session.run(names, {"images": x, "orig_target_sizes": sizes}),
                    strict=True,
                )
            )
            _need(outputs, ("labels", "boxes", "scores"))
            return post.decode_dfine(outputs["labels"], outputs["boxes"], outputs["scores"], config)
        feed = {session.get_inputs()[0].name: x}
        outputs = dict(zip(names, session.run(names, feed), strict=True))
        _need(outputs, ("dets", "labels"))
        return post.decode_rfdetr(outputs["dets"], outputs["labels"], config)


def _need(outputs: dict[str, Any], names: tuple[str, ...]) -> None:
    missing = [name for name in names if name not in outputs]
    if missing:
        raise InvalidInputError(f"the detector model has no output {missing}: {sorted(outputs)}")

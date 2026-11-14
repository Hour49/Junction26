"""The detector component (`detector:<arm>`): letterbox, the two export formats, duplicates,
thresholds and plans, run with a fake ONNX session on synthetic images. No weights needed."""

import io
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from PIL import Image

from app import composition
from app.adapters.raster_detector import OnnxDetector, load_config, post
from app.composition import build_pipeline
from app.core.drawing.model import Page
from app.core.errors import DomainError, InvalidInputError, NotFoundError
from app.core.pipeline.model import DrawingFile, Sheet
from app.settings import Settings

PNG = "data/cubicasa5k/x.png"
CLASSES = ("door", "door_none", "window", "plan")
BASE: dict[str, Any] = {
    "format": "dfine",
    "side": 100,
    "classes": CLASSES,
    "element_class": {"door": "door", "door_none": None, "window": "window", "plan": None},
    "read": ["door", "window"],
    "thresholds": {"door": 0.5, "door_none": 0.5, "window": 0.3, "plan": 0.5},
    "groups": [["door", "door_none"]],
}


def config(**changes: Any) -> post.DetectorConfig:
    return post.DetectorConfig.model_validate({**BASE, **changes})


def png(width: int, height: int, mode: str = "RGB") -> bytes:
    buffer = io.BytesIO()
    Image.new(mode, (width, height), (0, 0, 0, 0) if mode == "RGBA" else "black").save(
        buffer, "PNG"
    )
    return buffer.getvalue()


class Files:
    def __init__(self, data: bytes) -> None:
        self.data = data

    def read(self, path: str) -> bytes:
        assert path == PNG
        return self.data


class Named:
    def __init__(self, name: str) -> None:
        self.name = name


class FakeSession:
    """Answers with fixed outputs and keeps what it was fed."""

    def __init__(self, inputs: Sequence[str], outputs: dict[str, np.ndarray]) -> None:
        self.inputs = [Named(name) for name in inputs]
        self.outputs = outputs
        self.fed: dict[str, Any] = {}

    def get_inputs(self) -> list[Named]:
        return self.inputs

    def get_outputs(self) -> list[Named]:
        return [Named(name) for name in self.outputs]

    def run(self, output_names: list[str], input_feed: dict[str, Any]) -> list[np.ndarray]:
        self.fed = input_feed
        return [self.outputs[name] for name in output_names]


def sheet(width: int, height: int) -> tuple[DrawingFile, Sheet]:
    file = DrawingFile(path=PNG, size=1, sha256="0" * 64, kind="png")
    return file, Sheet(file=file, pages=(Page(page=1, width=width, height=height, unit="px"),))


def test_the_letterbox_centres_the_page_on_white_and_maps_boxes_back() -> None:
    page = Image.new("RGBA", (200, 100), (0, 0, 0, 0))  # transparent: becomes white
    canvas, frame = post.letterbox(post.open_rgb(page), 100)
    assert (frame.new_width, frame.new_height, frame.dx, frame.dy) == (100, 50, 0, 25)
    assert canvas.getpixel((50, 10)) == (255, 255, 255)
    assert canvas.getpixel((50, 50)) == (255, 255, 255)
    assert frame.to_page((0, 25, 50, 75)) == (0.0, 0.0, 0.5, 1.0)
    assert frame.to_page((-5, 0, 120, 80)) == (0.0, 0.0, 1.0, 1.0)  # clamped to the page
    tall = post.Letterbox.fit(100, 200, 100)  # a tall page is offset along x
    assert (tall.dx, tall.dy) == (25, 0)
    assert tall.to_page((25, 0, 75, 50)) == (0.0, 0.0, 1.0, 0.5)


def test_rfdetr_output_is_decoded_as_its_post_process_does() -> None:
    dets = np.array([[[0.5, 0.5, 0.2, 0.2], [0.1, 0.1, 0.1, 0.1]]], dtype=np.float32)
    logits = np.full((1, 2, 5), -10.0, dtype=np.float32)  # 4 classes + a no-object column
    logits[0, 0, 2] = 2.0  # query 0: window
    logits[0, 1, 4] = 5.0  # query 1: the no-object column scores highest but is not a class
    found = post.decode_rfdetr(dets, logits, config(format="rfdetr", top_k=1))
    assert len(found) == 1
    assert found[0].name == "window"
    assert found[0].score == pytest.approx(1 / (1 + np.exp(-2.0)))
    assert found[0].box == pytest.approx((40.0, 40.0, 60.0, 60.0))


def test_dfine_rows_with_score_zero_are_not_detections() -> None:
    labels = np.array([[2, 2]])
    boxes = np.array([[[0, 0, 10, 10], [20, 20, 30, 30]]], dtype=np.float32)
    scores = np.array([[0.4, 0.0]], dtype=np.float32)  # the second row was not filled
    found = post.decode_dfine(labels, boxes, scores, config(thresholds={"window": 0.0}))
    assert [(d.name, d.box) for d in found] == [("window", (0.0, 0.0, 10.0, 10.0))]
    assert len(post.kept(found, config(thresholds={"window": 0.0}))) == 1


def test_duplicates_compete_inside_a_group_and_each_class_has_its_threshold() -> None:
    door = post.Detection("door", 0.9, (0, 0, 10, 10))
    doorless = post.Detection("door_none", 0.8, (1, 1, 9, 9))  # same opening: suppressed
    window = post.Detection("window", 0.85, (1, 1, 9, 9))  # other class: kept
    weak = post.Detection("window", 0.2, (50, 50, 60, 60))  # under the window threshold
    unknown = post.Detection("stair", 0.99, (70, 70, 80, 80))  # no threshold: dropped
    assert post.kept([doorless, weak, window, door, unknown], config()) == [door, window]
    no_dedup = post.kept([doorless, door], config(dedup="none"))
    assert no_dedup == [door, doorless]


def test_plans_by_detector_by_grouping_or_the_whole_page() -> None:
    frame = post.Letterbox.fit(200, 100, 100)
    found = [
        post.Detection("plan", 0.9, (0, 25, 50, 75)),
        *(post.Detection("door", 0.9, (x, 30, x + 2, 32)) for x in (0, 3, 6)),
        post.Detection("door", 0.9, (90, 70, 92, 72)),  # alone: not a plan
    ]
    assert post.plan_boxes(found, frame, config(plans="detector")) == [(0, 25, 50, 75)]
    grouped = post.plan_boxes(found, frame, config(plans="grouping", gap=0.05, min_items=3))
    assert grouped == [(0, 30, 8, 32)]
    assert post.plan_boxes(found, frame, config(plans="constant")) == [(0.0, 25.0, 100.0, 75.0)]


def test_the_detector_reads_a_png_into_elements_and_plans_as_page_fractions() -> None:
    session = FakeSession(
        ["images", "orig_target_sizes"],
        {
            "labels": np.array([[0, 1, 2, 3]]),
            "boxes": np.array(
                [[[0, 25, 10, 35], [1, 26, 9, 34], [50, 50, 60, 60], [0, 25, 100, 75]]],
                dtype=np.float32,
            ),
            "scores": np.array([[0.9, 0.8, 0.7, 0.95]], dtype=np.float32),
        },
    )
    detector = OnnxDetector(Files(png(200, 100)), config(), session, "B")
    found = detector.extract(*sheet(200, 100))

    assert session.fed["images"].shape == (1, 3, 100, 100)
    assert session.fed["images"].dtype == np.float32
    assert float(session.fed["images"].max()) == 1.0  # white letterbox, 0-1 without mean/std
    assert session.fed["orig_target_sizes"].tolist() == [[100, 100]]
    assert [(e.class_, e.box, e.attrs["score"]) for e in found.elements] == [
        ("door", (0.0, 0.0, 0.1, 0.2), 0.9),
        ("window", (0.5, 0.5, 0.6, 0.7), 0.7),
    ]
    assert [p.box for p in found.plans] == [(0.0, 0.0, 1.0, 1.0)]
    assert found.read == ("door", "window")
    assert found.rooms == ()


def test_an_rfdetr_export_gets_normalised_pixels_and_needs_its_outputs() -> None:
    dets = np.array([[[0.5, 0.5, 0.2, 0.2]]], dtype=np.float32)
    logits = np.array([[[3.0, -9.0, -9.0, -9.0]]], dtype=np.float32)
    session = FakeSession(["input"], {"dets": dets, "labels": logits})
    mean, std = (0.5, 0.5, 0.5), (0.25, 0.25, 0.25)
    rfdetr = config(format="rfdetr", mean=mean, std=std)
    found = OnnxDetector(Files(png(100, 100)), rfdetr, session, "A").extract(*sheet(100, 100))
    assert float(session.fed["input"].min()) == pytest.approx(-2.0)  # black: (0 - 0.5) / 0.25
    assert [(e.class_, e.box) for e in found.elements] == [("door", (0.4, 0.4, 0.6, 0.6))]

    wrong = FakeSession(["input"], {"boxes": dets, "logits": logits})
    with pytest.raises(InvalidInputError, match="no output"):
        OnnxDetector(Files(png(100, 100)), rfdetr, wrong, "A").extract(*sheet(100, 100))


# core's model.json as export_onnx.py writes it for RF-DETR: no `format` key, prose beside facts.
MODEL_JSON: dict[str, Any] = {
    "model": "RFDETRSmall",
    "licence": "Apache-2.0",
    "side": 100,
    "classes": list(CLASSES),
    "element_class": BASE["element_class"],
    "input": "float32 NCHW ...",
    "mean": [0.485, 0.456, 0.406],
    "std": [0.229, 0.224, 0.225],
    "outputs": "dets ...; labels ...",
    "decode": "sigmoid ...",
}
# counts.py tune output as it writes it.
TUNED: dict[str, Any] = {
    "dedup": "ios:0.5",
    "door_family": True,
    "images": 376,
    "missing_raw": 0,
    "classes": {name: {"threshold": 0.3, "exact": 0.5} for name in CLASSES},
}


def write(folder: Path, name: str, body: dict[str, Any]) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / name).write_text(json.dumps(body))
    return folder / name


def test_cores_model_json_and_a_tune_run_make_the_config(tmp_path: Path) -> None:
    write(tmp_path, "model.json", MODEL_JSON)
    tuned = write(tmp_path / "runs", "A-val.thresholds.json", TUNED)
    found = load_config(tmp_path, tuned)
    assert (found.format, found.side, found.classes) == ("rfdetr", 100, CLASSES)
    assert (found.mean, found.std) == ((0.485, 0.456, 0.406), (0.229, 0.224, 0.225))
    assert found.read == ("door", "window")  # what a class is written as, in order, once
    assert found.thresholds == dict.fromkeys(CLASSES, 0.3)
    assert (found.dedup, found.dedup_limit, found.groups) == ("ios", 0.5, (("door", "door_none"),))
    assert found.plans == "detector"
    # The same tune output as thresholds.json in the folder needs no run name.
    write(tmp_path, "thresholds.json", {**TUNED, "door_family": False})
    assert load_config(tmp_path).groups == ()


def test_a_detector_json_is_used_when_it_agrees_with_model_json(tmp_path: Path) -> None:
    write(tmp_path, "model.json", {**MODEL_JSON, "format": "dfine", "mean": None, "std": None})
    write(tmp_path, "detector.json", {**BASE, "plans": "constant"})
    assert load_config(tmp_path).plans == "constant"
    write(tmp_path, "detector.json", {**BASE, "side": 640})
    with pytest.raises(InvalidInputError, match="disagree on side"):
        load_config(tmp_path)


def test_a_missing_or_bad_arm_folder_fails_at_startup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with pytest.raises(NotFoundError, match=r"model\.json"):
        load_config(tmp_path)
    write(tmp_path, "model.json", MODEL_JSON)
    with pytest.raises(NotFoundError, match="detector:<arm>:<run>"):
        load_config(tmp_path)
    write(tmp_path, "thresholds.json", {"classes": {}})  # no `dedup`
    with pytest.raises(InvalidInputError, match=r"thresholds\.json"):
        load_config(tmp_path)
    write(tmp_path, "detector.json", {**BASE, "format": "yolo"})
    with pytest.raises(InvalidInputError, match="format"):
        load_config(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("EXTRACTOR_RASTER", "composite")
    monkeypatch.setenv("RASTER_COMPONENTS", "elements=detector:../../x,plans=one-plan")
    with pytest.raises(InvalidInputError, match="not a path inside"):
        build_pipeline(Settings(), tmp_path)


def test_the_source_names_the_arm_and_its_tune_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    models, runs = tmp_path / "models", tmp_path / "runs"
    write(models / "C", "model.json", MODEL_JSON)
    write(runs, "C-onnx-val.thresholds.json", TUNED)
    monkeypatch.setattr(composition, "DETECTOR_DIR", models)
    monkeypatch.setattr(composition, "DETECTOR_RUNS", runs)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("EXTRACTOR_RASTER", "composite")
    monkeypatch.setenv("RASTER_COMPONENTS", "elements=detector:C:C-onnx-val,plans=one-plan")
    # The config was found; only the weights are missing from this synthetic folder.
    with pytest.raises(DomainError, match=r"model\.onnx is missing"):
        build_pipeline(Settings(), tmp_path)
    monkeypatch.setenv("RASTER_COMPONENTS", "elements=detector:C:../../x,plans=one-plan")
    with pytest.raises(InvalidInputError, match="not a path inside"):
        build_pipeline(Settings(), tmp_path)

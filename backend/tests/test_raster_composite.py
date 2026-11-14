"""`EXTRACTOR_RASTER=composite`: one raster drawing from component readers, one source per part,
nothing counted twice, and a class a source did not read stays unknown. Synthetic drawings only."""

import hashlib
import json
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any, ClassVar

import pytest
from jsonschema import Draft202012Validator

from app import composition
from app.adapters.decisions.g1main import FAMILIES
from app.adapters.extraction_v1 import ExtractionV1Reader, ExtractionV1Writer
from app.adapters.raster import CompositeRasterExtractor, assemble, parse_components
from app.adapters.raster.precomputed import PrecomputedExtractor, WholePagePlan
from app.composition import build_pipeline
from app.core.answering.model import Answer, Question
from app.core.drawing.model import Box, Drawing, Element, Page, Plan, ReadClass, Room, Scale
from app.core.errors import InvalidInputError
from app.core.pipeline.model import DrawingFile, Extracted, Sheet
from app.core.pipeline.ports import Extractor
from app.core.pipeline.takeoff import known_quantities
from app.settings import Settings

SCHEMAS = Path(__file__).parents[2] / "eval" / "schemas"
PNG = "data/cubicasa5k/colorful-1.png"
FILE = DrawingFile(path=PNG, size=1, sha256="0" * 64, kind="png")
SHEET = Sheet(file=FILE, pages=(Page(page=1, width=40, height=30, unit="px"),))
LEFT: Box = (0.0, 0.0, 0.5, 1.0)
RIGHT: Box = (0.5, 0.0, 1.0, 1.0)


def element(kind: str, box: Box, plan: str | None = None, score: float = 0.9) -> Element:
    return Element.model_validate(
        {"id": "x", "class": kind, "page": 1, "plan": plan, "box": box, "attrs": {"score": score}}
    )


def room(kind: str, box: Box, plan: str | None = None) -> Room:
    return Room(id="x", type=kind, page=1, plan=plan, box=box)  # type: ignore[arg-type]


class Fake:
    """A component that gives a fixed reading and counts how often it was asked."""

    def __init__(
        self,
        *,
        elements: Sequence[Element] = (),
        rooms: Sequence[Room] = (),
        plans: Sequence[Plan] = (),
        read: Sequence[ReadClass] | None = None,
    ) -> None:
        self.found = Extracted(
            method="detector",
            scale=Scale(status="no_scale"),
            plans=tuple(plans),
            elements=tuple(elements),
            rooms=tuple(rooms),
            read=None if read is None else tuple(read),
            notes=("fake",),
        )
        self.calls = 0

    def extract(self, source: DrawingFile, sheet: Sheet) -> Extracted:
        self.calls += 1
        return self.found


def composite(parts: dict[str, str], readers: dict[str, Extractor]) -> CompositeRasterExtractor:
    return assemble(parse_components(",".join(f"{k}={v}" for k, v in parts.items())), readers.get)  # type: ignore[arg-type]


def test_the_spec_is_parsed_into_one_source_per_part() -> None:
    assert parse_components(" elements=exp:detector/A , door=exp:detector/B,plans=one-plan,") == {
        "elements": "exp:detector/A",
        "door": "exp:detector/B",
        "plans": "one-plan",
    }


@pytest.mark.parametrize(
    ("spec", "says"),
    [
        ("elements=a", "needs plans"),
        ("plans=a,plans=b", "given twice"),
        ("plans=a,walls=b", "unknown part 'walls'"),
        ("plans=a,rooms", "not <part>=<source>"),
        ("plans=a,rooms=", "not <part>=<source>"),
    ],
)
def test_a_bad_spec_is_refused_saying_why(spec: str, says: str) -> None:
    with pytest.raises(InvalidInputError, match=says):
        parse_components(spec)


def test_each_part_comes_from_its_one_source_and_nothing_is_counted_twice() -> None:
    detector = Fake(
        elements=[element("door", LEFT), element("window", LEFT), element("window", RIGHT)],
        read=["door", "window", "toilet"],
    )
    windows = Fake(elements=[element("window", RIGHT, score=0.5)], read=["window"])
    ocr = Fake(rooms=[room("kitchen", RIGHT), room("bedroom", LEFT)], read=["room"])
    plans = Fake(plans=[Plan(id="a", page=1, box=LEFT), Plan(id="b", page=1, box=RIGHT)], read=())
    found = composite(
        {"elements": "det", "window": "win", "rooms": "ocr", "plans": "pl"},
        {"det": detector, "win": windows, "ocr": ocr, "pl": plans},
    ).extract(FILE, SHEET)

    # The detector's windows are left out: windows come from their own source only.
    assert [(e.class_, e.attrs["component"]) for e in found.elements] == [
        ("door", "det"),
        ("window", "win"),
    ]
    assert found.read == ("door", "window", "toilet", "room")  # union of what each part read
    assert [e.id for e in found.elements] == ["e1", "e2"]
    assert [r.id for r in found.rooms] == ["r1", "r2"]
    assert [p.id for p in found.plans] == ["p1", "p2"]
    # Every item sits on the plan whose box holds its centre, whatever source it came from.
    assert [e.plan for e in found.elements] == ["p1", "p2"]
    assert [r.plan for r in found.rooms] == ["p2", "p1"]
    assert found.elements[1].attrs["score"] == 0.5  # the source's confidence is kept
    assert all(fake.calls == 1 for fake in (detector, windows, ocr, plans))


def test_a_source_that_did_not_read_the_sheet_leaves_its_classes_unknown_not_zero() -> None:
    missing = Fake(read=())  # what a precomputed arm gives for an image it has no file for
    found = composite(
        {"elements": "arm", "rooms": "arm", "plans": "one"},
        {"arm": missing, "one": WholePagePlan()},
    ).extract(FILE, SHEET)
    assert found.read == ()
    assert missing.calls == 1  # one source for two parts reads the sheet once
    drawing = Drawing(
        file=PNG, pages=SHEET.pages, scale=found.scale, plans=found.plans, read=found.read
    )
    assert known_quantities(drawing) == {}  # no count at all, so the answer is the prior's


def test_a_class_the_source_did_not_look_for_is_left_out_and_its_items_dropped() -> None:
    detector = Fake(elements=[element("door", LEFT), element("sink", LEFT)], read=["door"])
    found = composite(
        {"elements": "det", "plans": "one"}, {"det": detector, "one": WholePagePlan()}
    ).extract(FILE, SHEET)
    assert found.read == ("door",)
    assert [e.class_ for e in found.elements] == ["door"]
    quantities = known_quantities(
        Drawing(
            file=PNG,
            pages=SHEET.pages,
            scale=found.scale,
            plans=found.plans,
            elements=found.elements,
            read=found.read,
        )
    )
    assert (quantities["door"].value, quantities["plan"].value) == (1, 1)
    assert "sink" not in quantities and "window" not in quantities


def gold(file: str, **lists: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "schema": "extraction_v1",
        "file": file,
        "split": "dev",
        "truth": "elements",
        "pages": [{"page": 1, "width": 40, "height": 30, "unit": "px"}],
        "scale": {"status": "no_scale"},
        "plans": [{"id": "p1", "page": 1, "box": [0.0, 0.0, 1.0, 1.0]}],
        "elements": lists.get("elements", []),
        "rooms": lists.get("rooms", []),
    }


def test_precomputed_reads_an_arms_file_by_its_file_field_and_nothing_for_a_missing_one(
    tmp_path: Path,
) -> None:
    door = {"id": "d", "class": "door", "page": 1, "plan": "p1", "box": [0.1, 0.1, 0.2, 0.2]}
    (tmp_path / "colorful-1.json").write_text(json.dumps(gold(PNG, elements=[door])))
    arm = PrecomputedExtractor(tmp_path)
    found = arm.extract(FILE, SHEET)
    assert (len(found.elements), len(found.plans), found.read) == (1, 1, None)
    other = SHEET.model_copy(update={"file": FILE.model_copy(update={"path": "data/c/x.png"})})
    assert arm.extract(FILE, other).read == ()


def test_precomputed_finds_an_upload_by_its_content_when_the_path_is_not_the_datasets(
    tmp_path: Path, make_png: Callable[[int, int], bytes]
) -> None:
    dataset, arm = tmp_path / "dataset", tmp_path / "arm"
    (dataset / "data" / "cubicasa5k").mkdir(parents=True)
    image = make_png(40, 30)
    (dataset / PNG).write_bytes(image)
    (dataset / "data" / "cubicasa5k" / "colorful-2.png").write_bytes(make_png(30, 40))
    arm.mkdir()
    door = {"id": "d", "class": "door", "page": 1, "plan": "p1", "box": [0.1, 0.1, 0.2, 0.2]}
    (arm / "colorful-1.json").write_text(json.dumps(gold(PNG, elements=[door])))
    other = "data/cubicasa5k/colorful-2.png"
    (arm / "colorful-2.json").write_text(json.dumps(gold(other)))

    def upload(data: bytes) -> tuple[DrawingFile, Sheet]:
        file = DrawingFile(
            path="uploads/plan.png", size=len(data), sha256=hashlib.sha256(data).hexdigest(),
            kind="png",
        )  # fmt: skip
        return file, SHEET.model_copy(update={"file": file})

    found = PrecomputedExtractor(arm, dataset).extract(*upload(image))
    assert [e.class_ for e in found.elements] == ["door"]
    assert f"matched by content to {PNG}" in found.notes
    # Same size, other bytes: not that image. Without the dataset folder: path only.
    changed = image[:-5] + bytes(5)
    assert PrecomputedExtractor(arm, dataset).extract(*upload(changed)).read == ()
    assert PrecomputedExtractor(arm).extract(*upload(image)).read == ()


def test_precomputed_reads_nothing_from_a_file_of_totals_only(tmp_path: Path) -> None:
    body = {**gold(PNG), "truth": "counts", "plans": [], "counts": {"door": 3}}
    (tmp_path / "colorful-1.json").write_text(json.dumps(body))
    found = PrecomputedExtractor(tmp_path).extract(FILE, SHEET)
    assert (found.read, found.elements, found.plans) == ((), (), ())


def test_a_wrong_source_name_or_a_missing_spec_fails_at_startup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("EXTRACTOR_RASTER", "composite")
    with pytest.raises(InvalidInputError, match="needs plans"):
        build_pipeline(Settings(), tmp_path)
    monkeypatch.setenv("RASTER_COMPONENTS", "plans=one-plan,rooms=ocr-v9")
    with pytest.raises(InvalidInputError, match="unknown source 'ocr-v9'"):
        build_pipeline(Settings(), tmp_path)


def test_the_composite_runs_in_the_pipeline_and_writes_valid_extraction_v1(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, make_png: Callable[[int, int], bytes]
) -> None:
    dataset, arm, out = tmp_path / "dataset", tmp_path / "arm", tmp_path / "out"
    (dataset / "data" / "cubicasa5k").mkdir(parents=True)
    (dataset / PNG).write_bytes(make_png(40, 30))
    arm.mkdir()
    boxes = ([0.1, 0.1, 0.2, 0.2], [0.6, 0.1, 0.7, 0.2])
    doors = [
        {"id": f"d{i}", "class": "door", "page": 1, "plan": "p1", "box": box}
        for i, box in enumerate(boxes)
    ]
    sauna = {"id": "s", "type": "sauna", "page": 1, "plan": "p1", "box": [0.3, 0.3, 0.5, 0.5]}
    (arm / "colorful-1.json").write_text(json.dumps(gold(PNG, elements=doors, rooms=[sauna])))
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("EXTRACTOR_RASTER", "composite")
    monkeypatch.setenv("RASTER_COMPONENTS", f"door=dir:{arm},rooms=dir:{arm},plans=one-plan")

    report = build_pipeline(Settings(), dataset).ingest(
        [PNG], ExtractionV1Writer(out, {PNG: "dev"})
    )

    assert [(sheet.route, sheet.takeoff["door"]) for sheet in report.sheets] == [("raster", 2)]
    body = json.loads((out / "cubicasa5k" / "colorful-1.png.json").read_text())
    schema = json.loads((SCHEMAS / "extraction_v1.schema.json").read_text(encoding="utf-8"))
    Draft202012Validator(schema).validate(body)
    assert body["read"] == ["door", "room"]
    drawing = ExtractionV1Reader(out).drawing(PNG)
    assert drawing is not None
    quantities = known_quantities(drawing)
    assert (quantities["plan"].value, quantities["room:sauna"].value) == (1, 1)
    assert "window" not in quantities


class FakeGemini:
    """Stands in for GeminiClient: no network, a fixed reply, the key it was built with."""

    built: ClassVar[list[str]] = []
    REPLY = '[{"type": "bedroom", "label": "MH", "box_2d": [100, 200, 300, 400]}]'

    def __init__(self, api_key: str, model: str, timeout_s: float) -> None:
        FakeGemini.built.append(api_key)
        self.name = model

    def ask(self, png: bytes, prompt: str) -> str:
        return self.REPLY


def test_rooms_from_gemini_are_wired_with_its_settings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, make_png: Callable[[int, int], bytes]
) -> None:
    dataset, out = tmp_path / "dataset", tmp_path / "out"
    (dataset / "data" / "cubicasa5k").mkdir(parents=True)
    (dataset / PNG).write_bytes(make_png(40, 30))
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("EXTRACTOR_RASTER", "composite")
    monkeypatch.setenv("RASTER_COMPONENTS", "rooms=gemini,plans=one-plan")
    monkeypatch.setenv("GEMINI_CACHE_DIR", str(tmp_path / "cache"))
    with pytest.raises(InvalidInputError, match="GEMINI_API_KEY"):  # no key: fails at startup
        build_pipeline(Settings(), dataset)

    monkeypatch.setattr(composition, "GeminiClient", FakeGemini)
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setenv("GEMINI_MODEL", "fake-model")
    pipeline = build_pipeline(Settings(), dataset)
    assert FakeGemini.built[-1] == "test-key"
    report = pipeline.ingest([PNG], ExtractionV1Writer(out, {PNG: "dev"}))
    assert report.sheets[0].takeoff["room:bedroom"] == 1
    drawing = ExtractionV1Reader(out).drawing(PNG)
    assert drawing is not None
    assert drawing.read == ("room",)
    assert [(r.type, r.label, r.attrs["component"]) for r in drawing.rooms] == [
        ("bedroom", "MH", "gemini")
    ]
    assert list((tmp_path / "cache").glob("*fake-model.json"))  # the reply is cached


class FakeVerda:
    """Stands in for HttpReaderClient: records how it was built, answers with one door."""

    built: ClassVar[list[tuple[str, str, int]]] = []

    def __init__(self, url: str, key: str, *, max_in_flight: int) -> None:
        FakeVerda.built.append((url, key, max_in_flight))

    def read(self, image: bytes) -> dict[str, Any]:
        door = element("door", (0.1, 0.1, 0.2, 0.2))
        found = Extracted(
            method="detector",
            scale=Scale(status="no_scale"),
            plans=(Plan(id="p1", page=1, box=(0.0, 0.0, 1.0, 1.0)),),
            elements=(door,),
            read=("door",),
        )
        return {"schema": "reader_v1", "model": "m", "provider": "cpu", "seconds": 0.1,
                "extracted": found.model_dump(mode="json", by_alias=True)}  # fmt: skip


def test_the_verda_reader_is_wired_with_its_url_key_and_requests_in_flight(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, make_png: Callable[[int, int], bytes]
) -> None:
    dataset, out = tmp_path / "dataset", tmp_path / "out"
    (dataset / "data" / "cubicasa5k").mkdir(parents=True)
    (dataset / PNG).write_bytes(make_png(40, 30))
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("EXTRACTOR_RASTER", "composite")
    monkeypatch.setenv("RASTER_COMPONENTS", "elements=verda,plans=verda")
    with pytest.raises(InvalidInputError, match="VERDA_READER_URL"):  # no URL: fails at startup
        build_pipeline(Settings(), dataset)

    monkeypatch.setattr(composition, "HttpReaderClient", FakeVerda)
    monkeypatch.setenv("VERDA_READER_URL", "https://reader.example")
    monkeypatch.setenv("VERDA_INFERENCE_API_KEY", "test-key")
    monkeypatch.setenv("VERDA_READER_MAX_IN_FLIGHT", "2")
    pipeline = build_pipeline(Settings(), dataset)
    assert FakeVerda.built == [("https://reader.example", "test-key", 2)]  # one client, both parts
    report = pipeline.ingest([PNG], ExtractionV1Writer(out, {PNG: "dev"}))
    assert (report.sheets[0].takeoff["door"], report.sheets[0].takeoff["plan"]) == (1, 1)
    assert Settings().verda_reader_max_in_flight == 2
    monkeypatch.delenv("VERDA_READER_MAX_IN_FLIGHT")
    assert Settings().verda_reader_max_in_flight == 4  # the default


class FakeDecisions:
    """Stands in for DecisionsClient: records the key, and Gemini is sure the page has 1 toilet,
    no shower or bathtub and no sauna."""

    built: ClassVar[list[str]] = []
    calls = 0

    def __init__(self, key: str, timeout_s: float) -> None:
        FakeDecisions.built.append(key)

    @property
    def model(self) -> str:
        return "fake-decider"

    def decide(self, body: dict[str, Any]) -> dict[str, Any]:
        FakeDecisions.calls += 1
        sure = {"toilet": {0: 0.01, 1: 0.99}, "shower+bathtub": {0: 1.0}, "sauna": {0: 1.0}}
        return {"answers": {
            f"g1_{key}": {"type": "choice", "probabilities": {
                str(k): v for k, v in sure.get(family, {1: 1.0}).items()}}
            for family, (key, _, _) in FAMILIES.items()}}  # fmt: skip


class FakeVerdaNoToilet(FakeVerda):
    """A reader that looked for toilets and found none."""

    def read(self, image: bytes) -> dict[str, Any]:
        found = Extracted(
            method="detector",
            scale=Scale(status="no_scale"),
            plans=(Plan(id="p1", page=1, box=(0.1, 0.1, 0.9, 0.9)),),
            elements=(),
            read=("toilet", "shower", "bathtub", "sauna_stove"),
        )
        return {"schema": "reader_v1", "model": "m", "provider": "cpu", "seconds": 0.1,
                "extracted": found.model_dump(mode="json", by_alias=True)}  # fmt: skip


def test_decisions_wraps_its_inner_source_and_swaps_counts_with_one_cached_call(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, make_png: Callable[[int, int], bytes]
) -> None:
    dataset, out = tmp_path / "dataset", tmp_path / "out"
    (dataset / "data" / "cubicasa5k").mkdir(parents=True)
    (dataset / PNG).write_bytes(make_png(40, 30))
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("EXTRACTOR_RASTER", "composite")
    monkeypatch.setenv("RASTER_COMPONENTS", "elements=decisions:verda,plans=decisions:verda")
    monkeypatch.setenv("VERDA_READER_URL", "https://reader.example")
    monkeypatch.setenv("DECISIONS_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setattr(composition, "HttpReaderClient", FakeVerdaNoToilet)
    with pytest.raises(InvalidInputError, match="GEMINI_API_KEY"):  # no key: fails at startup
        build_pipeline(Settings(), dataset)

    monkeypatch.setattr(composition, "DecisionsClient", FakeDecisions)
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    pipeline = build_pipeline(Settings(), dataset)
    assert FakeDecisions.built[-1] == "test-key"
    report = pipeline.ingest([PNG], ExtractionV1Writer(out, {PNG: "dev"}))
    assert report.sheets[0].takeoff["toilet"] == 1  # the detector read 0, Gemini is sure of 1
    assert report.sheets[0].takeoff["plan"] == 1  # plans pass through
    assert FakeDecisions.calls == 1  # elements and plans: one source, one call
    assert len(list((tmp_path / "cache").glob("*fake-decider*.json"))) == 1


def test_decisions_confidence_rates_drawing_answers_with_the_count_swaps_reader(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, make_png: Callable[[int, int], bytes]
) -> None:
    dataset, out = tmp_path / "dataset", tmp_path / "out"
    (dataset / "data" / "cubicasa5k").mkdir(parents=True)
    (dataset / PNG).write_bytes(make_png(40, 30))
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("EXTRACTOR_RASTER", "composite")
    monkeypatch.setenv("RASTER_COMPONENTS", "elements=decisions:verda,plans=decisions:verda")
    monkeypatch.setenv("VERDA_READER_URL", "https://reader.example")
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setenv("QUESTION_PARSER", "templates")
    monkeypatch.setenv("ANSWER_PRIOR", "none")
    monkeypatch.setenv("DECISIONS_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setattr(composition, "HttpReaderClient", FakeVerdaNoToilet)
    monkeypatch.setattr(composition, "DecisionsClient", FakeDecisions)
    assert build_pipeline(Settings(), dataset).confidence is None  # off by default

    monkeypatch.setenv("DECISIONS_CONFIDENCE", "true")
    built, calls = len(FakeDecisions.built), FakeDecisions.calls
    pipeline = build_pipeline(Settings(), dataset)
    assert len(FakeDecisions.built) == built + 1  # one client for the swap and the confidence
    pipeline.ingest([PNG], ExtractionV1Writer(out, {PNG: "dev"}))
    answers: list[Answer] = []
    question = "How many toilet bowls (WC seats) are drawn on this floor plan?"
    pipeline.answer_questions(
        [Question(id=1, file=PNG, text=question)], ExtractionV1Reader(out), Sink(answers)
    )
    assert [(a.answer, a.confidence) for a in answers] == [(1, 0.99)]
    assert FakeDecisions.calls == calls + 1  # the page was paid for once


class Sink:
    def __init__(self, answers: list[Answer]) -> None:
        self.answers = answers

    def write(self, answer: Answer) -> None:
        self.answers.append(answer)


class FakeRegion(WholePagePlan):
    """Stands in for RegionDetector: records the folders it was built from."""

    built: ClassVar[list[tuple[Path, Path | None]]] = []

    @classmethod
    def from_folders(cls, files: object, detector: Path, region: Path | None) -> "FakeRegion":
        FakeRegion.built.append((detector, region))
        return cls()


def test_the_region_source_is_built_from_the_detector_arm_and_region_model_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(composition, "RegionDetector", FakeRegion)
    monkeypatch.setenv("EXTRACTOR_RASTER", "composite")
    monkeypatch.setenv("RASTER_COMPONENTS", "elements=region:arm-x,plans=region:arm-x")
    monkeypatch.setenv("REGION_MODEL_DIR", str(tmp_path / "unet"))
    build_pipeline(Settings(), tmp_path)
    assert FakeRegion.built == [(composition.DETECTOR_DIR / "arm-x", tmp_path / "unet")]  # once
    monkeypatch.setenv("REGION_MODEL_DIR", "")  # no region filter
    build_pipeline(Settings(), tmp_path)
    assert FakeRegion.built[-1] == (composition.DETECTOR_DIR / "arm-x", None)
    monkeypatch.setenv("RASTER_COMPONENTS", "elements=region:../x,plans=one-plan")
    with pytest.raises(InvalidInputError, match="not a path inside"):
        build_pipeline(Settings(), tmp_path)

"""What the count arbiter read is kept with the drawing (`count_arbiter`): written by `arbiter-t1`,
carried by the raster composite to the drawing, absent from every dump when it did not run, and
read back by the answer's local gate (`reading_of`)."""

import io
import json
from pathlib import Path
from typing import Any

import numpy as np
from jsonschema import Draft202012Validator
from PIL import Image
from test_raster_composite import SCHEMAS

from app.adapters.count_arbiter import ArbiterCountExtractor, L1PageCounts
from app.adapters.extraction_v1 import ExtractionV1Reader, ExtractionV1Writer
from app.adapters.raster import assemble, parse_components
from app.core.answering.local_gate import reading_of
from app.core.drawing.model import ArbiterReading, Drawing, Element, Page, Plan, Scale
from app.core.pipeline.count_arbiter import (
    ArbiterModel,
    FamilyModel,
    count_arbiter_reading,
)
from app.core.pipeline.ingest import ingest
from app.core.pipeline.model import DrawingFile, Extracted, Measurement, Sheet

PNG = "data/cubicasa5k/x.png"
FILE = DrawingFile(path=PNG, size=1, sha256="0" * 64, kind="png")
SHEET = Sheet(file=FILE, pages=(Page(page=1, width=40, height=30, unit="px"),))
PLAN = Plan(id="p1", page=1, box=(0.1, 0.1, 0.9, 0.9))
HEADS = ("door", "toilet", "plan", "room:wc")


class Files:
    def read(self, path: str) -> bytes:
        buffer = io.BytesIO()
        Image.new("RGB", (20, 10), "black").save(buffer, "PNG")
        return buffer.getvalue()


class Read:
    """A reader with fixed elements: `counts` per class, scores descending from 0.9."""

    def __init__(self, counts: dict[str, int], **more: Any) -> None:
        elements = tuple(
            Element.model_validate(
                {"id": f"{kind}{n}", "class": kind, "page": 1, "box": (0.2, 0.2, 0.3, 0.3),
                 "attrs": {"score": round(0.9 - n / 100, 3)}}
            )
            for kind, count in counts.items()
            for n in range(count)
        )  # fmt: skip
        self.found = Extracted(
            method="detector", scale=Scale(status="no_scale"), plans=(PLAN,), elements=elements,
            **more,
        )  # fmt: skip

    def extract(self, source: DrawingFile, sheet: Sheet) -> Extracted:
        return self.found


class Session:
    """L1's ONNX session: fixed logits per head (3 counts each)."""

    def get_inputs(self) -> list[Any]:
        return [type("Named", (), {"name": "page"})()]

    def get_outputs(self) -> list[Any]:
        return []

    def run(self, output_names: Any, input_feed: Any) -> list[np.ndarray]:
        return [np.array([[0.0, np.log(3.0), 0.0]], np.float32) for _ in HEADS]


def arbiter() -> ArbiterCountExtractor:
    """T1 with a fit for toilet only, which follows the one-view count (feature 12)."""
    coef = [0.0] * 19
    coef[12] = 5.0
    fit = FamilyModel((0.0,) * 19, (1.0,) * 19, tuple(coef), 0.0)
    model = ArbiterModel({"toilet": fit}, {"toilet": {1: 0.5}})
    l1 = L1PageCounts(Session(), HEADS, 16, dict.fromkeys(HEADS, 1.0))
    return ArbiterCountExtractor(Read({"toilet": 1}), Read({"toilet": 2}), l1, model, Files())


def test_the_arbiter_keeps_l1s_probabilities_and_its_p_per_family() -> None:
    found = arbiter().extract(FILE, SHEET)
    assert found.count_arbiter is not None
    assert list(found.count_arbiter) == list(HEADS)  # every L1 head
    for reading in found.count_arbiter.values():
        assert np.allclose(reading.probs, [0.2, 0.6, 0.2])
    assert found.count_arbiter["toilet"].p is not None and found.count_arbiter["toilet"].p > 0.9
    assert found.count_arbiter["door"].p is None  # no fit for door: no pick
    assert found.count_arbiter["plan"].p is None and found.count_arbiter["room:wc"].p is None
    assert sum(e.class_ == "toilet" for e in found.elements) == 2  # and it still counts


def test_the_composite_carries_it_from_the_element_source_only() -> None:
    kept = {"door": ArbiterReading(probs=(0.1, 0.9), p=0.8)}
    readers = {"t1": Read({"door": 1}, count_arbiter=kept), "plain": Read({"door": 1})}
    found = assemble(parse_components("elements=t1,plans=plain"), readers.__getitem__).extract(
        FILE, SHEET
    )
    assert found.count_arbiter == kept
    without = assemble(parse_components("elements=plain,plans=t1"), readers.__getitem__)
    assert without.extract(FILE, SHEET).count_arbiter is None  # plans alone carry no counts


class Sheets:
    """What `ingest` needs around the extractor: the PNG's bytes, its page, no sources, no
    second count, and the drawings it writes."""

    def __init__(self) -> None:
        self.drawings: list[Drawing] = []

    def read(self, path: str) -> bytes:
        return b"\x89PNG\r\n\x1a\n" + b"synthetic"

    def sources(self, path: str) -> list[str]:
        return []

    def pages(self, file: DrawingFile) -> tuple[Page, ...]:
        return SHEET.pages

    def measure(self, source: DrawingFile, sheet: Sheet) -> list[Measurement]:
        return []

    def write(self, drawing: Drawing) -> None:
        self.drawings.append(drawing)


def ingested(extractor: Read) -> Drawing:
    around = Sheets()
    ingest(
        [PNG],
        files=around,
        finder=around,
        pages=around,
        extractors={"raster": extractor},
        second_counter=around,
        sink=around,
    )
    (written,) = around.drawings
    return written


def test_ingest_writes_it_into_the_drawing_and_nothing_when_it_did_not_run() -> None:
    kept = {"toilet": ArbiterReading(probs=(0.25, 0.75), p=0.9)}
    assert ingested(Read({"toilet": 1}, count_arbiter=kept)).count_arbiter == kept
    assert ingested(Read({"toilet": 1})).count_arbiter is None


def drawing(**more: Any) -> Drawing:
    return Drawing(file=PNG, pages=SHEET.pages, scale=Scale(status="no_scale"), **more)


def test_a_drawing_without_it_is_dumped_as_before_and_one_with_it_round_trips(
    tmp_path: Path,
) -> None:
    assert "count_arbiter" not in drawing().model_dump(mode="json", by_alias=True)
    assert "count_arbiter" not in drawing().model_dump_json(by_alias=True)
    kept = {
        "toilet": ArbiterReading(probs=(0.25, 0.75), p=0.9),
        "plan": ArbiterReading(probs=(1.0,)),
    }
    body = json.loads(drawing(count_arbiter=kept).model_dump_json(by_alias=True))
    assert body["count_arbiter"]["toilet"] == {"probs": [0.25, 0.75], "p": 0.9}
    assert Drawing.model_validate(body).count_arbiter == kept

    ExtractionV1Writer(tmp_path, {PNG: "dev"}).write(drawing(count_arbiter=kept))
    (written,) = tmp_path.rglob("*.json")
    schema = json.loads((SCHEMAS / "extraction_v1.schema.json").read_text(encoding="utf-8"))
    Draft202012Validator(schema).validate(json.loads(written.read_text(encoding="utf-8")))
    read_back = ExtractionV1Reader(tmp_path).drawing(PNG)
    assert read_back is not None and read_back.count_arbiter == kept


def test_the_local_gate_reads_it_from_the_drawing_unless_given() -> None:
    kept = {"toilet": ArbiterReading(probs=(0.25, 0.75), p=0.9)}
    stored = drawing(count_arbiter=kept)
    assert count_arbiter_reading(stored, "toilet") == kept["toilet"]
    assert count_arbiter_reading(stored, "door") is None
    assert count_arbiter_reading(drawing(), "toilet") is None
    reading = reading_of(stored, "toilet", 1)
    assert (tuple(reading.probs or ()), reading.arbiter_p) == ((0.25, 0.75), 0.9)
    given = reading_of(stored, "toilet", 1, probs=[0.5, 0.5], arbiter_p=0.4)
    assert (given.probs, given.arbiter_p) == ([0.5, 0.5], 0.4)
    assert reading_of(drawing(), "toilet", 1).probs is None

"""`vlm` (DISCIPLINE_PICTURES=gemini): one Carbon call per page reads the legend and the symbols.
A fake client gives the replies; no key, no network, no partner data."""

import io
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from PIL import Image

from app.adapters.discipline_pictures.gemini import GeminiPictureReader, reading_of
from app.adapters.discipline_pictures.lane import PictureLane, PictureSheets
from app.adapters.raster_ocr.gemini import GeminiError, NoAnswerError
from app.core.drawing.model import Page
from app.core.ifc_facts import Spot
from app.core.picture_facts import HELD, PictureReading, Sighting
from app.core.pipeline.model import DrawingFile, Sheet


def reply(found: Any, thought: str | None = None) -> dict[str, Any]:
    parts = [{"text": thought, "thought": True}] if thought else []
    parts.append({"text": json.dumps(found)})
    return {
        "candidates": [{"content": {"parts": parts}}],
        "usageMetadata": {"promptTokenCount": 1000, "candidatesTokenCount": 500},
    }


LEGEND = [
    {"label": "Radiator", "line": False, "box": [100, 900, 120, 920]},
    {"label": "Supply pipe", "line": True, "box": [130, 900, 140, 960]},
    {"label": "Valve", "line": False, "box": [150, 900, 170, 920]},
]


def test_the_reply_becomes_the_legend_and_its_symbols_boxes() -> None:
    reading = reading_of(
        reply(
            {
                "legend": LEGEND,
                "symbols": [
                    {"label": "Radiator", "boxes": [[500, 100, 520, 120], [200, 300, 220, 320]]},
                    {"label": "Valve", "boxes": [[600, 400, 610, 410]]},
                    {"label": "Pump", "boxes": [[10, 10, 20, 20]]},  # not in the legend: dropped
                    {"label": "Supply pipe", "boxes": [[1, 1, 5, 5]]},  # a line style: no symbol
                ],
            },
            thought="first the legend...",
        )
    )
    assert reading.reader == "vlm" and reading.read == ("Radiator", "Valve")
    assert [(e.label, e.line) for e in reading.legend or ()] == [
        ("Radiator", False), ("Supply pipe", True), ("Valve", False)
    ]  # fmt: skip
    assert [s.label for s in reading.sightings] == ["Radiator", "Radiator", "Valve"]
    assert reading.sightings[0].spot.box == (0.3, 0.2, 0.32, 0.22)  # x0, y0, x1, y1 fractions


def test_malformed_boxes_are_dropped_and_no_legend_reads_nothing() -> None:
    reading = reading_of(
        reply(
            {"legend": LEGEND, "symbols": [{"label": "Valve", "boxes": [[1, 2, 3], [5, 5, 5, 5]]}]}
        )
    )
    assert reading.sightings == ()
    empty = reading_of(reply({"legend": [], "symbols": []}))
    assert empty.legend is None and empty.read == () and "no legend" in empty.notes[0]


def test_a_reply_that_is_not_the_asked_json_is_refused() -> None:
    with pytest.raises(ValueError, match="not the asked JSON"):
        reading_of({"candidates": [{"content": {"parts": [{"text": "sorry"}]}}]})


class Files:
    def read(self, path: str) -> bytes:
        buffer = io.BytesIO()
        Image.new("RGB", (400, 300), "white").save(buffer, "PNG")
        return buffer.getvalue()


class Client:
    def __init__(self, answer: dict[str, Any] | Exception) -> None:
        self.answer = answer
        self.calls = 0

    def generate(self, jpeg: bytes, prompt: str, schema: dict, max_tokens: int) -> dict[str, Any]:
        self.calls += 1
        if isinstance(self.answer, Exception):
            raise self.answer
        return self.answer


def sheet() -> tuple[DrawingFile, Sheet]:
    source = DrawingFile(path="h.png", size=1, sha256="0" * 64, kind="png")
    return source, Sheet(file=source, pages=(Page(page=1, width=400, height=300, unit="px"),))


def reader(client: Client, tmp_path: Path) -> GeminiPictureReader:
    return GeminiPictureReader(Files(), client, tmp_path / "replies")  # type: ignore[arg-type]


def test_the_reader_sends_the_page_once_and_charges_the_reply(tmp_path: Path) -> None:
    client = Client(
        reply({"legend": LEGEND, "symbols": [{"label": "Valve", "boxes": [[1, 1, 9, 9]]}]})
    )
    reading = reader(client, tmp_path).read(*sheet())
    assert client.calls == 1 and len(reading.sightings) == 1 and reading.cost_usd > 0


def test_a_page_is_paid_for_once_the_reply_is_cached(tmp_path: Path) -> None:
    client = Client(
        reply({"legend": LEGEND, "symbols": [{"label": "Valve", "boxes": [[1, 1, 9, 9]]}]})
    )
    first = reader(client, tmp_path).read(*sheet())
    again = reader(client, tmp_path).read(*sheet())  # a re-ingest: a new reader, the same cache
    assert client.calls == 1
    assert again.sightings == first.sightings and again.cost_usd == 0.0


def test_a_failed_call_raises_and_caches_nothing(tmp_path: Path) -> None:
    client = Client(NoAnswerError("HTTP 503"))
    with pytest.raises(GeminiError, match="HTTP 503"):
        reader(client, tmp_path).read(*sheet())
    assert not (tmp_path / "replies").exists()


def test_a_reply_that_is_not_the_asked_json_raises_and_is_not_cached(tmp_path: Path) -> None:
    client = Client({"candidates": [{"content": {"parts": [{"text": "sorry"}]}}]})
    with pytest.raises(GeminiError, match="not the asked JSON"):
        reader(client, tmp_path).read(*sheet())
    client.answer = reply({"legend": LEGEND, "symbols": []})
    reader(client, tmp_path).read(*sheet())
    assert client.calls == 2  # the bad reply was not kept


def test_float_boxes_are_read() -> None:
    reading = reading_of(
        reply(
            {"legend": LEGEND, "symbols": [{"label": "Valve", "boxes": [[600.0, 400.5, 610, 410]]}]}
        )
    )
    assert len(reading.sightings) == 1


class Inner:
    def extract(self, source: Any, sheet: Any) -> str:
        return "drawing"


def lane(client: Client, tmp_path: Path) -> tuple[PictureLane, PictureSheets]:
    sheets = PictureSheets(Files(), tmp_path / "sheets")  # type: ignore[arg-type]
    legend = SimpleNamespace(
        legend=lambda source, sheet: None,
        scale=lambda source, sheet: SimpleNamespace(m_per_unit=None),
    )
    made = PictureLane(
        Inner(),  # type: ignore[arg-type]
        Files(),  # type: ignore[arg-type]
        lambda path: None,
        sheets,
        legend,  # type: ignore[arg-type]
        reader(client, tmp_path),
    )
    return made, sheets


def named_sheet() -> tuple[DrawingFile, Sheet]:
    source = DrawingFile(path="H-101 heating.png", size=1, sha256="1" * 64, kind="png")
    return source, Sheet(file=source, pages=(Page(page=1, width=400, height=300, unit="px"),))


def test_after_a_failed_call_the_lane_keeps_the_sheet_it_had(tmp_path: Path) -> None:
    good = reply({"legend": LEGEND, "symbols": [{"label": "Valve", "boxes": [[1, 1, 9, 9]]}]})
    made, sheets = lane(Client(good), tmp_path)
    made.extract(*named_sheet())
    kept = sheets.sheet("1" * 64)
    assert kept is not None and kept.facts
    for path in (tmp_path / "replies").glob("*.json"):
        path.unlink()  # the cached reply gone: the next read calls again, and fails
    failing, _ = lane(Client(NoAnswerError("HTTP 503")), tmp_path)
    assert failing.extract(*named_sheet()) == "drawing"  # ingest goes on
    assert sheets.sheet("1" * 64) == kept  # not overwritten by a sheet without symbols


class Reads:
    """A fake reader: the given sightings of one label."""

    def __init__(self, reader: str, label: str, boxes: list[tuple[float, float, float, float]]):
        self.reading = PictureReading(
            reader=reader,
            legend=None,
            read=(label,),
            sightings=tuple(
                Sighting(label=label, spot=Spot(page=1, box=b, reader=reader)) for b in boxes
            ),
        )

    def read(self, source: Any, sheet: Any) -> PictureReading:
        return self.reading


def checked_lane(first: Reads, second: Reads, tmp_path: Path) -> PictureSheets:
    sheets = PictureSheets(Files(), tmp_path / "sheets")  # type: ignore[arg-type]
    legend = SimpleNamespace(
        legend=lambda source, sheet: None,
        scale=lambda source, sheet: SimpleNamespace(m_per_unit=None),
    )
    PictureLane(
        Inner(),  # type: ignore[arg-type]
        Files(),  # type: ignore[arg-type]
        lambda path: None,
        sheets,
        legend,  # type: ignore[arg-type]
        first,
        check=second,
    ).extract(*named_sheet())
    return sheets


BOXES = [(0.1, 0.1, 0.12, 0.12), (0.5, 0.5, 0.52, 0.52)]


def test_a_count_the_second_reader_confirms_is_not_held(tmp_path: Path) -> None:
    sheets = checked_lane(Reads("vlm", "Valve", BOXES), Reads("template", "Valve", BOXES), tmp_path)
    kept = sheets.sheet("1" * 64)
    assert kept is not None
    counts = [f for f in kept.facts if f.topic == "valve.count" and f.subject == "Valve"]
    assert counts and not any(f.source.endswith(HELD) for f in counts)


def test_a_count_the_second_reader_disputes_or_did_not_read_is_held(tmp_path: Path) -> None:
    for n, second in enumerate(
        (Reads("template", "Valve", BOXES[:1]), Reads("template", "Ventil X", BOXES))
    ):
        sheets = checked_lane(Reads("vlm", "Valve", BOXES), second, tmp_path / str(n))
        kept = sheets.sheet("1" * 64)
        assert kept is not None
        counts = [f for f in kept.facts if f.topic == "valve.count" and f.subject == "Valve"]
        assert counts and all(f.source.endswith(HELD) for f in counts)
        assert not [f for f in kept.facts if f.subject == "Ventil X"]  # the check adds no facts

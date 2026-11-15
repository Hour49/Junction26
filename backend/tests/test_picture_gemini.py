"""`vlm` (DISCIPLINE_PICTURES=gemini): one Carbon call per page reads the legend and the symbols.
A fake client gives the replies; no key, no network, no partner data."""

import io
import json
from typing import Any

from PIL import Image

from app.adapters.discipline_pictures.gemini import GeminiPictureReader, reading_of
from app.adapters.raster_ocr.gemini import NoAnswerError
from app.core.drawing.model import Page
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


def test_a_reply_that_is_not_the_asked_json_reads_nothing() -> None:
    answer = {"candidates": [{"content": {"parts": [{"text": "sorry"}]}}]}
    reading = reading_of(answer)
    assert reading.sightings == () and "not the asked JSON" in reading.notes[0]


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


def test_the_reader_sends_the_page_once_and_charges_the_reply() -> None:
    client = Client(
        reply({"legend": LEGEND, "symbols": [{"label": "Valve", "boxes": [[1, 1, 9, 9]]}]})
    )
    reading = GeminiPictureReader(Files(), client).read(*sheet())  # type: ignore[arg-type]
    assert client.calls == 1 and len(reading.sightings) == 1 and reading.cost_usd > 0


def test_no_answer_reads_nothing_and_says_why() -> None:
    client = Client(NoAnswerError("HTTP 503"))
    reading = GeminiPictureReader(Files(), client).read(*sheet())  # type: ignore[arg-type]
    assert reading.sightings == () and "HTTP 503" in reading.notes[0]

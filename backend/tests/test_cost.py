"""R1b-4-2: paid model calls are recorded where cost_usd is summed (the stage, the file, the
project), not only logged."""

import io
import json
from pathlib import Path

import pytest
from PIL import Image

import app.composition as composition
from app.adapters.decisions.client import DecisionsClient
from app.adapters.decisions_kind import KindUnavailable
from app.composition import build_ingest
from app.core import cost
from app.core.drawing.model import Drawing
from app.core.ingest.judge import pipeline_stages
from app.core.ingest.timing import CollectingSink, StageClock, TimedExtractor
from app.core.pipeline.model import DrawingFile, Extracted, Sheet
from app.settings import Settings


def test_the_decisions_client_charges_what_it_logs() -> None:
    reply = {"answers": {}, "usage": {"total_input_tokens": 3151}}
    client = DecisionsClient("k", 5.0, lambda body, key, timeout: (200, json.dumps(reply).encode()))
    before = cost.spent()
    client.decide({"q": 1})
    assert cost.spent() - before == pytest.approx(3151 * 0.10 / 1e6)


class Paid:
    """An extractor whose model call costs $0.25."""

    def extract(self, source: DrawingFile, sheet: Sheet) -> Extracted:
        cost.charge(0.25)
        return Extracted.model_construct()


def test_a_stage_records_what_its_calls_charged() -> None:
    timer = StageClock(clock=lambda: 0.0)
    source = DrawingFile(path="a.png", size=1, sha256="0" * 64, kind="png")
    sheet = Sheet(file=source, pages=())
    TimedExtractor(Paid(), timer).extract(source, sheet)
    CollectingSink(timer).write(Drawing.model_construct(file="a.png"))  # takeoff: no call
    assert timer.usd == {"a.png": {"extract": 0.25}}
    (stage,) = pipeline_stages(["extract: read 3 doors"], {"extract": 1.0}, timer.usd["a.png"])
    assert stage.cost_usd == 0.25


class PaidKind:
    """A sheet-kind reader whose call costs $0.125 and finds no answer."""

    def __init__(self, *args: object) -> None:
        pass

    def read(self, data: bytes) -> KindUnavailable:
        cost.charge(0.125)
        return KindUnavailable("kind signal not available: HTTP 503")


def drawing_png() -> bytes:
    image = Image.new("RGB", (400, 300), "white")
    image.paste((0, 0, 0), (50, 50, 350, 60))
    buffer = io.BytesIO()
    image.save(buffer, "PNG")
    return buffer.getvalue()


def test_the_identify_stage_and_the_project_record_the_kind_call(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(composition, "KindReader", PaidKind)
    settings = Settings(
        _env_file=None,  # pyright: ignore[reportCallIssue]
        decisions_kind=True,
        gemini_api_key="test-key",  # pyright: ignore[reportArgumentType]
    )
    ingest = build_ingest(settings, tmp_path / "projects", background=False)
    status = ingest.status(ingest.start("plan.png", drawing_png()))
    (file,) = status.files
    identify = next(s for s in ingest.trace(status.id, file.id).stages if s.stage == "identify")
    ingest.close()
    assert (identify.cost_usd, file.cost_usd, status.cost_usd) == (0.125, 0.125, 0.125)

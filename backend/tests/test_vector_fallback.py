"""VECTOR_FALLBACK=raster (local-dec BK S1, 2026-11-14): a drawn PDF the vector reader has no
sheet style for (a Revit or AutoCAD plot: 584 of opening_design's 587 drawn PDFs) is read on the
raster route as the image of its page, flagged, so none of its answers is certified. Off (the
default), it stays on the vector route and reads nothing, as before."""

import io
import json
from pathlib import Path

import pytest
from pdf_sheets import SheetPdf, rect
from PIL import Image
from test_scan_images import DETECTOR, Files, Reader, Session
from test_vector_pdf import swiss_sheet

from app import composition
from app.adapters import raster_detector
from app.adapters.answer_v1 import AnswerV1Writer
from app.adapters.archive.probe import is_scanned_pdf
from app.adapters.extraction_v1 import ExtractionV1Reader, ExtractionV1Writer
from app.adapters.vector_pdf.unruled import Unruled
from app.composition import build_answering, build_ingest, build_pipeline
from app.core.answering.model import Question
from app.core.ingest.judge import UNRULED_FLAG, reading_flags
from app.settings import Settings

PDF = "data/plots/plan.pdf"


def plot() -> bytes:
    """A drawn PDF in no style the vector reader knows: twelve plain stroked boxes."""
    sheet = SheetPdf(600, 400)
    for n in range(12):
        x, y = 40 + 45 * n, 60 + 10 * (n % 3)
        sheet.path(rect(x, y, x + 30, y + 30), width=1.0)
    return sheet.pdf()


def test_unruled_is_a_drawn_pdf_that_matches_no_style() -> None:
    unruled = Unruled()
    assert not is_scanned_pdf(plot()) and unruled(plot())
    assert not unruled(swiss_sheet().pdf())  # the vector reader has rules for it
    assert not unruled(b"\x89PNG...")  # not a PDF
    assert not unruled(b"%PDF-1.7 broken")  # pdfium can't open it: left where it was routed


def detector(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The composite raster reader on a stand-in detector that finds one door on any canvas;
    it opens the file as an image, so given the PDF it fails."""
    models = tmp_path / "models" / "C"
    models.mkdir(parents=True)
    facts = {k: DETECTOR[k] for k in ("format", "side", "classes", "element_class")}
    (models / "model.json").write_text(json.dumps(facts))
    (models / "detector.json").write_text(json.dumps(DETECTOR))
    monkeypatch.setattr(composition, "DETECTOR_DIR", tmp_path / "models")
    monkeypatch.setattr(raster_detector, "onnx_session", lambda path: Session())
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("EXTRACTOR_RASTER", "composite")
    monkeypatch.setenv("EXTRACTOR_VECTOR", "pdf")
    monkeypatch.setenv("RASTER_COMPONENTS", "elements=detector:C,plans=detector:C")


@pytest.mark.parametrize("fallback", ["off", "raster"])
def test_the_fallback_reads_an_unruled_plot_on_the_raster_route(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fallback: str
) -> None:
    detector(tmp_path, monkeypatch)
    monkeypatch.setenv("VECTOR_FALLBACK", fallback)
    dataset = tmp_path / "dataset"
    (dataset / PDF).parent.mkdir(parents=True)
    (dataset / PDF).write_bytes(plot())
    pipeline = build_pipeline(Settings(), dataset, lambda path: "pdf_vector")
    report = pipeline.ingest([PDF], ExtractionV1Writer(tmp_path / "out", {PDF: "dev"}))
    (sheet,) = report.sheets
    if fallback == "off":  # as before: the vector route, which reads nothing here
        assert sheet.route == "vector" and "door" not in dict(sheet.takeoff)
    else:
        assert sheet.route == "raster" and dict(sheet.takeoff)["door"] == 1


def test_a_pdf_the_vector_reader_has_rules_for_stays_on_the_vector_route(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    detector(tmp_path, monkeypatch)
    monkeypatch.setenv("VECTOR_FALLBACK", "raster")
    dataset = tmp_path / "dataset"
    (dataset / PDF).parent.mkdir(parents=True)
    (dataset / PDF).write_bytes(swiss_sheet().pdf())
    pipeline = build_pipeline(Settings(), dataset, lambda path: "pdf_vector")
    report = pipeline.ingest([PDF], ExtractionV1Writer(tmp_path / "out", {PDF: "dev"}))
    (sheet,) = report.sheets
    assert sheet.route == "vector" and dict(sheet.takeoff)["room:kitchen"] == 1


@pytest.mark.parametrize("fallback", ["off", "raster"])
def test_an_uploaded_plot_read_by_the_fallback_is_flagged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fallback: str
) -> None:
    """Through the real upload: the file's route, its state and the flag its answers carry."""
    detector(tmp_path, monkeypatch)
    monkeypatch.setenv("VECTOR_FALLBACK", fallback)
    ingest = build_ingest(Settings(), tmp_path / "projects", background=False)
    names = ingest._names  # pyright: ignore[reportPrivateUsage]
    assert names.get("vector_fallback") == (None if fallback == "off" else "raster")
    project = ingest.start("plan.pdf", plot())
    (file,) = ingest.status(project).files
    assert file.kind == "pdf_vector" and file.state == "flagged"
    if fallback == "off":
        assert file.route == "vector" and "read nothing" in file.reason
        assert UNRULED_FLAG not in file.reason
    else:
        assert file.route == "raster" and file.reason.startswith(UNRULED_FLAG)
        assert file.takeoff["door"] == 1
        stages = ingest.trace(project, file.id).stages
        assert "VECTOR_FALLBACK" in next(stage.did for stage in stages if stage.stage == "route")


def test_the_flag_is_a_reading_flag_so_no_answer_is_certified() -> None:
    assert reading_flags("pdf_vector", None, unruled=True) == (UNRULED_FLAG,)
    assert reading_flags("pdf_vector", None) == ()


def test_the_answer_confidence_asks_about_the_render_of_an_unruled_plot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reader = Reader()
    monkeypatch.setattr(composition, "decisions_reader", lambda settings: reader)
    answering = build_answering(Settings(decisions_confidence=True, vector_fallback="raster"))
    assert answering.confidence is not None
    answering.confidence(Files({PDF: plot()})).probability(PDF, "door", 1)
    (asked,) = reader.asked
    with Image.open(io.BytesIO(asked)) as image:
        assert image.format == "PNG"


def test_the_cli_never_certifies_an_answer_on_a_plot_the_fallback_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """codecheck's review-283 M1 repro: with DECISIONS_CONFIDENCE and a GATE_POLICY, the
    golden/answer CLI path gave the plot's door count `sure: true`; ingest and ask flag it."""
    detector(tmp_path, monkeypatch)
    monkeypatch.setattr(composition, "decisions_reader", lambda settings: Reader())
    gate = tmp_path / "gate.json"
    gate.write_text(json.dumps({
        "schema": "gate_policy_v1", "part": "val", "split_sha256": "0" * 64,
        "families": {"door": {"threshold": 0.5, "signal": "g1main"}},
    }))  # fmt: skip
    dataset = tmp_path / "dataset"
    (dataset / PDF).parent.mkdir(parents=True)
    (dataset / PDF).write_bytes(plot())
    settings = Settings(vector_fallback="raster", decisions_confidence=True, gate_policy=str(gate))
    pipeline = build_pipeline(settings, dataset, lambda path: "pdf_vector")
    out = tmp_path / "extraction"
    out.mkdir()
    (sheet,) = pipeline.ingest([PDF], ExtractionV1Writer(out, {PDF: "dev"})).sheets
    assert sheet.route == "raster"
    answers = tmp_path / "answers.jsonl"
    pipeline.answer_questions(
        [Question(id=1, file=PDF, text="How many doors are there?")],
        ExtractionV1Reader(out),
        AnswerV1Writer(answers),
    )
    (answer,) = [json.loads(line) for line in answers.read_text().splitlines()]
    assert answer["answer"] == 1 and answer["confidence"] == 1.0
    assert answer.get("sure") is None  # read as an image without reading rules: no verdict

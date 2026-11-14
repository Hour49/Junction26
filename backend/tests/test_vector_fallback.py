"""VECTOR_FALLBACK=raster (local-dec BK S1, 2026-11-14): a drawn PDF the vector reader has no
sheet style for (a Revit or AutoCAD plot: 584 of opening_design's 587 drawn PDFs) is read on the
raster route as the image of its page, flagged, so none of its answers is certified. Off (the
default), it stays on the vector route and reads nothing, as before."""

import dataclasses
import io
import json
from pathlib import Path

import numpy as np
import pypdfium2
import pytest
from pdf_sheets import SheetPdf, rect
from PIL import Image
from test_pdf_tables import door_schedule
from test_scan_images import DETECTOR, Files, Reader, Session
from test_vector_pdf import ifc_sheet, swiss_sheet

from app import composition
from app.adapters import raster_detector
from app.adapters.answer_v1 import AnswerV1Writer
from app.adapters.archive.probe import is_scanned_pdf
from app.adapters.extraction_v1 import ExtractionV1Reader, ExtractionV1Writer
from app.adapters.vector_pdf import STYLES, objects
from app.adapters.vector_pdf.objects import FILL_NONE, read_page
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
    assert not unruled(ifc_sheet().pdf())
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
    assert names.get("vector_fallback") == (None if fallback == "off" else "raster:v2")
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
        routes = [stage for stage in stages if stage.stage == "route"]
        assert [stage.output for stage in routes] == ["vector", "raster"]  # read, then fell back
        assert "VECTOR_FALLBACK" in routes[-1].did


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


def test_the_unruled_check_reads_only_filled_paths_not_the_whole_page(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """review-283 S2: reading the whole page held the PDFium lock up to 5 s on a Revit plot. The
    check gives the vector reader's own answer without it."""
    sheets = {"plot": plot(), "swiss": swiss_sheet().pdf(), "ifc": ifc_sheet().pdf()}
    read = {
        name: not any(style.matches(read_page(data)) for style in STYLES)
        for name, data in sheets.items()
    }
    assert read == {"plot": True, "swiss": False, "ifc": False}

    def whole(data: bytes, index: int) -> None:
        raise AssertionError("read the whole page")

    monkeypatch.setattr(objects, "_read_page", whole)
    assert {name: Unruled()(data) for name, data in sheets.items()} == read


def test_every_style_is_drawn_with_filled_paths() -> None:
    """What lets the check pass a path drawn without a fill after one call."""
    for data in (swiss_sheet().pdf(), ifc_sheet().pdf()):
        styled = [p for p in read_page(data).paths if any(s.matches_path(p) for s in STYLES)]
        assert styled
        for path in styled:
            unfilled = dataclasses.replace(path, fill_mode=FILL_NONE)
            assert not any(style.matches_path(unfilled) for style in STYLES)


class PlanOnly(Session):
    """A detector that finds a plan and nothing on it: what Carbon and the detector give on a
    wall-detail or cabinet sheet (think-local r10 line 3: "1 floor plan" on 3 such sheets)."""

    def run(self, names: list[str], feed: dict) -> list[np.ndarray]:
        found = {
            "labels": np.array([[2]]),
            "boxes": np.array([[[0, 0, 100, 100]]], dtype=np.float32),
            "scores": np.array([[0.9]], dtype=np.float32),
        }
        return [found[name] for name in names]


def upload(tmp_path: Path, name: str, data: bytes) -> list:
    """The project's files after a real upload with VECTOR_FALLBACK=raster."""
    ingest = build_ingest(
        Settings(vector_fallback="raster"), tmp_path / "projects", background=False
    )
    return list(ingest.status(ingest.start(name, data)).files)


def test_a_page_with_no_element_and_no_room_still_reads_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """r10 fix 1: the image reading found a plan and nothing on it, so the file keeps the vector
    route's reading (nothing), not "1 floor plan" on a flagged page."""
    detector(tmp_path, monkeypatch)
    monkeypatch.setattr(raster_detector, "onnx_session", lambda path: PlanOnly())
    (file,) = upload(tmp_path, "plan.pdf", plot())
    assert file.route == "vector" and "read nothing" in file.reason
    assert UNRULED_FLAG not in file.reason and "plan" not in file.takeoff


def two_pages() -> bytes:
    """A set of two plot pages, both drawn: ingest reads page 2 as `plan#p2.pdf`."""
    document = pypdfium2.PdfDocument.new()
    for _ in range(2):
        document.import_pages(pypdfium2.PdfDocument(plot()))
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def test_only_page_1_of_an_upload_falls_back(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """r10 fix 2: a set's later pages keep the vector route, so an upload pays one image read."""
    detector(tmp_path, monkeypatch)
    files = {file.path: file for file in upload(tmp_path, "plan.pdf", two_pages())}
    assert set(files) == {"plan.pdf", "plan#p2.pdf"}
    assert files["plan.pdf"].route == "raster" and files["plan.pdf"].takeoff["door"] == 1
    assert files["plan#p2.pdf"].route == "vector" and "read nothing" in files["plan#p2.pdf"].reason


def test_a_drawn_pdf_whose_schedule_is_read_keeps_the_vector_route(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """r10 fix 3: the vector route read its schedule, so it is not read again as an image nor
    flagged (golden's A-801 kept its answers but lost their level)."""
    detector(tmp_path, monkeypatch)
    sheet = SheetPdf(600, 400)
    door_schedule(sheet)
    for n in range(12):
        x, y = 40 + 45 * n, 260 + 10 * (n % 3)
        sheet.path(rect(x, y, x + 30, y + 30), width=1.0)
    data = sheet.pdf()
    assert Unruled()(data)  # no reading rules: the fallback would read it before
    (file,) = upload(tmp_path, "schedule.pdf", data)
    assert file.route == "vector" and file.state == "ready" and UNRULED_FLAG not in file.reason

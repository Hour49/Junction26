"""A scanned PDF on the raster route (app/adapters/scan_images.py): every raster reader reads the
image of its page, rendered once, instead of the PDF bytes it could not open (local-dec BK S0,
2026-11-14: "failed at extract: UnidentifiedImageError" on opening_design's scanned PDFs)."""

import io
import json
import threading
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from PIL import Image

from app import composition
from app.adapters import raster_detector, scan_images
from app.adapters.archive.probe import is_scanned_pdf
from app.adapters.decisions.g1main import FAMILIES, CountDist, PageCounts
from app.adapters.extraction_v1 import ExtractionV1Writer
from app.adapters.page_render import MAX_PIXELS
from app.adapters.page_sizes import PageSizes
from app.adapters.printed_scale import PrintedScale, stated_dpi
from app.adapters.scan_images import ScanImages, ScanRenders
from app.composition import build_answering, build_pipeline
from app.core.drawing.model import Scale
from app.core.pipeline.model import DrawingFile, Extracted, Sheet
from app.core.pipeline.printed import INCH_M, PrintedSheet
from app.settings import Settings

PDF = "data/scans/plan.pdf"
CLASSES = ["door", "window", "plan"]
DETECTOR: dict[str, Any] = {  # the detector's facts and knobs (detector.json), as core writes them
    "format": "dfine",
    "side": 100,
    "classes": CLASSES,
    "element_class": {"door": "door", "window": "window", "plan": None},
    "read": ["door", "window"],
    "thresholds": {"door": 0.5, "window": 0.5, "plan": 0.5},
}


def scan(width: int = 300, height: int = 200, dpi: int = 100) -> bytes:
    """A scanner's PDF: one page that is one image, `width` x `height` px at `dpi`."""
    image = Image.new("RGB", (width, height), "white")
    image.paste((0, 0, 0), (40, 40, 60, 60))
    buffer = io.BytesIO()
    image.save(buffer, "PDF", resolution=dpi)
    return buffer.getvalue()


class Files:
    def __init__(self, data: dict[str, bytes]) -> None:
        self.data, self.reads = data, 0

    def read(self, path: str) -> bytes:
        self.reads += 1
        return self.data[path]


def test_a_scanned_pdf_reads_as_the_png_of_its_page_rendered_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    data = scan()  # 3 x 2 inches
    assert is_scanned_pdf(data)
    renders: list[bytes] = []
    real = scan_images.scan_png
    monkeypatch.setattr(scan_images, "scan_png", lambda pdf: renders.append(pdf) or real(pdf))
    files = ScanImages(Files({PDF: data, "plan.png": b"\x89PNG..."}))
    first = files.read(PDF)
    with Image.open(io.BytesIO(first)) as image:
        assert image.format == "PNG"
        assert [round(side / 150, 1) for side in image.size] == [3.0, 2.0]  # 150 px an inch
    assert files.read(PDF) == first and len(renders) == 1  # shared by every reader
    assert files.read("plan.png") == b"\x89PNG..."  # an image reads as it is


def test_a_pdf_that_is_not_a_scan_reads_as_it_is(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(scan_images, "is_scanned_pdf", lambda data: False)
    assert ScanImages(Files({PDF: scan()})).read(PDF) == scan()


class Session:
    """A detector that finds one door and the plan on any canvas it is given."""

    def get_inputs(self) -> list[Any]:
        return []

    def get_outputs(self) -> list[Any]:
        return [type("Out", (), {"name": name})() for name in ("labels", "boxes", "scores")]

    def run(self, names: list[str], feed: dict[str, Any]) -> list[np.ndarray]:
        found = {
            "labels": np.array([[0, 2]]),
            "boxes": np.array([[[10, 10, 20, 20], [0, 0, 100, 100]]], dtype=np.float32),
            "scores": np.array([[0.9, 0.9]], dtype=np.float32),
        }
        return [found[name] for name in names]


def test_the_raster_route_reads_a_scanned_pdf_upload(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The shipping raster readers open the file as an image; given the PDF they failed."""
    dataset = tmp_path / "dataset"
    (dataset / PDF).parent.mkdir(parents=True)
    (dataset / PDF).write_bytes(scan())
    models = tmp_path / "models" / "C"
    models.mkdir(parents=True)
    facts = {k: DETECTOR[k] for k in ("format", "side", "classes", "element_class")}
    (models / "model.json").write_text(json.dumps(facts))
    (models / "detector.json").write_text(json.dumps(DETECTOR))
    monkeypatch.setattr(composition, "DETECTOR_DIR", tmp_path / "models")
    monkeypatch.setattr(raster_detector, "onnx_session", lambda path: Session())
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("EXTRACTOR_RASTER", "composite")
    monkeypatch.setenv("RASTER_COMPONENTS", "elements=detector:C,plans=detector:C")
    pipeline = build_pipeline(Settings(), dataset, lambda path: "pdf_scan")
    report = pipeline.ingest([PDF], ExtractionV1Writer(tmp_path / "out", {PDF: "dev"}))
    (sheet,) = report.sheets
    assert sheet.route == "raster"
    assert dict(sheet.takeoff)["door"] == 1


class Reader:
    """Gemini Decisions' count reader, keeping the bytes it was asked about."""

    def __init__(self) -> None:
        self.asked: list[bytes] = []

    def read(self, image: bytes) -> PageCounts:
        self.asked.append(image)
        return PageCounts({family: CountDist({1: 1.0}) for family in FAMILIES}, "stand-in")


def test_the_answer_confidence_asks_about_the_same_image_as_ingest(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The count swap at ingest reads the render; the confidence at ask time must send Gemini
    the same bytes (one cached reply, one price), not the PDF."""
    reader = Reader()
    monkeypatch.setattr(composition, "decisions_reader", lambda settings: reader)
    answering = build_answering(Settings(decisions_confidence=True))
    assert answering.confidence is not None
    data = scan()
    found = answering.confidence(Files({PDF: data})).probability(PDF, "door", 1)
    assert found.value == 1.0
    assert reader.asked == [ScanImages(Files({PDF: data})).read(PDF)]


def test_every_answer_on_a_scan_shares_its_one_render(monkeypatch: pytest.MonkeyPatch) -> None:
    """Each answer gets its own files view (api/ask.py `_SheetFiles`); they share one cache, so
    the page is not rendered again per answer (review-280 S2)."""
    renders: list[bytes] = []
    real = scan_images.scan_png
    monkeypatch.setattr(scan_images, "scan_png", lambda pdf: renders.append(pdf) or real(pdf))
    monkeypatch.setattr(composition, "decisions_reader", lambda settings: Reader())
    answering = build_answering(Settings(decisions_confidence=True))
    assert answering.confidence is not None
    data = scan()
    for _ in range(3):
        assert answering.confidence(Files({PDF: data})).probability(PDF, "door", 1).value == 1.0
    assert len(renders) == 1


def test_a_render_holds_up_only_the_readers_of_its_own_page(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An A0 scan renders for seconds; a reader of another page must not queue behind it
    (review-280 S1: one lock for every file did)."""
    slow, other = b"%PDF slow page", b"%PDF other page"
    started, release = threading.Event(), threading.Event()

    def render(pdf: bytes) -> bytes:
        if pdf == slow:
            started.set()
            release.wait()
        return b"png of " + pdf

    monkeypatch.setattr(scan_images, "is_scanned_pdf", lambda data: True)
    monkeypatch.setattr(scan_images, "scan_png", render)
    renders = ScanRenders()
    read: dict[bytes, bytes] = {}
    first = threading.Thread(target=lambda: read.update({slow: renders.image(slow)}))
    first.start()
    try:
        assert started.wait(10)
        second = threading.Thread(target=lambda: read.update({other: renders.image(other)}))
        second.start()
        second.join(10)  # returns at once unless it waits for the slow render
        assert read.get(other) == b"png of " + other
    finally:
        release.set()
        first.join(10)
    assert read[slow] == b"png of " + slow


class Unscaled:
    """A raster reader that found no scale (Carbon's reading: it does not scale the drawing)."""

    def extract(self, source: DrawingFile, sheet: Sheet) -> Extracted:
        return Extracted(method="detector", scale=Scale(status="no_scale"))


class Prints:
    """The printed-scale reader, reading the ratio the sheet prints."""

    def read(self, source: DrawingFile, sheet: Sheet) -> PrintedSheet:
        return PrintedSheet(printed_scale='1/4" = 1\'-0"')


def test_a_scanned_pdfs_printed_ratio_becomes_its_scale() -> None:
    """judge-path 2026-11-14: a scanned 39.1 x 24.5 in sheet printing 1/4" = 1'-0" had its ratio
    read and dropped ("an image has no paper size"), areas about 17% low. The render states its
    resolution, so the ratio scales the page: 48 x the paper's width across the image."""
    data = scan(391, 245, dpi=10)  # the uscg-bldg125 floor plan's paper, 39.1 x 24.5 in
    page = ScanImages(Files({PDF: data})).read(PDF)
    with Image.open(io.BytesIO(page)) as image:
        width, height = image.size
    assert width < 39.1 * 150 and width * height == pytest.approx(MAX_PIXELS, rel=1e-3)  # capped
    dpi = stated_dpi(page)
    assert dpi is not None and dpi[0] == pytest.approx(width / 39.1, rel=1e-3) == dpi[1]
    file = DrawingFile(path=PDF, size=len(data), sha256="0" * 64, kind="pdf")
    # The sheet's pages as the pipeline reads them: the PDF's own, in points, not the render's
    # pixels. The scale is metres per page unit, so it is 48 x 0.0254 / 72 whatever the render's
    # resolution (r10, 2026-11-14: it was metres per render pixel, and areas came out x0.31).
    sheet = Sheet(file=file, pages=PageSizes(Files({PDF: data})).pages(file))
    assert sheet.pages[0].unit == "pt"
    assert sheet.pages[0].width == pytest.approx(39.1 * 72, rel=1e-3)
    found = PrintedScale(Unscaled(), Prints(), ScanImages(Files({PDF: data}))).extract(file, sheet)
    assert found.scale.status == "scaled" and found.scale.m_per_unit is not None
    assert found.scale.m_per_unit * sheet.pages[0].width == pytest.approx(
        48 * 39.1 * INCH_M, rel=1e-3
    )
    assert found.scale.source == "printed scale 1/4\" = 1'-0\" on the page's paper size"

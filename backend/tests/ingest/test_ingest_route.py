"""Stage 5 routes a group to its richest route that has a reader, never to one that reads
nothing: a swiss plan's PDF, PNG and DXF go to the vector reader while there is no CAD reader."""

import io
from pathlib import Path

import pytest
from PIL import Image
from test_vector_pdf import swiss_sheet

from app.adapters.archive.probe import is_scanned_pdf
from app.adapters.hello import HelloExtractor, HelloSecondCounter, HelloSourceFinder
from app.adapters.page_sizes import PageSizes
from app.adapters.vector_pdf import PdfVectorExtractor
from app.composition import build_pipeline
from app.core.drawing.model import Drawing
from app.core.pipeline.ingest import ingest
from app.core.pipeline.model import DrawingFile, DrawingGroup, FileKind, Route
from app.core.pipeline.route import route
from app.settings import Settings

PLAN = swiss_sheet()
DXF = b"0\nSECTION\n2\nENTITIES\n0\nENDSEC\n0\nEOF\n"


def a_file(kind: FileKind) -> DrawingFile:
    return DrawingFile(path=f"a/plan.{kind}", size=1, sha256="0" * 64, kind=kind)


@pytest.mark.parametrize(
    ("kinds", "readable", "expected"),
    [
        (["png", "pdf", "dxf"], {"vector", "bim"}, "vector"),  # no CAD reader: the PDF
        (["png", "pdf", "dxf"], {"cad", "vector"}, "cad"),  # a CAD reader: the DXF
        (["pdf", "ifc"], {"vector"}, "vector"),
        (["png", "dxf"], {"vector"}, "cad"),  # nothing readable: the richest, as before
        (["png", "pdf"], {"raster"}, "raster"),
    ],
)
def test_the_richest_route_with_a_reader_wins(
    kinds: list[FileKind], readable: set[Route], expected: Route
) -> None:
    group = DrawingGroup(key="a/plan", files=tuple(a_file(kind) for kind in kinds))
    assert route(group, readable).route == expected


def test_without_readers_named_every_route_counts_as_before() -> None:
    group = DrawingGroup(key="a/plan", files=(a_file("pdf"), a_file("dxf")))
    assert route(group).route == "cad"


class Files:
    def __init__(self, content: dict[str, bytes]) -> None:
        self._content = content

    def read(self, path: str) -> bytes:
        return self._content[path]


class Kept:
    def __init__(self) -> None:
        self.drawings: list[Drawing] = []

    def write(self, drawing: Drawing) -> None:
        self.drawings.append(drawing)


def test_a_swiss_plan_with_its_dxf_is_read_by_the_vector_reader() -> None:
    files = Files({"a/p.pdf": PLAN.pdf(), "a/p.png": PLAN.png(), "a/p.dxf": DXF})
    kept = Kept()
    report = ingest(
        ["a/p.pdf", "a/p.png", "a/p.dxf"],
        files=files,
        finder=HelloSourceFinder(),
        pages=PageSizes(files),
        extractors={
            "bim": HelloExtractor(),
            "cad": HelloExtractor(),
            "vector": PdfVectorExtractor(files),
            "raster": HelloExtractor(),
        },
        second_counter=HelloSecondCounter(),
        sink=kept,
        readable={"vector"},
    )
    assert [(sheet.file, sheet.route, sheet.source) for sheet in report.sheets] == [
        ("a/p.pdf", "vector", "a/p.pdf"),
        ("a/p.png", "vector", "a/p.pdf"),
    ]
    assert all(len(drawing.elements) == 8 for drawing in kept.drawings)


def test_the_pipeline_knows_which_routes_have_a_reader(tmp_path: Path) -> None:
    defaults = Settings(_env_file=None)  # pyright: ignore[reportCallIssue]
    assert defaults.extractor_cad == "hello" and defaults.extractor_raster == "hello"
    assert build_pipeline(defaults, tmp_path).readable == {"bim", "vector"}
    everything_hello = Settings(
        _env_file=None,  # pyright: ignore[reportCallIssue]
        extractor_bim="hello",
        extractor_vector="hello",
    )
    assert build_pipeline(everything_hello, tmp_path).readable == frozenset()


def test_a_scanned_pdf_goes_to_the_raster_route() -> None:
    pdf = a_file("pdf")
    group = DrawingGroup(key="a/plan", files=(pdf,))
    assert route(group, scanned={pdf.path}).route == "raster"
    assert route(group).route == "vector"


def scanned_pdf() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (800, 600), "white").save(buffer, "PDF", resolution=100)
    return buffer.getvalue()


class Seen:
    def __init__(self) -> None:
        self.sources: list[str] = []

    def extract(self, source: DrawingFile, sheet: object) -> object:
        self.sources.append(source.path)
        return HelloExtractor().extract(source, sheet)  # type: ignore[arg-type]


def test_ingest_sends_a_scanned_pdf_to_the_raster_reader_and_a_drawn_one_to_vector() -> None:
    files = Files({"scan.pdf": scanned_pdf(), "plan.pdf": PLAN.pdf()})
    raster, vector = Seen(), Seen()
    report = ingest(
        ["scan.pdf", "plan.pdf"],
        files=files,
        finder=HelloSourceFinder(),
        pages=PageSizes(files),
        extractors={"bim": HelloExtractor(), "cad": HelloExtractor(),
                    "vector": vector, "raster": raster},  # type: ignore[dict-item]
        second_counter=HelloSecondCounter(),
        sink=Kept(),
        scanned=is_scanned_pdf,
    )  # fmt: skip
    assert [(sheet.file, sheet.route) for sheet in report.sheets] == [
        ("scan.pdf", "raster"),
        ("plan.pdf", "vector"),
    ]
    assert (raster.sources, vector.sources) == (["scan.pdf"], ["plan.pdf"])


def test_the_pipeline_tells_scans_apart(tmp_path: Path) -> None:
    pipeline = build_pipeline(Settings(_env_file=None), tmp_path)  # pyright: ignore[reportCallIssue]
    assert pipeline.scanned is not None
    assert pipeline.scanned(scanned_pdf()) and not pipeline.scanned(PLAN.pdf())

"""The ingest use case end to end on fakes: which files get a drawing model, from which source,
and what the report says."""

from app.core.drawing.model import (
    Drawing,
    Element,
    MeasuredValue,
    Page,
    Scale,
    Subject,
)
from app.core.pipeline.ingest import NO_SHEET, ingest
from app.core.pipeline.model import DrawingFile, Extracted, Measurement, SetAside, Sheet

PNG = b"\x89PNG\r\n\x1a\n" + b"synthetic"
PDF = b"%PDF-1.7 synthetic"
DXF = b"0\nSECTION\n2\nHEADER\n"
IFC = b"ISO-10303-21;\nHEADER;"
BOX = (0.1, 0.2, 0.3, 0.4)


class Files:
    def __init__(self, content: dict[str, bytes]) -> None:
        self.content = content

    def read(self, path: str) -> bytes:
        return self.content[path]


class Pages:
    """A PDF sheet has two pages in points, an image one page in pixels."""

    def pages(self, file: DrawingFile) -> tuple[Page, ...]:
        if file.kind == "pdf":
            return tuple(Page(page=n, width=200, height=100, unit="pt") for n in (1, 2))
        return (Page(page=1, width=40, height=30, unit="px"),)


class OneDoor:
    """An extractor that finds one door wherever it looks, and remembers what it was shown."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def extract(self, source: DrawingFile, sheet: Sheet) -> Extracted:
        self.calls.append((source.path, sheet.file.path))
        door = Element(id="e1", class_="door", page=1, box=BOX)
        return Extracted(method="parser", scale=Scale(status="no_scale"), elements=(door,))


class Nothing:
    def measure(self, source: DrawingFile, sheet: Sheet) -> list[Measurement]:
        return []


class TwoDoors:
    """A second method that always counts two doors."""

    def measure(self, source: DrawingFile, sheet: Sheet) -> list[Measurement]:
        return [
            Measurement(
                quantity="element_count",
                subject=Subject(kind="class", ref="door"),
                value=MeasuredValue(value=2, unit="count", method="detector"),
            )
        ]


class Collected:
    def __init__(self) -> None:
        self.drawings: list[Drawing] = []

    def write(self, drawing: Drawing) -> None:
        self.drawings.append(drawing)


def test_ingest_writes_one_drawing_per_sheet_file_read_from_the_richest_source() -> None:
    content = {
        "data/swiss/plan1.png": PNG,
        "data/swiss/plan1.pdf": PDF,
        "data/swiss/plan1.dxf": DXF,
        "data/cubi/scan.png": PNG,
        "data/ifc/model.ifc": IFC,
        "data/cubi/readme.txt": b"not a drawing",
    }
    cad, raster, unused = OneDoor(), OneDoor(), OneDoor()
    sink = Collected()

    report = ingest(
        list(content),
        files=Files(content),
        pages=Pages(),
        extractors={"bim": unused, "cad": cad, "vector": unused, "raster": raster},
        second_counter=Nothing(),
        sink=sink,
    )

    # The swiss group is read from its DXF, once per sheet; the DXF itself has no page.
    assert cad.calls == [
        ("data/swiss/plan1.dxf", "data/swiss/plan1.png"),
        ("data/swiss/plan1.dxf", "data/swiss/plan1.pdf"),
    ]
    assert raster.calls == [("data/cubi/scan.png", "data/cubi/scan.png")]
    assert unused.calls == []
    assert [drawing.file for drawing in sink.drawings] == [
        "data/swiss/plan1.png",
        "data/swiss/plan1.pdf",
        "data/cubi/scan.png",
    ]
    pdf_drawing = sink.drawings[1]
    assert [page.unit for page in pdf_drawing.pages] == ["pt", "pt"]
    assert [element.class_ for element in pdf_drawing.elements] == ["door"]
    assert pdf_drawing.conflicts is None  # nothing was measured a second time
    assert report.set_aside == (
        SetAside(path="data/cubi/readme.txt", reason="not a drawing format we read"),
        SetAside(path="data/ifc/model.ifc", reason=NO_SHEET),
    )

    png_sheet = report.sheets[0]
    assert (png_sheet.file, png_sheet.kind, png_sheet.group) == (
        "data/swiss/plan1.png",
        "png",
        "data/swiss/plan1",
    )
    assert (png_sheet.route, png_sheet.source) == ("cad", "data/swiss/plan1.dxf")
    assert png_sheet.takeoff["door"] == 1
    assert png_sheet.takeoff["window"] == 0
    assert [line.split(":")[0] for line in png_sheet.trace] == [
        "inventory",
        "identify",
        "group",
        "route",
        "normalise",
        "extract",
        "second count",
        "rules",
        "takeoff",
    ]
    assert png_sheet.trace[4] == "normalise: 1 page(s), page 1 is 40 x 30 px"
    assert png_sheet.trace[5] == "extract: 1 elements, 0 rooms, 0 plans, scale no_scale"
    assert png_sheet.trace[8] == "takeoff: 31 quantities, 1 above zero"


def test_ingest_writes_what_a_second_method_measured_into_the_drawing() -> None:
    content = {"data/cubi/scan.png": PNG}
    sink = Collected()
    extractor = OneDoor()

    report = ingest(
        list(content),
        files=Files(content),
        pages=Pages(),
        extractors={"bim": extractor, "cad": extractor, "vector": extractor, "raster": extractor},
        second_counter=TwoDoors(),
        sink=sink,
    )

    conflicts = sink.drawings[0].conflicts
    assert conflicts is not None
    (conflict,) = conflicts
    assert (conflict.status, conflict.subject.ref) == ("conflict", "door")
    assert [(value.value, value.method) for value in conflict.values] == [
        (1.0, "parser"),
        (2.0, "detector"),
    ]
    assert report.sheets[0].trace[6] == "second count: 1 quantities measured twice, 1 conflict(s)"

"""The ingest use case end to end on fakes: which files get a drawing model, from which source,
and what the report says."""

from app.core.drawing.model import (
    Drawing,
    Element,
    MeasuredValue,
    ModelObject,
    Page,
    Scale,
    Subject,
)
from app.core.pipeline.ingest import NO_SHEET, ingest
from app.core.pipeline.model import DrawingFile, Extracted, Measurement, Route, SetAside, Sheet

PNG = b"\x89PNG\r\n\x1a\n" + b"synthetic"
PDF = b"%PDF-1.7 synthetic"
DXF = b"0\nSECTION\n2\nHEADER\n"
IFC = b"ISO-10303-21;\nHEADER;"
BOX = (0.1, 0.2, 0.3, 0.4)


class Files:
    def __init__(self, content: dict[str, bytes]) -> None:
        self.content = content
        self.reads: list[str] = []

    def read(self, path: str) -> bytes:
        self.reads.append(path)
        return self.content[path]


class Found:
    """A finder that knows the given sources, by the path of the file they belong to."""

    def __init__(self, sources: dict[str, list[str]] | None = None) -> None:
        self.found = sources or {}

    def sources(self, path: str) -> list[str]:
        return self.found.get(path, [])


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


class DoorsOnly:
    """An extractor that says it looked for doors and nothing else, and found none."""

    def extract(self, source: DrawingFile, sheet: Sheet) -> Extracted:
        return Extracted(method="detector", scale=Scale(status="no_scale"), read=("door",))


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
    cad, raster, bim, unused = OneDoor(), OneDoor(), OneDoor(), OneDoor()
    sink = Collected()

    report = ingest(
        list(content),
        files=Files(content),
        finder=Found(),
        pages=Pages(),
        extractors={"bim": bim, "cad": cad, "vector": unused, "raster": raster},
        second_counter=Nothing(),
        sink=sink,
    )

    # The swiss group is read from its DXF, once per sheet; the DXF itself has no page.
    assert cad.calls == [
        ("data/swiss/plan1.dxf", "data/swiss/plan1.png"),
        ("data/swiss/plan1.dxf", "data/swiss/plan1.pdf"),
    ]
    assert raster.calls == [("data/cubi/scan.png", "data/cubi/scan.png")]
    # The model has no page either. Its extractor is asked what it lists: no objects here.
    assert bim.calls == [("data/ifc/model.ifc", "data/ifc/model.ifc")]
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
    assert png_sheet.trace[4] == "normalise: 1 page, page 1 is 40 x 30 px"
    assert png_sheet.trace[5] == "extract: 1 element, 0 rooms, 0 plans, no scale on the sheet"
    assert png_sheet.trace[8] == "takeoff: 31 quantities, 1 above zero"


def test_ingest_writes_what_a_second_method_measured_into_the_drawing() -> None:
    content = {"data/cubi/scan.png": PNG}
    sink = Collected()
    extractor = OneDoor()

    report = ingest(
        list(content),
        files=Files(content),
        finder=Found(),
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
    assert report.sheets[0].trace[6] == "second count: 1 quantity measured twice, 1 conflict"


class WithAModel:
    """An extractor that also hands over what its building model lists."""

    listed = (ModelObject(id="m1", class_="slab", storey="EG", quantities={"volume_m3": 24.0}),)

    def extract(self, source: DrawingFile, sheet: Sheet) -> Extracted:
        return Extracted(
            method="plan_drawing", scale=Scale(status="no_scale"), model_objects=self.listed
        )


def test_the_drawing_carries_the_model_objects_its_extractor_gives() -> None:
    content = {"data/cubi/scan.png": PNG, "data/swiss/plan1.pdf": PDF}
    sink = Collected()
    ingest(
        list(content),
        files=Files(content),
        finder=Found(),
        pages=Pages(),
        extractors={
            "bim": OneDoor(),
            "cad": OneDoor(),
            "vector": WithAModel(),
            "raster": OneDoor(),
        },
        second_counter=Nothing(),
        sink=sink,
    )
    listed = {drawing.file: drawing.model_objects for drawing in sink.drawings}
    # None: the extractor had no model, which is not the same as a model that lists nothing.
    assert listed == {"data/cubi/scan.png": None, "data/swiss/plan1.pdf": WithAModel.listed}


def test_the_drawing_says_what_its_extractor_looked_for() -> None:
    content = {"data/cubi/scan.png": PNG, "data/swiss/plan1.pdf": PDF}
    sink = Collected()
    ingest(
        list(content),
        files=Files(content),
        finder=Found(),
        pages=Pages(),
        extractors={
            "bim": OneDoor(),
            "cad": OneDoor(),
            "vector": OneDoor(),
            "raster": DoorsOnly(),
        },
        second_counter=Nothing(),
        sink=sink,
    )
    read = {drawing.file: drawing.read for drawing in sink.drawings}
    # No door found is a count of 0 only for a class that was looked for; None: all of them were.
    assert read == {"data/cubi/scan.png": ("door",), "data/swiss/plan1.pdf": None}


SHEET, SHEET_2, MODEL = (
    "data/ifc/tower_plan-01-eg.pdf",
    "data/ifc/tower_plan-02-og.pdf",
    "data/ifc/tower.ifc",
)


def routes() -> dict[Route, OneDoor]:
    return {"bim": OneDoor(), "cad": OneDoor(), "vector": OneDoor(), "raster": OneDoor()}


def test_a_model_found_for_a_sheet_joins_its_group_and_is_the_source_it_is_read_from() -> None:
    """Only the sheets are given. The model has another name, so only the finder pairs them."""
    files = Files({SHEET: PDF, SHEET_2: PDF, MODEL: IFC})
    extractors, sink = routes(), Collected()

    report = ingest(
        [SHEET, SHEET_2],
        files=files,
        finder=Found({SHEET: [MODEL], SHEET_2: [MODEL]}),
        pages=Pages(),
        extractors=extractors,
        second_counter=Nothing(),
        sink=sink,
    )

    assert extractors["bim"].calls == [(MODEL, SHEET), (MODEL, SHEET_2)]
    assert extractors["vector"].calls == []
    assert [drawing.file for drawing in sink.drawings] == [SHEET, SHEET_2]  # none for the model
    assert report.set_aside == ()  # the model was not asked about: it is a source, nothing more
    first = report.sheets[0]
    assert (first.route, first.source, first.group) == ("bim", MODEL, "data/ifc/tower_plan-01-eg")
    assert first.trace[2] == "group: data/ifc/tower_plan-01-eg, 2 files"
    assert files.reads.count(MODEL) == 1  # two sheets, one inventory entry


def test_a_sheet_the_finder_knows_no_source_for_keeps_its_own_route() -> None:
    files = Files({SHEET: PDF, SHEET_2: PDF, MODEL: IFC})
    extractors = routes()
    ingest(
        [SHEET, SHEET_2],
        files=files,
        finder=Found({SHEET: [MODEL]}),
        pages=Pages(),
        extractors=extractors,
        second_counter=Nothing(),
        sink=Collected(),
    )
    assert extractors["bim"].calls == [(MODEL, SHEET)]
    assert extractors["vector"].calls == [(SHEET_2, SHEET_2)]


def test_a_model_asked_about_whose_extractor_lists_nothing_is_set_aside_and_serves_its_sheet() -> (
    None
):
    files = Files({SHEET: PDF, MODEL: IFC})
    extractors, sink = routes(), Collected()
    report = ingest(
        [MODEL, SHEET],
        files=files,
        finder=Found({SHEET: [MODEL]}),
        pages=Pages(),
        extractors=extractors,
        second_counter=Nothing(),
        sink=sink,
    )
    # Asked what it lists of itself, the extractor names no model objects.
    assert extractors["bim"].calls == [(MODEL, MODEL), (MODEL, SHEET)]
    assert [drawing.file for drawing in sink.drawings] == [SHEET]
    assert report.set_aside == (SetAside(path=MODEL, reason=NO_SHEET),)


class ListsItsModel:
    """A model route's extractor: a door on a sheet, and the model's objects either way."""

    listed = (
        ModelObject(id="m1", class_="door", storey="EG", element="e1"),
        ModelObject(id="m2", class_="slab", storey="EG", quantities={"volume_m3": 24.0}),
    )

    def __init__(self) -> None:
        self.pages_seen: list[int] = []

    def extract(self, source: DrawingFile, sheet: Sheet) -> Extracted:
        self.pages_seen.append(len(sheet.pages))
        if not sheet.pages:
            unplaced = tuple(item.model_copy(update={"element": None}) for item in self.listed)
            return Extracted(
                method="ifc_model",
                scale=Scale(status="no_scale"),
                read=("door", "slab"),
                model_objects=unplaced,
                notes=("read as a model",),
            )
        door = Element(id="e1", class_="door", page=1, box=BOX)
        return Extracted(
            method="plan_drawing",
            scale=Scale(status="no_scale"),
            elements=(door,),
            model_objects=self.listed,
        )


def test_a_model_that_is_asked_about_gets_a_drawing_of_its_objects_without_a_page() -> None:
    files = Files({SHEET: PDF, MODEL: IFC})
    bim, sink = ListsItsModel(), Collected()
    report = ingest(
        [MODEL, SHEET],
        files=files,
        finder=Found({SHEET: [MODEL]}),
        pages=Pages(),
        extractors={**routes(), "bim": bim},
        second_counter=TwoDoors(),
        sink=sink,
    )
    assert bim.pages_seen == [0, 2]  # the model as its own sheet, then the PDF sheet
    assert report.set_aside == ()
    of_model, of_sheet = sink.drawings
    assert (of_model.file, of_model.pages, of_sheet.file) == (MODEL, (), SHEET)
    assert (of_model.plans, of_model.elements, of_model.rooms) == ((), (), ())
    assert of_model.model_objects is not None
    assert [(item.id, item.element) for item in of_model.model_objects] == [
        ("m1", None),
        ("m2", None),
    ]
    assert (of_model.read, of_model.notes) == (("door", "slab"), ("read as a model",))
    assert of_model.conflicts is None  # no sheet: nothing to measure a second time
    assert of_sheet.conflicts is not None
    assert of_sheet.model_objects == ListsItsModel.listed

    entry = report.sheets[0]
    assert (entry.file, entry.kind, entry.group) == (MODEL, "ifc", "data/ifc/tower")
    assert (entry.route, entry.source) == ("bim", MODEL)
    assert [line.split(":")[0] for line in entry.trace] == [
        "inventory",
        "identify",
        "group",
        "route",
        "normalise",
        "extract",
        "takeoff",
    ]
    assert entry.trace[3:6] == (
        f"route: bim, read from {MODEL}",
        "normalise: no page, a building model",
        "extract: 2 model objects",
    )


def test_only_a_building_model_is_asked_what_it_holds_without_a_page() -> None:
    """A CAD file alone has no page either, and no objects to list: its extractor is not run."""
    dxf = "data/swiss/plan1.dxf"
    extractors = routes()
    report = ingest(
        [dxf],
        files=Files({dxf: DXF}),
        finder=Found(),
        pages=Pages(),
        extractors=extractors,
        second_counter=Nothing(),
        sink=Collected(),
    )
    assert [found.calls for found in extractors.values()] == [[], [], [], []]
    assert report.set_aside == (SetAside(path=dxf, reason=NO_SHEET),)


def test_a_found_source_with_pages_is_read_from_and_gets_no_drawing_of_its_own() -> None:
    """Only the PNG is asked about; the finder knows its PDF."""
    png, pdf = "data/swiss/plan1.png", "data/swiss/elsewhere.pdf"
    extractors, sink = routes(), Collected()
    report = ingest(
        [png],
        files=Files({png: PNG, pdf: PDF}),
        finder=Found({png: [pdf]}),
        pages=Pages(),
        extractors=extractors,
        second_counter=Nothing(),
        sink=sink,
    )
    assert extractors["vector"].calls == [(pdf, png)]
    assert [drawing.file for drawing in sink.drawings] == [png]
    assert [sheet.file for sheet in report.sheets] == [png]


def test_a_found_source_that_is_also_asked_about_gets_one_drawing_in_its_own_group() -> None:
    png, pdf = "data/swiss/plan1.png", "data/swiss/elsewhere.pdf"
    extractors, sink = routes(), Collected()
    report = ingest(
        [png, pdf],
        files=Files({png: PNG, pdf: PDF}),
        finder=Found({png: [pdf]}),
        pages=Pages(),
        extractors=extractors,
        second_counter=Nothing(),
        sink=sink,
    )
    assert extractors["vector"].calls == [(pdf, png), (pdf, pdf)]
    assert [drawing.file for drawing in sink.drawings] == [png, pdf]
    assert [(sheet.file, sheet.group) for sheet in report.sheets] == [
        (png, "data/swiss/plan1"),
        (pdf, "data/swiss/elsewhere"),
    ]


def test_a_found_source_that_is_not_a_drawing_is_set_aside_and_the_sheet_keeps_its_route() -> None:
    files = Files({SHEET: PDF, MODEL: b"not a model"})
    extractors = routes()
    report = ingest(
        [SHEET],
        files=files,
        finder=Found({SHEET: [MODEL]}),
        pages=Pages(),
        extractors=extractors,
        second_counter=Nothing(),
        sink=Collected(),
    )
    assert extractors["vector"].calls == [(SHEET, SHEET)]
    assert report.set_aside == (SetAside(path=MODEL, reason="not a drawing format we read"),)

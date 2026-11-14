"""The ingest use case: runs the ten stages over a list of files and writes one drawing model per
sheet file to the sink. The CLI and the API both call this (through app/composition.py)."""

from collections.abc import Callable, Collection, Iterable, Mapping

from app.core.drawing.model import Drawing
from app.core.pipeline.extract import extract
from app.core.pipeline.group import group, key_of
from app.core.pipeline.identify import identify
from app.core.pipeline.inventory import file_entry
from app.core.pipeline.model import (
    SHEET_KINDS,
    DrawingFile,
    DrawingGroup,
    IngestReport,
    Route,
    Routed,
    SetAside,
    Sheet,
    SheetReport,
)
from app.core.pipeline.normalise import normalise
from app.core.pipeline.ports import (
    DrawingFiles,
    DrawingSink,
    Extractor,
    PageReader,
    SecondCounter,
    SourceFinder,
)
from app.core.pipeline.route import RICHEST_FIRST, route
from app.core.pipeline.rules import apply_rules
from app.core.pipeline.second_count import measured, resolved_rooms, second_count
from app.core.pipeline.takeoff import take_off

NO_SHEET = "no PDF, PNG or JPEG in its group, so there is no page to place a drawing model on"
MODEL_ROUTE: Route = "bim"  # the one route whose source can be asked about without a page


def ingest(
    paths: Iterable[str],
    *,
    files: DrawingFiles,
    finder: SourceFinder,
    pages: PageReader,
    extractors: Mapping[Route, Extractor],
    second_counter: SecondCounter,
    sink: DrawingSink,
    readable: Collection[Route] = RICHEST_FIRST,
    scanned: Callable[[bytes], bool] | None = None,
) -> IngestReport:
    """A drawing model is written for every sheet among `paths`, and for a building model among
    them when its extractor lists its objects. A source the finder adds (a sheet's building
    model) is read from, and gets no drawing model of its own. `readable`: the routes whose
    extractor reads something; stage 5 routes a group only to one of them when it can.
    `scanned`: whether a PDF's bytes are a scan (no drawn content), which stage 5 routes to the
    raster reader; None: every PDF is drawn."""
    inventory: dict[str, DrawingFile | SetAside] = {}
    scans: set[str] = set()

    def entry(path: str) -> DrawingFile | SetAside:
        if path not in inventory:
            data = files.read(path)
            inventory[path] = found = identify(file_entry(path, data), data)
            is_pdf = isinstance(found, DrawingFile) and found.kind == "pdf"
            if scanned is not None and is_pdf and scanned(data):
                scans.add(path)
        return inventory[path]

    drawing_files = [found for path in paths if isinstance(found := entry(path), DrawingFile)]
    sources: dict[str, list[DrawingFile]] = {}
    for file in drawing_files:
        for path in finder.sources(file.path):
            if isinstance(found := entry(path), DrawingFile):
                sources.setdefault(file.path, []).append(found)
    set_aside = [found for found in inventory.values() if isinstance(found, SetAside)]
    given = {file.path for file in drawing_files}

    sheets: list[SheetReport] = []
    for members in group(drawing_files, sources):
        routed = route(members, readable, scans)
        # A source found for this group that was also given gets its drawing in its own group.
        asked = [
            file for file in members.files if file.path in given and key_of(file) == members.key
        ]
        sheet_files = [file for file in asked if file.kind in SHEET_KINDS]
        for file in asked:
            if file.kind in SHEET_KINDS:
                sheets.append(
                    _ingest_sheet(
                        file,
                        members,
                        routed,
                        pages=pages,
                        extractors=extractors,
                        second_counter=second_counter,
                        sink=sink,
                    )
                )
            elif (
                model := _ingest_model(file, members, routed, extractors=extractors, sink=sink)
            ) is not None:
                sheets.append(model)
            elif not sheet_files:
                set_aside.append(SetAside(path=file.path, reason=NO_SHEET))
    return IngestReport(sheets=tuple(sheets), set_aside=tuple(set_aside))


def _ingest_model(
    file: DrawingFile,
    members: DrawingGroup,
    routed: Routed,
    *,
    extractors: Mapping[Route, Extractor],
    sink: DrawingSink,
) -> SheetReport | None:
    """Stages 7-10 for a building model that is asked about itself. It has no page, so its
    drawing model is the objects its extractor lists of it (`model_objects`), with nothing
    placed and nothing to measure a second time. None: it is not the model its group is read
    from, or the extractor lists nothing of it, so there is no drawing model to write."""
    if routed.route != MODEL_ROUTE or file != routed.source:
        return None
    found = extract(routed, Sheet(file=file, pages=()), extractors)
    if not found.model_objects:
        return None
    drawing = Drawing(
        file=file.path,
        pages=(),
        scale=found.scale,
        read=found.read,
        model_objects=found.model_objects,
        notes=found.notes,
    )
    quantities = take_off(drawing, apply_rules(drawing.marks_by_quantity()))
    sink.write(drawing)
    above_zero = sum(quantity.value > 0 for quantity in quantities.values())
    return SheetReport(
        file=file.path,
        sha256=file.sha256,
        kind=file.kind,
        group=members.key,
        route=routed.route,
        source=routed.source.path,
        takeoff={key: quantity.value for key, quantity in quantities.items()},
        trace=(
            *_found(file, members, routed),
            "normalise: no page, a building model",
            f"extract: {len(found.model_objects)} model objects",
            f"takeoff: {len(quantities)} quantities, {above_zero} above zero",
        ),
    )


def _found(file: DrawingFile, members: DrawingGroup, routed: Routed) -> tuple[str, ...]:
    """The trace of stages 1-5 for one file."""
    return (
        f"inventory: {file.size} bytes, sha256 {file.sha256[:12]}",
        f"identify: {file.kind}",
        f"group: {members.key}, {len(members.files)} file(s)",
        f"route: {routed.route}, read from {routed.source.path}",
    )


def _ingest_sheet(
    file: DrawingFile,
    members: DrawingGroup,
    routed: Routed,
    *,
    pages: PageReader,
    extractors: Mapping[Route, Extractor],
    second_counter: SecondCounter,
    sink: DrawingSink,
) -> SheetReport:
    """Stages 6-10 for one sheet of a group. One drawing model per sheet file: a PDF and a PNG of
    the same plan have different page frames (decision 0004)."""
    sheet = normalise(file, pages.pages(file))
    found = extract(routed, sheet, extractors)
    again = second_counter.measure(routed.source, sheet)
    compared = second_count(measured(found), again)
    drawing = Drawing(
        file=file.path,
        pages=sheet.pages,
        scale=found.scale,
        plans=found.plans,
        elements=found.elements,
        rooms=resolved_rooms(found.rooms, compared),
        apartments=found.apartments,
        tables=found.tables,
        conflicts=tuple(compared) if again else None,
        read=found.read,
        model_objects=found.model_objects,
        double_check=found.double_check,
        notes=found.notes,
    )
    counted = apply_rules(drawing.marks_by_quantity())
    quantities = take_off(drawing, counted)
    sink.write(drawing)
    first_page = sheet.pages[0]
    rules = sorted({found.rule.id for found in counted.values()})
    above_zero = sum(quantity.value > 0 for quantity in quantities.values())
    conflicts = sum(entry.status == "conflict" for entry in compared)
    return SheetReport(
        file=file.path,
        sha256=file.sha256,
        kind=file.kind,
        group=members.key,
        route=routed.route,
        source=routed.source.path,
        takeoff={key: quantity.value for key, quantity in quantities.items()},
        trace=(
            *_found(file, members, routed),
            f"normalise: {len(sheet.pages)} page(s), page 1 is "
            f"{first_page.width:g} x {first_page.height:g} {first_page.unit}",
            f"extract: {len(drawing.elements)} elements, {len(drawing.rooms)} rooms, "
            f"{len(drawing.plans)} plans, scale {drawing.scale.status}",
            f"second count: {len(compared)} quantities measured twice, {conflicts} conflict(s)",
            f"rules: {', '.join(rules)}",
            f"takeoff: {len(quantities)} quantities, {above_zero} above zero",
        ),
    )

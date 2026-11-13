"""The ingest use case: runs the ten stages over a list of files and writes one drawing model per
sheet file to the sink. The CLI and the API both call this (through app/composition.py)."""

from collections.abc import Iterable, Mapping

from app.core.drawing.model import Drawing
from app.core.pipeline.extract import extract
from app.core.pipeline.group import group
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
    SheetReport,
)
from app.core.pipeline.normalise import normalise
from app.core.pipeline.ports import DrawingFiles, DrawingSink, Extractor, PageReader, SecondCounter
from app.core.pipeline.route import route
from app.core.pipeline.rules import apply_rules
from app.core.pipeline.second_count import measured, resolved_rooms, second_count
from app.core.pipeline.takeoff import take_off

NO_SHEET = "no PDF, PNG or JPEG in its group, so there is no page to place a drawing model on"


def ingest(
    paths: Iterable[str],
    *,
    files: DrawingFiles,
    pages: PageReader,
    extractors: Mapping[Route, Extractor],
    second_counter: SecondCounter,
    sink: DrawingSink,
) -> IngestReport:
    drawing_files: list[DrawingFile] = []
    set_aside: list[SetAside] = []
    for path in paths:
        data = files.read(path)
        found = identify(file_entry(path, data), data)
        if isinstance(found, SetAside):
            set_aside.append(found)
        else:
            drawing_files.append(found)

    sheets: list[SheetReport] = []
    for members in group(drawing_files):
        routed = route(members)
        sheet_files = [file for file in members.files if file.kind in SHEET_KINDS]
        if not sheet_files:
            set_aside += [SetAside(path=file.path, reason=NO_SHEET) for file in members.files]
        for file in sheet_files:
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
    return IngestReport(sheets=tuple(sheets), set_aside=tuple(set_aside))


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
            f"inventory: {file.size} bytes, sha256 {file.sha256[:12]}",
            f"identify: {file.kind}",
            f"group: {members.key}, {len(members.files)} file(s)",
            f"route: {routed.route}, read from {routed.source.path}",
            f"normalise: {len(sheet.pages)} page(s), page 1 is "
            f"{first_page.width:g} x {first_page.height:g} {first_page.unit}",
            f"extract: {len(drawing.elements)} elements, {len(drawing.rooms)} rooms, "
            f"{len(drawing.plans)} plans, scale {drawing.scale.status}",
            f"second count: {len(compared)} quantities measured twice, {conflicts} conflict(s)",
            f"rules: {', '.join(rules)}",
            f"takeoff: {len(quantities)} quantities, {above_zero} above zero",
        ),
    )

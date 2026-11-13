"""Each ingest stage on tiny synthetic inputs (docs/PIPELINE.md, stages 1-10)."""

import hashlib

import pytest

from app.core.drawing.model import (
    COUNT_KEYS,
    Drawing,
    Element,
    Mark,
    MeasuredValue,
    MeasureMethod,
    Page,
    Scale,
    Subject,
)
from app.core.errors import InvalidInputError
from app.core.pipeline.extract import extract
from app.core.pipeline.group import group
from app.core.pipeline.identify import identify, sniff
from app.core.pipeline.inventory import file_entry
from app.core.pipeline.model import (
    DrawingFile,
    DrawingGroup,
    Extracted,
    FileKind,
    Measurement,
    Routed,
    SetAside,
    Sheet,
)
from app.core.pipeline.normalise import normalise
from app.core.pipeline.route import route
from app.core.pipeline.rules import AS_GIVEN, EACH_ONCE, apply_rules
from app.core.pipeline.second_count import element_counts, second_count
from app.core.pipeline.takeoff import known_quantities, take_off

PAGE = Page(page=1, width=100, height=50, unit="px")
NO_SCALE = Scale(status="no_scale")
BOX = (0.1, 0.2, 0.3, 0.4)


def a_file(path: str, kind: FileKind) -> DrawingFile:
    return DrawingFile(path=path, size=1, sha256="0" * 64, kind=kind)


def two_doors(method: MeasureMethod = "parser") -> Extracted:
    doors = tuple(Element(id=f"e{n}", class_="door", page=1, box=BOX) for n in (1, 2))
    return Extracted(method=method, scale=NO_SCALE, elements=doors)


def counted(name: str, value: float, method: MeasureMethod) -> Measurement:
    return Measurement(
        quantity="element_count",
        subject=Subject(kind="class", ref=name),
        value=MeasuredValue(value=value, unit="count", method=method),
    )


# Stages 1-2: inventory and hash


def test_inventory_records_size_and_sha256() -> None:
    entry = file_entry("data/demo/a.png", b"abc")
    assert entry.path == "data/demo/a.png"
    assert entry.size == 3
    assert entry.sha256 == hashlib.sha256(b"abc").hexdigest()


# Stage 3: identify


@pytest.mark.parametrize(
    ("data", "kind"),
    [
        (b"%PDF-1.7\n...", "pdf"),
        (b"\x89PNG\r\n\x1a\n....", "png"),
        (b"\xff\xd8\xff\xe0..JFIF", "jpeg"),
        (b"ISO-10303-21;\nHEADER;", "ifc"),
        (b'<?xml version="1.0"?>\n<svg xmlns="http://www.w3.org/2000/svg">', "svg"),
        (b"<svg viewBox='0 0 1 1'></svg>", "svg"),
        (b"  0\r\nSECTION\r\n  2\r\nHEADER\r\n", "dxf"),
        (b"AutoCAD Binary DXF\r\n\x1a\x00", "dxf"),
        (b'<?xml version="1.0"?>\n<html></html>', None),
        (b"Door schedule, revision 3", None),
        (b"", None),
    ],
)
def test_sniff_reads_the_format_from_the_content(data: bytes, kind: str | None) -> None:
    assert sniff(data) == kind


def test_identify_ignores_the_extension() -> None:
    png_named_pdf = identify(
        file_entry("data/demo/a.pdf", b"\x89PNG\r\n\x1a\n"), b"\x89PNG\r\n\x1a\n"
    )
    assert isinstance(png_named_pdf, DrawingFile)
    assert png_named_pdf.kind == "png"


def test_identify_sets_aside_what_is_not_a_drawing_format() -> None:
    found = identify(file_entry("data/demo/notes.txt", b"hello"), b"hello")
    assert found == SetAside(path="data/demo/notes.txt", reason="not a drawing format we read")


# Stage 4: group


def test_group_puts_same_named_files_of_a_folder_together() -> None:
    files = [
        a_file("data/swiss/plan1.pdf", "pdf"),
        a_file("data/cubi/plan1.png", "png"),
        a_file("data/swiss/plan1.png", "png"),
        a_file("data/swiss/plan2.v2.png", "png"),
    ]
    groups = group(files)
    assert [(found.key, [file.path for file in found.files]) for found in groups] == [
        ("data/swiss/plan1", ["data/swiss/plan1.pdf", "data/swiss/plan1.png"]),
        ("data/cubi/plan1", ["data/cubi/plan1.png"]),
        ("data/swiss/plan2.v2", ["data/swiss/plan2.v2.png"]),
    ]


# Stage 5: route


@pytest.mark.parametrize(
    ("kinds", "expected_route", "expected_source"),
    [
        (["png", "pdf", "dxf"], "cad", "dxf"),
        (["png", "pdf"], "vector", "pdf"),
        (["jpeg"], "raster", "jpeg"),
        (["pdf", "ifc"], "bim", "ifc"),
        (["svg", "pdf"], "vector", "svg"),
    ],
)
def test_route_picks_the_richest_source(
    kinds: list[FileKind], expected_route: str, expected_source: str
) -> None:
    files = tuple(a_file(f"data/demo/x.{kind}", kind) for kind in kinds)
    routed = route(DrawingGroup(key="data/demo/x", files=files))
    assert (routed.route, routed.source.kind) == (expected_route, expected_source)


# Stage 6: normalise


def test_normalise_keeps_the_pages_as_the_file_gives_them() -> None:
    file = a_file("data/demo/a.png", "png")
    assert normalise(file, [PAGE]) == Sheet(file=file, pages=(PAGE,))


@pytest.mark.parametrize("pages", [[], [Page(page=2, width=1, height=1, unit="pt")]])
def test_normalise_refuses_pages_that_are_not_numbered_from_one(pages: list[Page]) -> None:
    with pytest.raises(InvalidInputError, match="must be numbered"):
        normalise(a_file("data/demo/a.pdf", "pdf"), pages)


# Stage 7: extract


class RecordingExtractor:
    def __init__(self, found: Extracted) -> None:
        self.found = found
        self.calls: list[tuple[str, str]] = []

    def extract(self, source: DrawingFile, sheet: Sheet) -> Extracted:
        self.calls.append((source.path, sheet.file.path))
        return self.found


def test_extract_calls_the_extractor_of_the_route_with_the_source_and_the_sheet() -> None:
    pdf, png = a_file("data/demo/a.pdf", "pdf"), a_file("data/demo/a.png", "png")
    vector, raster = RecordingExtractor(two_doors()), RecordingExtractor(two_doors("detector"))
    found = extract(
        Routed(route="vector", source=pdf),
        Sheet(file=png, pages=(PAGE,)),
        {"vector": vector, "raster": raster},
    )
    assert found == two_doors()
    assert vector.calls == [("data/demo/a.pdf", "data/demo/a.png")]
    assert raster.calls == []


# Stage 8: second count


def test_element_counts_gives_every_class_with_the_extractors_method() -> None:
    first = element_counts(two_doors())
    values = {one.subject.ref: one.value.value for one in first}
    assert values["door"] == 2
    assert values["window"] == 0
    assert {one.value.method for one in first} == {"parser"}
    assert {one.quantity for one in first} == {"element_count"}


def test_second_count_keeps_both_values_and_says_whether_they_agree() -> None:
    again = [counted("door", 3, "detector"), counted("window", 0, "detector")]
    door, window = second_count(element_counts(two_doors()), again)
    assert (door.id, door.status, door.tolerance) == ("c1", "conflict", 0.0)
    assert [(value.value, value.method) for value in door.values] == [
        (2.0, "parser"),
        (3.0, "detector"),
    ]
    assert door.subject == Subject(kind="class", ref="door")
    assert door.resolution is None
    assert (window.id, window.status) == ("c2", "agree")


def test_second_count_compares_measures_within_two_percent() -> None:
    def area(value: float, method: MeasureMethod) -> Measurement:
        return Measurement(
            quantity="room_area",
            subject=Subject(kind="room", ref="r1"),
            value=MeasuredValue(value=value, unit="m2", method=method),
        )

    (close,) = second_count([area(100.0, "printed_label")], [area(101.9, "polygon_x_scale")])
    (far,) = second_count([area(100.0, "printed_label")], [area(103.0, "polygon_x_scale")])
    assert (close.status, close.tolerance) == ("agree", 0.02)
    assert far.status == "conflict"


def test_second_count_has_no_entry_for_what_only_one_method_measured() -> None:
    assert second_count(element_counts(two_doors()), []) == []
    assert second_count([], [counted("door", 3, "detector")]) == []


def test_second_count_refuses_a_second_value_from_the_same_method() -> None:
    with pytest.raises(ValueError, match="not an independent count"):
        second_count(element_counts(two_doors()), [counted("door", 2, "parser")])


# Stage 9: rules


def test_rules_count_every_listed_item_once() -> None:
    marks = (Mark(page=1, box=BOX), Mark(page=1, box=BOX))
    selected = apply_rules({"door": marks, "window": ()})
    assert selected["door"].marks == marks
    assert selected["window"].marks == ()
    assert {found.rule.id for found in selected.values()} == {EACH_ONCE.id}


# Stage 10: takeoff


def a_drawing(found: Extracted, counts: dict[str, int] | None = None) -> Drawing:
    return Drawing(
        file="data/demo/a.png",
        pages=(PAGE,),
        scale=found.scale,
        elements=found.elements,
        counts=counts,
    )


def test_takeoff_gives_every_count_with_its_marks_and_rule() -> None:
    drawing = a_drawing(two_doors())
    quantities = take_off(drawing, apply_rules(drawing.marks_by_quantity()))
    assert tuple(quantities) == COUNT_KEYS
    door = quantities["door"]
    assert (door.value, door.unit, door.rule) == (2, "count", "each-once")
    assert door.marks == (Mark(page=1, box=BOX), Mark(page=1, box=BOX))
    assert quantities["bathtub"].value == 0
    assert quantities["bathtub"].marks == ()


def test_takeoff_of_stated_totals_gives_only_those_without_marks() -> None:
    drawing = a_drawing(Extracted(method="other", scale=NO_SCALE), counts={"door": 9, "plan": 1})
    quantities = known_quantities(drawing)
    assert set(quantities) == {"door", "plan"}
    assert (quantities["door"].value, quantities["door"].marks) == (9, ())
    assert quantities["door"].rule == AS_GIVEN.id


def test_known_quantities_runs_rules_then_takeoff() -> None:
    drawing = a_drawing(two_doors())
    assert known_quantities(drawing) == take_off(drawing, apply_rules(drawing.marks_by_quantity()))

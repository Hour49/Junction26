"""DOUBLE_CHECK_READERS: the raster route also keeps what other readers saw on the sheet, next to
the drawing and never in its counts, so an answer can say where they disagree with it. Synthetic
drawings only."""

import json
from collections.abc import Callable
from pathlib import Path

import pytest
from ingest.test_ingest_kind_wiring import drawing_png
from jsonschema import Draft202012Validator
from test_raster_composite import FILE, LEFT, PNG, RIGHT, SCHEMAS, SHEET, Fake, element, gold

from app.adapters.extraction_v1 import ExtractionV1Reader, ExtractionV1Writer
from app.adapters.raster import assemble, parse_components, parse_readers
from app.adapters.raster.precomputed import WholePagePlan
from app.composition import build_ingest, build_pipeline
from app.core.drawing.model import ELEMENT_CLASSES, Drawing, Page, ReaderView, Scale
from app.core.errors import InvalidInputError
from app.core.pipeline.disputed_marks import counted_elements, disputed_marks, reader_elements
from app.core.pipeline.model import Extracted
from app.core.pipeline.ports import Extractor
from app.settings import Settings


def test_the_setting_is_parsed_into_a_source_per_reader_name() -> None:
    assert parse_readers(" l1=detector:C-yolo26l , seg=seg:Bl,") == {
        "l1": "detector:C-yolo26l",
        "seg": "seg:Bl",
    }
    assert parse_readers("") == {}


@pytest.mark.parametrize(
    ("spec", "says"),
    [
        ("m1", "not <name>=<source>"),
        ("m1=", "not <name>=<source>"),
        ("=detector:M", "not <name>=<source>"),
        ("m1=a,m1=b", "given twice"),
        ("answer=a", "'answer' is the count itself"),
    ],
)
def test_a_bad_setting_is_refused_saying_why(spec: str, says: str) -> None:
    with pytest.raises(InvalidInputError, match=f"DOUBLE_CHECK_READERS: .*{says}"):
        parse_readers(spec)


def read_sheet(readers: dict[str, Extractor], components: str, checks: str) -> Extracted:
    composite = assemble(
        parse_components(components), readers.__getitem__, double_check=parse_readers(checks)
    )
    return composite.extract(FILE, SHEET)


def test_what_a_reader_saw_is_kept_under_its_name_and_never_counted() -> None:
    main = Fake(elements=[element("door", LEFT), element("sink", LEFT)], read=["door", "sink"])
    second = Fake(
        elements=[
            element("door", LEFT, score=0.7),
            element("window", RIGHT),
            element("door", RIGHT, score=0.4),
        ],
        read=["sink", "door", "window"],
    )
    readers: dict[str, Extractor] = {"main": main, "m": second, "one": WholePagePlan()}

    found = read_sheet(readers, "elements=main,plans=one", "m1=m")

    assert [e.class_ for e in found.elements] == ["door", "sink"]  # as without the setting
    assert found.read == ("door", "sink")
    assert found.double_check is not None
    assert list(found.double_check) == ["m1"]
    view = found.double_check["m1"]
    assert view.read == ("door", "window", "sink")  # in the order of the element classes
    assert [(e.id, e.class_, e.plan, e.box, e.attrs) for e in view.elements] == [
        ("e1", "door", "p1", LEFT, {"score": 0.7, "component": "m"}),
        ("e2", "window", "p1", RIGHT, {"score": 0.9, "component": "m"}),
        ("e3", "door", "p1", RIGHT, {"score": 0.4, "component": "m"}),
    ]
    assert "double-check readers: m1: m" in found.notes
    assert "m: fake" in found.notes  # a reader's own notes are kept like a part's


def test_a_reader_says_which_classes_it_looked_for() -> None:
    """A reader that looked for no elements (a rooms reader) says so: it is not a reader that
    saw no doors."""
    readers: dict[str, Extractor] = {
        "all": Fake(elements=[element("door", LEFT)]),  # read None: everything
        "rooms": Fake(elements=[element("door", LEFT)], read=["room"]),
        "one": WholePagePlan(),
    }

    found = read_sheet(readers, "plans=one", "a=all,r=rooms")

    assert found.double_check is not None
    assert found.double_check["a"].read == ELEMENT_CLASSES
    assert found.double_check["r"] == ReaderView(read=(), elements=())


def test_a_source_that_is_a_part_and_a_reader_reads_the_sheet_once() -> None:
    """The seg network gives the rooms and, as a reader, its icons: one pass per sheet."""
    seg = Fake(elements=[element("door", LEFT)], read=["door", "room"])
    readers: dict[str, Extractor] = {"seg": seg, "one": WholePagePlan()}

    found = read_sheet(readers, "rooms=seg,plans=one", "seg=seg")

    assert seg.calls == 1
    assert found.elements == ()  # the composite's elements have no source here
    assert found.double_check is not None
    assert [e.class_ for e in found.double_check["seg"].elements] == ["door"]


def test_without_the_setting_nothing_is_kept_and_the_drawing_is_written_as_before() -> None:
    readers: dict[str, Extractor] = {"main": Fake(elements=[element("door", LEFT)])}
    readers["one"] = WholePagePlan()

    found = read_sheet(readers, "elements=main,plans=one", "")

    assert found.double_check is None
    assert not any("double-check" in note for note in found.notes)
    drawing = Drawing(file=PNG, pages=SHEET.pages, scale=Scale(status="no_scale"))
    assert "double_check" not in drawing.model_dump(mode="json", by_alias=True)


def door(
    name: str, box: tuple[float, float, float, float], score: float = 0.9
) -> dict[str, object]:
    return {"id": name, "class": "door", "page": 1, "box": list(box), "attrs": {"score": score}}


A = (0.1, 0.1, 0.2, 0.2)
B = (0.6, 0.6, 0.7, 0.7)


def ingested(tmp_path: Path, make_png: Callable[[int, int], bytes], name: str) -> Path:
    """What the pipeline writes for a sheet whose detector arm counts doors at A and B, with a
    second arm that sees a door at A only."""
    dataset, out = tmp_path / "dataset", tmp_path / name
    if not dataset.exists():
        (dataset / "data" / "cubicasa5k").mkdir(parents=True)
        (dataset / PNG).write_bytes(make_png(40, 30))
        for arm, doors in (("main", [door("a", A), door("b", B)]), ("second", [door("a", A)])):
            (tmp_path / arm).mkdir()
            (tmp_path / arm / "colorful-1.json").write_text(json.dumps(gold(PNG, elements=doors)))
    build_pipeline(Settings(), dataset).ingest([PNG], ExtractionV1Writer(out, {PNG: "dev"}))
    return out / "cubicasa5k" / "colorful-1.png.json"


def test_the_pipeline_writes_the_readers_views_into_the_drawing_only_with_the_setting(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, make_png: Callable[[int, int], bytes]
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("EXTRACTOR_RASTER", "composite")
    monkeypatch.setenv("RASTER_COMPONENTS", f"elements=dir:{tmp_path / 'main'},plans=one-plan")
    schema = json.loads((SCHEMAS / "extraction_v1.schema.json").read_text(encoding="utf-8"))

    off = ingested(tmp_path, make_png, "off")
    assert "double_check" not in json.loads(off.read_text(encoding="utf-8"))

    monkeypatch.setenv("DOUBLE_CHECK_READERS", f"m1=dir:{tmp_path / 'second'}")
    on = ingested(tmp_path, make_png, "on")
    body = json.loads(on.read_text(encoding="utf-8"))
    Draft202012Validator(schema).validate(body)
    assert [e["box"] for e in body["double_check"]["m1"]["elements"]] == [list(A)]
    without = {key: value for key, value in body.items() if key != "double_check"}
    as_before = json.loads(off.read_text(encoding="utf-8"))
    # the readers' notes aside, the drawing itself is the same: nothing of a reader is counted
    assert {**without, "notes": None} == {**as_before, "notes": None}

    drawing = ExtractionV1Reader(on.parents[1]).drawing(PNG)
    assert drawing is not None
    found = disputed_marks(
        counted_elements(drawing, "door"), reader_elements(drawing, "door"), noun="door", k=1
    )
    assert [(mark.mark_id, mark.box) for mark in found] == [("e2", B)]
    assert found[0].readers == {"answer": "door, score 0.90", "m1": "nothing"}


def test_the_setting_needs_the_composite_and_sources_that_build(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("DOUBLE_CHECK_READERS", "m1=one-plan")
    with pytest.raises(InvalidInputError, match="DOUBLE_CHECK_READERS needs EXTRACTOR_RASTER"):
        build_pipeline(Settings(), tmp_path)

    monkeypatch.setenv("EXTRACTOR_RASTER", "composite")
    monkeypatch.setenv("RASTER_COMPONENTS", "plans=one-plan")
    build_pipeline(Settings(), tmp_path)  # a source that builds

    monkeypatch.setenv("DOUBLE_CHECK_READERS", "m1=nowhere")
    with pytest.raises(InvalidInputError, match=r"DOUBLE_CHECK_READERS='m1=nowhere': .*unknown"):
        build_pipeline(Settings(), tmp_path)


def test_the_setting_is_part_of_the_ingest_reuse_key_only_when_on(tmp_path: Path) -> None:
    def readers(**on: str) -> dict[str, str]:
        settings = Settings(_env_file=None, **on)  # pyright: ignore[reportCallIssue]
        ingest = build_ingest(settings, tmp_path / "projects", background=False)
        status = ingest.status(ingest.start("plan.png", drawing_png()))
        ingest.close()
        return status.readers

    assert "double_check_readers" not in readers()  # the default keeps the keys it had before
    on = readers(
        extractor_raster="composite",
        raster_components="plans=one-plan",
        double_check_readers="m1=one-plan",
    )
    assert on["double_check_readers"] == "m1=one-plan"


def drawing_with(**views: ReaderView) -> Drawing:
    counted = [element("door", LEFT), element("shower", LEFT), element("bathtub", RIGHT)]
    return Drawing(
        file=PNG,
        pages=(Page(page=1, width=40, height=30, unit="px"),),
        scale=Scale(status="no_scale"),
        elements=tuple(e.model_copy(update={"id": f"e{n}"}) for n, e in enumerate(counted, 1)),
        double_check=views or None,
    )


def test_the_accessors_give_a_familys_elements_as_counted_and_per_reader() -> None:
    seen = (element("door", LEFT), element("shower", RIGHT), element("bathtub", RIGHT))
    drawing = drawing_with(m1=ReaderView(read=("door", "shower", "bathtub"), elements=seen))

    assert [e.id for e in counted_elements(drawing, "door")] == ["e1"]
    assert [e.id for e in counted_elements(drawing, "shower+bathtub")] == ["e2", "e3"]
    assert reader_elements(drawing, "door") == {"m1": (seen[0],)}
    assert reader_elements(drawing, "shower+bathtub") == {"m1": seen[1:]}
    assert reader_elements(drawing, "sauna") == {}  # m1 did not look for stoves
    assert counted_elements(drawing, "sauna") == ()  # the stoves; this drawing has none


def test_a_reader_that_did_not_look_for_the_family_is_left_out_not_shown_as_seeing_nothing() -> (
    None
):
    drawing = drawing_with(
        m1=ReaderView(read=("door",), elements=(element("door", LEFT),)),
        seg=ReaderView(read=("shower",), elements=()),  # a shower reader that knows no bathtub
        rooms=ReaderView(read=(), elements=()),
    )

    assert list(reader_elements(drawing, "door")) == ["m1"]
    assert reader_elements(drawing, "shower+bathtub") == {}
    assert reader_elements(drawing, "room:bedroom") == {}  # element readers say nothing of rooms
    assert counted_elements(drawing, "room:bedroom") == ()
    assert reader_elements(drawing_with(), "door") == {}  # no reader ran

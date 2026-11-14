"""ROOM_POLICY: how the raster route types the rooms its reader found. `furniture` (the default)
keeps the reader's types; `gold-labels` follows the printed label, as the dataset's answers do.
Synthetic rooms only."""

import json
from collections.abc import Callable
from pathlib import Path

import pytest
from ingest.test_ingest_kind_wiring import drawing_png
from test_raster_composite import FILE, LEFT, PNG, RIGHT, SHEET, Fake, gold

from app.adapters.extraction_v1 import ExtractionV1Reader, ExtractionV1Writer
from app.adapters.raster import assemble, parse_components
from app.adapters.raster.precomputed import WholePagePlan
from app.composition import build_ingest, build_pipeline
from app.core.drawing.model import Box, Room
from app.core.pipeline.model import Extracted
from app.core.pipeline.room_policy import gold_label_rooms
from app.core.pipeline.takeoff import known_quantities
from app.settings import Settings


def room(kind: str, label: str | None, box: Box = LEFT) -> Room:
    return Room(id="x", type=kind, label=label, page=1, box=box)  # type: ignore[arg-type]


def retyped(kind: str, label: str | None) -> str:
    return gold_label_rooms([room(kind, label)])[0].type


@pytest.mark.parametrize("label", [None, "", "  "])
def test_a_bedroom_without_a_printed_label_is_not_a_bedroom(label: str | None) -> None:
    assert retyped("bedroom", label) == "other"


@pytest.mark.parametrize("label", ["ALKOVI", "alk.", "ALK\n6,0 m²"])
def test_an_alcove_is_a_hall_not_a_bedroom(label: str) -> None:
    assert retyped("bedroom", label) == "hall"


@pytest.mark.parametrize("label", ["WC", "wc\n1,5 m²", " WC/KH"])
def test_a_bathroom_labelled_wc_is_a_wc(label: str) -> None:
    assert retyped("bathroom", label) == "wc"


@pytest.mark.parametrize(
    ("kind", "label"),
    [("living", "APUK."), ("storage", "APK"), ("living", "TUPAKEITTIÖ\n24,0 m²"), ("hall", "apuk")],
)
def test_a_utility_kitchen_or_a_kitchen_living_room_is_a_kitchen(kind: str, label: str) -> None:
    assert retyped(kind, label) == "kitchen"


@pytest.mark.parametrize(
    ("kind", "label"),
    [
        ("bedroom", "MH"),  # a labelled bedroom stays
        ("bedroom", "MH\nALK"),  # only the label's first line is read
        ("bathroom", "KPH"),
        ("bathroom", "WCS"),  # WC as a whole word only
        ("wc", None),  # the empty-label rule is about bedrooms only
        ("living", None),
        ("living", "APKX"),  # APK as a whole word only
        ("kitchen", "APUK."),
        ("hall", "ALK"),  # the alcove rule only retypes a bedroom
    ],
)
def test_every_other_room_keeps_the_type_its_reader_gave(kind: str, label: str | None) -> None:
    assert gold_label_rooms([kept := room(kind, label)]) == (kept,)


def test_a_retyped_room_changes_only_its_type_and_says_what_it_was() -> None:
    first, second = room("bedroom", None, LEFT), room("kitchen", "K", RIGHT)
    changed, same = gold_label_rooms([first, second])
    assert changed == first.model_copy(
        update={"type": "other", "attrs": {"retyped_from": "bedroom"}}
    )
    assert same == second


ROOMS = [room("bedroom", None), room("bedroom", "ALKOVI"), room("bathroom", "WC", RIGHT)]


def read_rooms(**policy: Callable[..., object]) -> Extracted:
    parts = parse_components("rooms=ocr,plans=one")
    readers = {"ocr": Fake(rooms=ROOMS, read=["room"]), "one": WholePagePlan()}
    return assemble(parts, readers.__getitem__, **policy).extract(FILE, SHEET)  # type: ignore[arg-type]


def test_the_composite_applies_the_policy_to_its_rooms_source_and_notes_it() -> None:
    found = read_rooms(room_policy=gold_label_rooms)
    assert [(r.id, r.type, r.plan) for r in found.rooms] == [
        ("r1", "other", "p1"),
        ("r2", "hall", "p1"),
        ("r3", "wc", "p1"),
    ]
    assert found.rooms[0].attrs == {"retyped_from": "bedroom", "component": "ocr"}
    assert "room policy: 3 of 3 rooms retyped by their printed label" in found.notes


def test_without_a_policy_the_composite_gives_the_readers_rooms_and_no_note() -> None:
    found = read_rooms()
    assert [r.type for r in found.rooms] == ["bedroom", "bedroom", "bathroom"]
    assert all(r.attrs == {"component": "ocr"} for r in found.rooms)
    assert not any("room policy" in note for note in found.notes)


def written(tmp_path: Path, make_png: Callable[[int, int], bytes], name: str) -> Path:
    """The extraction the pipeline writes for a sheet whose rooms arm typed by furniture."""
    dataset, arm, out = tmp_path / "dataset", tmp_path / "arm", tmp_path / name
    if not arm.exists():
        (dataset / "data" / "cubicasa5k").mkdir(parents=True)
        (dataset / PNG).write_bytes(make_png(40, 30))
        arm.mkdir()
        rooms = [r.model_dump(mode="json") for r in ROOMS]
        (arm / "colorful-1.json").write_text(json.dumps(gold(PNG, rooms=rooms)))
    build_pipeline(Settings(), dataset).ingest([PNG], ExtractionV1Writer(out, {PNG: "dev"}))
    return out


def counts(out: Path) -> dict[str, object]:
    drawing = ExtractionV1Reader(out).drawing(PNG)
    assert drawing is not None
    quantities = known_quantities(drawing)
    return {kind: quantities[f"room:{kind}"].value for kind in ("bedroom", "bathroom", "wc")}


def test_the_setting_decides_what_the_pipeline_counts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, make_png: Callable[[int, int], bytes]
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("EXTRACTOR_RASTER", "composite")
    monkeypatch.setenv("RASTER_COMPONENTS", f"rooms=dir:{tmp_path / 'arm'},plans=one-plan")

    default = written(tmp_path, make_png, "default")  # ROOM_POLICY unset: furniture
    assert counts(default) == {"bedroom": 2, "bathroom": 1, "wc": 0}

    monkeypatch.setenv("ROOM_POLICY", "furniture")
    furniture = written(tmp_path, make_png, "furniture")
    file = Path("cubicasa5k") / "colorful-1.png.json"
    assert (furniture / file).read_bytes() == (default / file).read_bytes()
    assert b"retyped" not in (furniture / file).read_bytes()

    monkeypatch.setenv("ROOM_POLICY", "gold-labels")
    assert counts(written(tmp_path, make_png, "gold")) == {"bedroom": 0, "bathroom": 0, "wc": 1}


def test_the_setting_is_part_of_the_ingest_reuse_key_only_when_not_the_default(
    tmp_path: Path,
) -> None:
    def readers(**on: str) -> dict[str, str]:
        settings = Settings(_env_file=None, **on)  # pyright: ignore[reportCallIssue]
        ingest = build_ingest(settings, tmp_path / "projects", background=False)
        status = ingest.status(ingest.start("plan.png", drawing_png()))
        ingest.close()
        return status.readers

    assert "room_policy" not in readers()  # the default keeps the keys it had before
    assert readers(room_policy="gold-labels")["room_policy"] == "gold-labels"

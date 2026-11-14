"""The Carbon reader (app/adapters/carbon/; contract .agents/exp/carbon-reader.md): the contract
copy, the calls and their cache, what a failed call leaves, the spend, and the wiring. Every test
runs on a fake model or a stubbed urlopen: no network, no data/."""

import io
import json
import urllib.request
from pathlib import Path
from typing import Any

import pytest
from PIL import Image, ImageDraw

from app.adapters.carbon import CarbonClient, CarbonExtractor, CarbonReader, CarbonSwitch
from app.adapters.carbon import contract as c
from app.adapters.pdf_tables import PdfTables
from app.adapters.raster_scale import PriorScale
from app.composition import build_ingest, build_pipeline, uses_keys
from app.core import cost
from app.core.drawing.model import Page
from app.core.errors import InvalidInputError
from app.core.ingest.judge import CARBON_FLAG, judge, reading_flags
from app.core.pipeline.model import DrawingFile, Extracted, Sheet
from app.core.spend import SpendGuard
from app.settings import Settings
from scripts.make_sample_archive import png_bytes, raster_plan

KEY = "test-key-0123456789"


@pytest.fixture(autouse=True)
def _cost_left_as_found() -> Any:
    """These tests charge `cost`'s per-thread float; put it back exactly, so a later test that
    compares a difference of it with == (test_ingest_triage) sees the counter it would alone."""
    before = cost.spent()
    yield
    cost._local.usd = before  # pyright: ignore[reportPrivateUsage]


# --- the contract, as copied -------------------------------------------------------------------


def test_the_contract_copy_is_the_one_confidence_scores() -> None:
    # prototypes/carbon-reader/contract.py prints this; a changed prompt, schema or rule changes it
    assert c.READER_SHA == "dcb03cd7955c4fb2e4f5fcc80b0bdb5c5348e59183aea1220b5d22f2ebf3bf2e"
    assert c.SOURCE == "carbon:dcb03cd7955c"


def test_tile_plan_sizes_and_limits() -> None:
    assert c.tile_plan(926, 700, []) == [(0, 0, 926, 700)]
    assert c.tile_plan(8000, 6000, []) == []  # a large page with no plan: nothing to tile
    big = c.tile_plan(8000, 6000, [(0.1, 0.1, 0.9, 0.9)])
    assert big is not None and len(big) == 6
    assert all(x1 - x0 <= c.TILE and y1 - y0 <= c.TILE for x0, y0, x1, y1 in big)
    assert big[0][2] - big[1][0] >= c.OVERLAP
    assert c.tile_plan(14000, 10000, [(0.0, 0.0, 1.0, 1.0)]) is None  # 24 tiles: not tiled
    assert c.sent_size(926, 700) == (1536, 1161) and c.sent_size(6000, 3000) == (3072, 1536)


def test_assemble_without_tiles_reads_no_element_class() -> None:
    untiled = c.assemble(14000, 10000, page_form(), None, [])
    assert untiled["read"] == ["room"] and untiled["elements"] == []


# --- the reader on a fake model ----------------------------------------------------------------


def page_form(**changes: Any) -> dict[str, Any]:
    form: dict[str, Any] = {
        "seen": "a flat",
        "title_block": {"title": "PLAN", "sheet_number": None, "project": None, "date": None,
                        "revision": None},
        "printed_scale": "1:100",
        "plans": [{"name": None, "box_2d": [0, 0, 1000, 1000]}],
        "rooms": [
            {"type": "bedroom", "label": "MH", "area_m2": 12.5, "box_2d": [100, 100, 400, 400]},
            {"type": "kitchen", "label": "K", "area_m2": None, "box_2d": [500, 500, 700, 700]},
        ],
        "rooms_listed": "all",
        "printed_facts": [{"text": "2 FLATS", "subject": "room", "value": 2, "unit": "count",
                           "box_2d": [0, 0, 10, 10]}],
        "tables": [],
    }  # fmt: skip
    return {**form, **changes}


def tile_form(*elements: tuple[str, list[int]], unreadable: tuple[str, ...] = ()) -> dict[str, Any]:
    return {
        "elements": [{"class": kind, "box_2d": box} for kind, box in elements],
        "rooms_seen": [],
        "unreadable": list(unreadable),
    }


def answer(form: object, usd_tokens: int = 1000) -> dict[str, Any]:
    text = form if isinstance(form, str) else json.dumps(form)
    return {
        "candidates": [{"content": {"parts": [{"text": text}]}}],
        "usageMetadata": {"promptTokenCount": usd_tokens, "candidatesTokenCount": 0},
    }


class FakeCarbon:
    """Answers the page call with `page` and a tile call with `tiles[i]`, i chosen by the colour
    of the tile's top-left pixel (dark: tile 0), so parallel calls stay deterministic. Each call
    charges 0.01 USD on its own thread, as the real client does."""

    def __init__(self, page: object, tiles: list[object]) -> None:
        self.page = page
        self.tiles = tiles
        self.calls: list[str] = []

    def generate(
        self, jpeg: bytes, prompt: str, schema: dict[str, Any], max_tokens: int
    ) -> dict[str, Any]:
        from app.adapters.raster_ocr.gemini import GeminiError

        assert jpeg[:2] == b"\xff\xd8"  # a JPEG
        cost.charge(0.01)
        if schema is c.PAGE_SCHEMA:
            self.calls.append("page")
            reply = self.page
        else:
            assert schema is c.TILE_SCHEMA and prompt == c.TILE_PROMPT
            with Image.open(io.BytesIO(jpeg)) as image:
                dark = image.convert("L").getpixel((3, 3))
            index = 0 if isinstance(dark, int) and dark < 128 else 1
            self.calls.append(f"tile{index}")
            reply = self.tiles[index]
        if isinstance(reply, Exception):
            raise GeminiError(str(reply))
        return answer(reply)


def page_image(width: int, height: int) -> Image.Image:
    image = Image.new("RGB", (width, height), "white")
    ImageDraw.Draw(image).rectangle((0, 0, 99, 99), fill="black")  # tile 0's corner is dark
    return image


def test_a_small_page_is_one_page_call_and_one_tile_call(tmp_path: Path) -> None:
    model = FakeCarbon(page_form(), [tile_form(("door", [100, 100, 200, 130]),
                                               ("toilet", [300, 300, 340, 340]))])  # fmt: skip
    found = CarbonReader(model, tmp_path).read(page_image(900, 700))
    assert sorted(model.calls) == ["page", "tile0"]
    assert found.read == ("room", *c.CLASSES)
    assert [e.class_ for e in found.elements] == ["door", "toilet"]
    assert found.elements[0].attrs["reader"] == c.SOURCE
    assert [r.type for r in found.rooms] == ["bedroom", "kitchen"]
    bedroom = found.rooms[0]
    assert (bedroom.area_m2, bedroom.area_status, bedroom.area_source) == (12.5, "exact", "printed")
    assert found.rooms[1].area_m2 is None  # no area from geometry
    assert found.scale.status == "no_scale" and found.scale.text == "1:100"
    assert len(found.plans) == 1 and found.method == "detector"
    assert found.notes[0] == f"carbon: {c.SOURCE} (gemini-4-carbon, carbon-reader-1)"
    assert "carbon: printed on the sheet: 2 FLATS" in found.notes


def test_a_large_page_is_tiled_from_the_plan_boxes_and_a_door_two_tiles_saw_is_one(
    tmp_path: Path,
) -> None:
    # 3600 x 1000 with the plan on all of it: tiles (0-1950) and (1650-3600), 300 px shared
    door_left = ("door", [400, 872, 500, 923])  # page x 1700-1800, seen by tile 0 ...
    door_right = ("door", [400, 26, 500, 77])  # ... and by tile 1
    two = (("door", [100, 100, 200, 150]), ("door", [100, 160, 200, 210]))  # side by side
    model = FakeCarbon(page_form(), [tile_form(door_left, *two), tile_form(door_right)])
    found = CarbonReader(model, tmp_path).read(page_image(3600, 1000))
    assert model.calls[0] == "page" and sorted(model.calls[1:]) == ["tile0", "tile1"]
    doors = [e for e in found.elements if e.class_ == "door"]
    assert len(doors) == 3
    shared = [e for e in doors if e.attrs.get("tiles") == "0,1"]
    assert len(shared) == 1 and shared[0].box[0] == pytest.approx(1700 / 3600, abs=0.001)


def test_a_class_a_tile_cannot_count_is_not_read_and_lists_nothing(tmp_path: Path) -> None:
    tile = tile_form(("door", [100, 100, 200, 130]), ("sink", [300, 300, 340, 340]),
                     unreadable=("door",))  # fmt: skip
    found = CarbonReader(FakeCarbon(page_form(), [tile]), tmp_path).read(page_image(900, 700))
    assert "door" not in (found.read or ()) and "sink" in (found.read or ())
    assert [e.class_ for e in found.elements] == ["sink"]  # a partial door list is no count


def test_rooms_listed_some_reads_no_room(tmp_path: Path) -> None:
    model = FakeCarbon(page_form(rooms_listed="some"), [tile_form()])
    found = CarbonReader(model, tmp_path).read(page_image(900, 700))
    assert "room" not in (found.read or ()) and "door" in (found.read or ())


def test_a_failed_page_call_reads_nothing_and_caches_nothing(tmp_path: Path) -> None:
    model = FakeCarbon(RuntimeError("HTTP 503 UNAVAILABLE"), [tile_form()])
    found = CarbonReader(model, tmp_path).read(page_image(900, 700))
    assert found.read == ()
    assert found.notes[0].startswith("carbon: not read: the page call failed: HTTP 503")
    assert not any(p.name.startswith("carbon-page-") for p in tmp_path.iterdir())


def test_a_reply_that_is_not_the_form_is_a_failed_call_and_is_not_cached(tmp_path: Path) -> None:
    model = FakeCarbon({"seen": "half a reply"}, [tile_form()])
    found = CarbonReader(model, tmp_path).read(page_image(900, 700))
    assert found.read == () and "not the form" in found.notes[0]
    assert not any(p.name.startswith("carbon-page-") for p in tmp_path.iterdir())


def test_a_failed_tile_call_reads_no_element_class_and_keeps_the_rooms(tmp_path: Path) -> None:
    model = FakeCarbon(page_form(), [tile_form(("door", [400, 872, 500, 923])),
                                     RuntimeError("timeout")])  # fmt: skip
    found = CarbonReader(model, tmp_path).read(page_image(3600, 1000))
    assert found.read == ("room",) and found.elements == ()
    assert len(found.rooms) == 2
    assert "carbon: elements not read: 1 of 2 tile calls failed" in found.notes
    assert "carbon: the tile call failed: timeout" in found.notes


def test_calls_on_the_pool_are_charged_to_the_caller_and_a_cached_read_is_free(
    tmp_path: Path,
) -> None:
    model = FakeCarbon(page_form(), [tile_form(), tile_form()])
    reader = CarbonReader(model, tmp_path)
    before = cost.spent()
    reader.read(page_image(3600, 1000))
    assert cost.spent() - before == pytest.approx(0.03)  # page + 2 tiles, on other threads
    assert len(model.calls) == 3
    before = cost.spent()
    again = reader.read(page_image(3600, 1000))
    assert len(model.calls) == 3 and cost.spent() == before
    assert again.read == ("room", *c.CLASSES)
    names = sorted(p.name for p in tmp_path.iterdir())
    assert len(names) == 3 and all(n.endswith(f"-{c.MODEL}-{c.THINKING}.json") for n in names)


def test_a_cached_file_that_does_not_parse_is_a_miss(tmp_path: Path) -> None:
    model = FakeCarbon(page_form(), [tile_form()])
    CarbonReader(model, tmp_path).read(page_image(900, 700))
    for path in tmp_path.iterdir():
        path.write_text("{not json")
    CarbonReader(model, tmp_path).read(page_image(900, 700))
    assert len(model.calls) == 4


def test_the_extractor_applies_the_room_policy_to_its_own_rooms(tmp_path: Path) -> None:
    class Files:
        def read(self, path: str) -> bytes:
            buffer = io.BytesIO()
            page_image(900, 700).save(buffer, format="PNG")
            return buffer.getvalue()

    reader = CarbonReader(FakeCarbon(page_form(), [tile_form()]), tmp_path)
    sheet = Sheet(file=DrawingFile(path="a.png", size=1, sha256="0" * 64, kind="png"),
                  pages=(Page(page=1, width=900, height=700, unit="px"),))  # fmt: skip
    found = CarbonExtractor(Files(), reader, lambda rooms: [  # pyright: ignore[reportArgumentType]
        r.model_copy(update={"type": "other"}) for r in rooms
    ]).extract(sheet.file, sheet)  # fmt: skip
    assert [r.type for r in found.rooms] == ["other", "other"]


# --- the client --------------------------------------------------------------------------------


def test_the_client_sends_the_contract_body_and_charges_4_20(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sent: list[urllib.request.Request] = []

    def reply(request: urllib.request.Request, timeout: float) -> Any:
        sent.append(request)
        # small sums: cost's per-thread counter is a float other tests take differences of
        usage = {"promptTokenCount": 1000, "candidatesTokenCount": 100, "thoughtsTokenCount": 100}
        return io.BytesIO(json.dumps({**answer(tile_form()), "usageMetadata": usage}).encode())

    monkeypatch.setattr(urllib.request, "urlopen", reply)
    guard = SpendGuard()
    before = cost.spent()
    CarbonClient(KEY, 5, guard).generate(b"\xff\xd8jpeg", c.TILE_PROMPT, c.TILE_SCHEMA, 8192)
    usd = (1000 * 4.00 + 200 * 20.00) / 1e6  # thinking billed as output
    assert guard.spent_by() == {"carbon reader": pytest.approx(usd)}
    assert cost.spent() - before == pytest.approx(usd)
    (request,) = sent
    assert request.full_url.endswith("/gemini-4-carbon:generateContent")
    assert KEY not in request.full_url and request.get_header("X-goog-api-key") == KEY
    body = json.loads(request.data)  # pyright: ignore[reportArgumentType]
    assert body["contents"][0]["parts"][0]["inlineData"]["mimeType"] == "image/jpeg"
    assert body["generationConfig"]["responseSchema"] == c.TILE_SCHEMA


def test_a_spent_budget_is_a_failed_page_call_with_no_request(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def refuse(request: urllib.request.Request, timeout: float) -> Any:
        raise AssertionError("no request may be sent")

    monkeypatch.setattr(urllib.request, "urlopen", refuse)
    reader = CarbonReader(CarbonClient(KEY, 5, SpendGuard(total_usd=0)), tmp_path)
    found = reader.read(page_image(900, 700))
    assert found.read == () and "Gemini budget used up" in found.notes[0]


# --- wiring ------------------------------------------------------------------------------------


def carbon_settings(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, **env: str) -> Settings:
    monkeypatch.chdir(tmp_path)  # so a developer's backend/.env can't change the result
    values = {"EXTRACTOR_RASTER": "composite", "RASTER_COMPONENTS": "plans=one-plan",
              "GEMINI_API_KEY": KEY, **env}  # fmt: skip
    for name, value in values.items():
        monkeypatch.setenv(name, value)
    return Settings()


def test_carbon_reader_off_changes_nothing(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    settings = carbon_settings(monkeypatch, tmp_path)
    pipeline = build_pipeline(settings, tmp_path)
    assert pipeline.carbon_read is None
    raster = pipeline.extractors["raster"]
    assert isinstance(raster, PdfTables)
    assert not isinstance(raster._inner, CarbonSwitch)  # pyright: ignore[reportPrivateUsage]
    assert not uses_keys(settings)
    ingest = build_ingest(settings, tmp_path / "projects", background=False)
    assert "carbon_reader" not in ingest._names  # pyright: ignore[reportPrivateUsage]


def test_carbon_reader_all_sends_every_raster_drawing_to_carbon_with_no_door_prior_scale(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    settings = carbon_settings(monkeypatch, tmp_path, CARBON_READER="all", RASTER_SCALE="priors")
    pipeline = build_pipeline(settings, tmp_path)
    assert pipeline.carbon_read is not None and pipeline.carbon_read("a.png")
    switch = pipeline.extractors["raster"]._inner  # pyright: ignore[reportAttributeAccessIssue]
    assert isinstance(switch, CarbonSwitch)
    assert isinstance(switch._carbon, CarbonExtractor)  # pyright: ignore[reportPrivateUsage]
    assert isinstance(
        switch._other, PriorScale
    )  # the shipped branch only # pyright: ignore[reportPrivateUsage]
    assert uses_keys(settings)
    ingest = build_ingest(settings, tmp_path / "projects", background=False)
    names = ingest._names  # pyright: ignore[reportPrivateUsage]
    assert names["carbon_reader"] == f"all:{c.READER_SHA[:12]}"


def test_carbon_reader_advanced_refuses_to_start_without_the_sheet_kind_step(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    settings = carbon_settings(monkeypatch, tmp_path, CARBON_READER="advanced")
    assert uses_keys(settings)
    with pytest.raises(
        InvalidInputError,
        match=r"CARBON_READER=advanced reads the sheet-kind step's `advanced` flag: set SHEET_KIND",
    ):
        build_pipeline(settings, tmp_path)


def test_carbon_needs_the_composite_raster_reader(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    settings = carbon_settings(monkeypatch, tmp_path, EXTRACTOR_RASTER="hello", CARBON_READER="all")
    with pytest.raises(InvalidInputError, match="CARBON_READER needs EXTRACTOR_RASTER=composite"):
        build_pipeline(settings, tmp_path)


def test_carbon_is_a_source_and_a_second_reader(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    settings = carbon_settings(monkeypatch, tmp_path, RASTER_COMPONENTS="plans=one-plan",
                               DOUBLE_CHECK_READERS="c1=carbon")  # fmt: skip
    pipeline = build_pipeline(settings, tmp_path)
    assert pipeline.carbon_read is None  # a second reader flags nothing
    assert uses_keys(settings)
    ingest = build_ingest(settings, tmp_path / "projects", background=False)
    names = ingest._names  # pyright: ignore[reportPrivateUsage]
    assert names["carbon_reader"] == f"off:{c.READER_SHA[:12]}"  # a new prompt reads again


# --- the flag at ingest ------------------------------------------------------------------------


def test_a_drawing_carbon_read_alone_is_flagged() -> None:
    from app.core.drawing.model import Drawing, Scale

    drawing = Drawing(file="a.png", pages=(Page(page=1, width=9, height=9, unit="px"),),
                      scale=Scale(status="no_scale"), read=("door", "room"))  # fmt: skip
    assert reading_flags("png_plan", None, carbon=True) == (CARBON_FLAG,)
    assert reading_flags("photo_plan", None, carbon=True)[-1] == CARBON_FLAG
    assert reading_flags("png_plan", None) == ()
    state, reason = judge(drawing, "png_plan", "raster", "composite", None, carbon=True)
    assert state == "flagged" and reason.startswith(CARBON_FLAG)
    assert judge(drawing, "png_plan", "raster", "composite")[0] == "ready"


def test_ingest_flags_the_drawings_the_switch_sent_to_carbon(
    make_service: Any, tmp_path: Path
) -> None:
    class Reader:
        def __init__(self, files: Any) -> None:
            pass

        def extract(self, source: DrawingFile, sheet: Sheet) -> Extracted:
            from app.core.drawing.model import Scale

            return Extracted(method="detector", scale=Scale(status="no_scale"), read=("door",))

    plan = png_bytes(raster_plan())
    for carbon, flagged in ((lambda _: True, True), (None, False)):
        root = tmp_path / f"projects-{flagged}"  # each its own store: no reused outcome
        ingest = make_service(root=root, raster=Reader, carbon_read=carbon)
        (file,) = ingest.status(ingest.start("plan.png", plan)).files
        assert (CARBON_FLAG in file.reason) is flagged
        assert (file.state == "flagged") is flagged


def test_a_file_triage_set_aside_never_reaches_carbon_however_big(make_service: Any) -> None:
    """tables-fix #251 live test: the sheet-kind step's 4,000 px rule also calls set-aside
    sheets advanced. Carbon reads only what is read as a plan: a set-aside file reaches no
    reader, so it is neither read nor flagged, even with Carbon on for every path."""
    import zipfile

    from triage_fakes import FakeClassifier, steps

    asked: list[str] = []

    class Carbon:  # stands in for the Carbon reader: CarbonSwitch's carbon side
        def __init__(self, files: Any) -> None:
            pass

        def extract(self, source: DrawingFile, sheet: Sheet) -> Extracted:
            from app.core.drawing.model import Scale

            asked.append(source.path)
            return Extracted(method="detector", scale=Scale(status="no_scale"), read=("door",))

    big = png_bytes(raster_plan().resize((4200, 2975)))  # over the 4,000 px "advanced" line
    plan = png_bytes(raster_plan())
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w") as zipped:
        zipped.writestr("elevation.png", big)
        zipped.writestr("plan.png", plan)
    triage = steps(FakeClassifier({big: "other_drawing"}))
    ingest = make_service(raster=Carbon, carbon_read=lambda _: True, triage=triage)
    status = ingest.wait(ingest.start("site.zip", archive.getvalue()))
    files = {file.path: file for file in status.files}
    assert asked == ["plan.png"]
    elevation = files["elevation.png"]
    assert (elevation.state, elevation.drawing_id) == ("set_aside", None)
    assert CARBON_FLAG not in elevation.reason
    assert CARBON_FLAG in files["plan.png"].reason


def test_the_source_may_pin_the_reader_hash_and_a_stale_hash_is_refused(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    pinned = f"plans={c.SOURCE},rooms={c.SOURCE},elements={c.SOURCE}"
    settings = carbon_settings(monkeypatch, tmp_path, RASTER_COMPONENTS=pinned)
    build_pipeline(settings, tmp_path)  # builds
    names = build_ingest(settings, tmp_path / "projects", background=False)._names  # pyright: ignore[reportPrivateUsage]
    assert names["carbon_reader"] == f"off:{c.READER_SHA[:12]}"
    stale = carbon_settings(monkeypatch, tmp_path, RASTER_COMPONENTS="plans=carbon:0123456789ab")
    with pytest.raises(
        InvalidInputError, match=f"not the Carbon reader this build has \\({c.SOURCE}"
    ):
        build_pipeline(stale, tmp_path)


# --- CARBON_READER=advanced: the sheet-kind step's record (#251) -------------------------------


class SheetKinds:
    """The classifier with the sheet-kind step's record, per file's bytes: (class, advanced)."""

    def __init__(self, answers: dict[bytes, tuple[str, bool]]) -> None:
        self.answers = answers

    def classify(self, image: bytes, probed: Any) -> Any:
        from app.core.ingest.model import Classified

        kind, advanced = self.answers[image]
        plan = kind == "floor_plan"
        sheet = {
            "kind": "architectural_floor_plan" if plan else "mep_plan",
            "kind_words": "a floor plan" if plan else "a piping plan",
            "decision": "read" if plan else "set_aside", "takeoff_possible": plan,
            "confidence": 0.95 if plan else 0.05, "title": None, "sheet_number": None,
            "printed_scale": None, "advanced": advanced,
            "advanced_why": "over 4,000 px on its long side" if advanced else None,
            "seen": "a sheet", "model": "fake sheet kind",
        }  # fmt: skip
        return Classified.model_validate(
            {"class": kind, "p_plan": 0.97 if plan else 0.03, "method": "fake", "sheet": sheet}
        )


def test_carbon_reader_advanced_reads_what_the_sheet_kind_step_called_advanced_and_read(
    make_service: Any, tmp_path: Path
) -> None:
    import zipfile

    from app.adapters.archive import DiskProjectStore
    from app.composition import _stored_advanced  # pyright: ignore[reportPrivateUsage]
    from app.core.ingest.triage import TriageSteps

    big = png_bytes(raster_plan().resize((4200, 2975)))  # advanced, read as a plan
    small = png_bytes(raster_plan())  # not advanced
    piping = png_bytes(raster_plan().resize((4300, 3044)))  # advanced, but set aside
    read_by: dict[str, list[str]] = {"carbon": [], "shipped": []}

    class Named:
        def __init__(self, name: str) -> None:
            self.name = name

        def extract(self, source: DrawingFile, sheet: Sheet) -> Extracted:
            from app.core.drawing.model import Scale

            read_by[self.name].append(source.path)
            return Extracted(method="detector", scale=Scale(status="no_scale"), read=("door",))

    store = DiskProjectStore(tmp_path / "projects")
    advanced = _stored_advanced(store, "p001")  # the fixture's first project id
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w") as zipped:
        for name, data in (("big.png", big), ("small.png", small), ("piping.png", piping)):
            zipped.writestr(name, data)
    kinds = SheetKinds({big: ("floor_plan", True), small: ("floor_plan", False),
                        piping: ("other_drawing", True)})  # fmt: skip
    ingest = make_service(
        store=store,
        raster=lambda files: CarbonSwitch(Named("shipped"), Named("carbon"), advanced),
        carbon_read=advanced,
        triage=TriageSteps(classifier=kinds, describer=None, judge=None, name="fakes"),
    )
    status = ingest.wait(ingest.start("site.zip", archive.getvalue()))
    assert status.id == "p001"
    assert read_by == {"carbon": ["big.png"], "shipped": ["small.png"]}
    files = {file.path: file for file in status.files}
    assert CARBON_FLAG in files["big.png"].reason
    assert CARBON_FLAG not in files["small.png"].reason
    assert (
        files["piping.png"].state == "set_aside" and CARBON_FLAG not in files["piping.png"].reason
    )
    assert not advanced("not-in-the-project.png")


def test_carbon_reader_advanced_builds_with_the_sheet_kind_step_and_uses_its_flag(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    settings = carbon_settings(monkeypatch, tmp_path, CARBON_READER="advanced", SHEET_KIND="carbon")
    flagged = build_pipeline(settings, tmp_path, advanced=lambda path: path == "big.png")
    assert flagged.carbon_read is not None
    assert flagged.carbon_read("big.png") and not flagged.carbon_read("small.png")
    switch = flagged.extractors["raster"]._inner  # pyright: ignore[reportAttributeAccessIssue]
    assert isinstance(switch, CarbonSwitch)
    use = switch._use_carbon  # pyright: ignore[reportPrivateUsage]
    assert use("big.png") and not use("small.png")
    unrecorded = build_pipeline(settings, tmp_path)  # the CLI: no sheet record, so none is
    assert unrecorded.carbon_read is not None and not unrecorded.carbon_read("big.png")
    names = build_ingest(settings, tmp_path / "projects", background=False)._names  # pyright: ignore[reportPrivateUsage]
    assert names["carbon_reader"] == f"advanced:{c.READER_SHA[:12]}"


# --- a Carbon count is never certified, whichever path puts Carbon on a part (fail-1, #254) ----

CHECK = (
    Path(__file__).parents[3]
    / "eval/results/check/check-C1-T1-recall96-rt-full-small-medium20.json"
)


def api_doors(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, **env: str) -> dict[str, Any]:
    """fail-1's repro (.agents/qa/r9/review-254-repro.py): the demo's check policy, Carbon on a
    fake model, one plan uploaded through the API, the door question asked."""
    from fastapi.testclient import TestClient

    from app.main import create_app

    tmp_path.mkdir(parents=True, exist_ok=True)
    monkeypatch.chdir(tmp_path)
    tile = tile_form(("door", [100, 100, 200, 130]), ("door", [300, 300, 340, 340]))
    model = FakeCarbon(page_form(), [tile, tile])
    monkeypatch.setattr("app.composition.CarbonClient", lambda *args, **kwargs: model)
    values = {"EXTRACTOR_RASTER": "composite", "GEMINI_API_KEY": KEY, "CHECK_POLICY": str(CHECK),
              "PROJECTS_DIR": str(tmp_path / "p"), **env}  # fmt: skip
    for name, value in values.items():
        monkeypatch.setenv(name, value)
    settings = Settings()
    app = TestClient(
        create_app(settings, build_ingest(settings, settings.projects_dir, background=False))
    )
    project = app.post("/api/projects", params={"name": "plan.png"},
                       content=png_bytes(raster_plan())).json()  # fmt: skip
    status = app.get(f"/api/projects/{project['id']}").json()
    drawing_id = status["drawings"][0]["drawing_id"]
    asked = app.post("/api/ask", json={"drawing_id": drawing_id, "project_id": project["id"],
                                       "question": "How many doors are there?"}).json()  # fmt: skip
    model_json = app.get(f"/api/drawings/{drawing_id}/model").json()
    return {"file": status["files"][0], "ask": asked, "model": model_json}


@pytest.mark.parametrize(
    "env",
    [
        {"CARBON_READER": "all", "RASTER_COMPONENTS": "plans=one-plan"},
        {"RASTER_COMPONENTS": "elements=carbon,plans=carbon,rooms=carbon"},
        {"RASTER_COMPONENTS": f"plans=one-plan,door={c.SOURCE}"},  # one class is enough
    ],
    ids=["carbon-reader-all", "every-part", "one-part-pinned"],
)
def test_a_carbon_count_is_flagged_and_never_certified_on_any_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, env: dict[str, str]
) -> None:
    got = api_doors(monkeypatch, tmp_path, **env)
    doors = [e for e in got["model"]["elements"] if e["class"] == "door"]
    assert doors and all(e["attrs"]["reader"] == c.SOURCE for e in doors)
    assert got["file"]["state"] == "flagged" and CARBON_FLAG in got["file"]["reason"]
    assert got["ask"]["answer"] == 2
    assert got["ask"]["check"] is not None and got["ask"]["level"]["level"] == "low"


def test_carbon_as_a_second_reader_flags_nothing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    got = api_doors(monkeypatch, tmp_path, RASTER_COMPONENTS="plans=one-plan,elements=carbon",
                    DOUBLE_CHECK_READERS="c1=carbon")  # fmt: skip
    assert CARBON_FLAG in got["file"]["reason"]  # elements=carbon is a part: flagged
    got = api_doors(monkeypatch, tmp_path / "second", RASTER_COMPONENTS="plans=one-plan",
                    DOUBLE_CHECK_READERS="c1=carbon")  # fmt: skip
    assert CARBON_FLAG not in got["file"]["reason"]  # a double-check reader counts nothing

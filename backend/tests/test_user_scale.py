"""USER_SCALE: a scale the user gives in the chat ("the scale is 1:100", "the kitchen is 12 m2",
"this room is 4.2 m wide") re-measures a drawing without a scale of its own. Synthetic drawings."""

import io
import math
from collections.abc import Callable
from typing import Any

import pytest
from PIL import Image

from app.adapters.user_scale import ScaledIngest, UserScales, take_scale
from app.core.answering.model import Answer
from app.core.drawing.model import Drawing, Page, Room, Scale
from app.core.ingest.model import SheetFile
from app.core.pipeline.raster_scale import BOX_RATIO
from app.core.pipeline.takeoff import known_quantities
from app.core.pipeline.user_scale import (
    Given,
    is_user_scale,
    parse_given,
    rooms_named,
    user_scale,
    with_user_scale,
)
from app.core.plan_edit.model import Selection
from app.core.review.ask import Asked, user_scaled
from app.core.review.check import Level

PX = Page(page=1, width=1000, height=500, unit="px")
PT = Page(page=1, width=1000, height=500, unit="pt")
USER = "the scale you gave: the kitchen is 16 m²"


def room(id_: str, kind: str, box: tuple[float, float, float, float], **more: Any) -> Room:
    x0, y0, x1, y1 = box
    polygon = ((x0, y0), (x1, y0), (x1, y1), (x0, y1))
    return Room(id=id_, type=kind, page=1, box=box, polygon=polygon, **more)  # type: ignore[arg-type]


def drawing(page: Page = PX, status: str = "no_scale", **more: Any) -> Drawing:
    rooms = (
        room("r1", "kitchen", (0.1, 0.1, 0.3, 0.5), label="KEITTIÖ"),  # 200 x 200 px
        room("r2", "bedroom", (0.3, 0.1, 0.7, 0.5), label="MH"),  # 400 x 200 px
        room("r3", "bedroom", (0.7, 0.1, 0.9, 0.3), label="MH 2"),  # 200 x 100 px
    )
    return Drawing(file="plan.png", pages=(page,), scale=Scale(status=status), rooms=rooms, **more)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("message", "kind", "value", "room_name", "side"),
    [
        ("the scale is 1:100", "ratio", 100, None, None),
        ("It's drawn at 1 : 50 scale", "ratio", 50, None, None),
        ("the kitchen is 12 m2", "area", 12, "the kitchen", None),
        ("OK, the kitchen is about 12,5 m²; what about the bedroom?", "area", 12.5, None, None),
        ("this room is 4.2 m wide", "side", 4.2, "this room", "wide"),
        ("The living room is 6 metres long", "side", 6, "The living room", "long"),
    ],
)
def test_a_stated_scale_is_read(
    message: str, kind: str, value: float, room_name: str | None, side: str | None
) -> None:
    given = parse_given(message)
    assert given is not None and given.kind == kind and given.value == value
    if room_name is not None:
        assert given.room == room_name
    assert given.side == side


@pytest.mark.parametrize(
    "message",
    ["What is the area of the kitchen?", "How many doors are there?", "Is the kitchen 12 m2?"],
)
def test_a_question_states_no_scale(message: str) -> None:
    assert parse_given(message) is None


@pytest.mark.parametrize(
    "message",
    [
        "Is the scale 1:100?",
        "what does a scale of 1:100 mean?",
        "the scale is 1:100 or 1:50",  # two ratios: neither is taken
        "The scale is 1:100, or maybe 1:50",
        "Is it true that the kitchen is 12 m2?",
        "the scale is 1:0",  # S2: no ratio below 1
    ],
)
def test_s1_a_question_or_two_ratios_set_no_scale(message: str) -> None:
    assert parse_given(message) is None


def test_s1_a_statement_followed_by_a_question_is_read() -> None:
    given = parse_given("the kitchen is 12 m2, how big is the bedroom?")
    assert given is not None and (given.kind, given.value, given.room) == (
        "area",
        12,
        "the kitchen",
    )


def test_a_room_is_named_by_label_or_by_type() -> None:
    plan = drawing()
    assert [r.id for r in rooms_named(plan, "the kitchen")] == ["r1"]  # type: Finnish label
    assert [r.id for r in rooms_named(plan, "MH 2")] == ["r3"]  # label words
    assert [r.id for r in rooms_named(plan, "the bedroom")] == ["r2", "r3"]  # two: ambiguous
    assert rooms_named(plan, "this room") == []


def test_one_rooms_area_gives_the_others_in_proportion() -> None:
    plan = drawing()
    [kitchen] = rooms_named(plan, "kitchen")
    scale = user_scale(
        plan, Given(kind="area", value=12, room="the kitchen", text="k"), kitchen, None
    )
    assert isinstance(scale, Scale) and is_user_scale(scale) and scale.status == "estimated"
    areas = {r.id: r.area_m2 for r in with_user_scale(plan, scale).rooms}
    assert areas == {"r1": pytest.approx(12), "r2": pytest.approx(24), "r3": pytest.approx(6)}


def test_a_box_room_is_measured_as_the_area_rule_measures_it() -> None:
    boxed = drawing().model_copy(
        update={"rooms": tuple(r.model_copy(update={"polygon": None}) for r in drawing().rooms)}
    )
    kitchen = boxed.rooms[0]
    scale = user_scale(boxed, Given(kind="area", value=12, room="k", text="k"), kitchen, None)
    assert isinstance(scale, Scale) and scale.m_per_unit is not None
    assert scale.m_per_unit == pytest.approx(math.sqrt(12 * BOX_RATIO / (200 * 200)))
    assert with_user_scale(boxed, scale).rooms[0].area_m2 == pytest.approx(12)


def test_a_width_is_the_rooms_shorter_side_a_length_its_longer() -> None:
    plan = drawing()
    bedroom = plan.rooms[1]  # 400 x 200 px
    wide = user_scale(plan, Given(kind="side", value=4, side="wide", text="w"), bedroom, None)
    long = user_scale(plan, Given(kind="side", value=4, side="long", text="l"), bedroom, None)
    assert isinstance(wide, Scale) and wide.m_per_unit == pytest.approx(4 / 200)
    assert isinstance(long, Scale) and long.m_per_unit == pytest.approx(4 / 400)


def test_l3_a_ratio_needs_the_paper_size() -> None:
    ratio = Given(kind="ratio", value=100, text="1:100")
    refused = user_scale(drawing(), ratio, None, None)  # an image without a trusted DPI
    assert isinstance(refused, str) and "paper size" in refused and "m2" in refused
    on_pdf = user_scale(drawing(PT), ratio, None, 72.0)
    assert isinstance(on_pdf, Scale) and on_pdf.m_per_unit == pytest.approx(100 * 0.0254 / 72)
    at_dpi = user_scale(drawing(), ratio, None, 200.0)
    assert isinstance(at_dpi, Scale) and at_dpi.m_per_unit == pytest.approx(100 * 0.0254 / 200)


def test_a_printed_or_not_to_scale_sheet_keeps_its_own() -> None:
    ratio = Given(kind="ratio", value=100, text="1:100")
    printed = drawing(PT, "scaled").model_copy(
        update={"scale": Scale(status="scaled", m_per_unit=0.01, text="1:50")}
    )
    assert "1:50" in str(user_scale(printed, ratio, None, 72.0))
    assert "not to scale" in str(user_scale(drawing(PT, "not_to_scale"), ratio, None, 72.0))


def test_an_area_from_the_door_estimate_is_measured_again_a_printed_one_kept() -> None:
    plan = drawing(status="estimated")
    rooms = list(plan.rooms)
    rooms[1] = rooms[1].model_copy(
        update={"area_m2": 99.0, "area_status": "estimated", "area_source": "geometry_x_estimate"}
    )
    rooms[2] = rooms[2].model_copy(update={"area_m2": 7.0, "area_source": "printed"})
    plan = plan.model_copy(update={"rooms": tuple(rooms)})
    scale = Scale(status="estimated", m_per_unit=0.02, source="the scale you gave: x")
    areas = {r.id: r.area_m2 for r in with_user_scale(plan, scale).rooms}
    assert areas == {"r1": pytest.approx(16), "r2": pytest.approx(32), "r3": 7.0}


def test_the_takeoff_says_the_area_uses_the_scale_you_gave() -> None:
    plan = drawing()
    scale = user_scale(plan, Given(kind="area", value=12, room="k", text="the kitchen is 12 m²"),
                       plan.rooms[0], None)  # fmt: skip
    assert isinstance(scale, Scale)
    found = known_quantities(with_user_scale(plan, scale))
    total = next(q for key, q in found.items() if key.startswith("area:room") and q.value > 40)
    assert total.estimate is not None
    assert "using the scale you gave: the kitchen is 12 m²" in total.estimate
    assert "estimated scale" not in total.estimate


class FakeIngest:
    def __init__(self, drawings: dict[str, Drawing], data: bytes = b"", kind: str = "png") -> None:
        self.drawings, self.data, self.kind = drawings, data, kind

    def drawing(self, drawing_id: str) -> Drawing:
        return self.drawings[drawing_id]

    def sheet(self, drawing_id: str) -> SheetFile:
        return SheetFile(drawing_id=drawing_id, path="plan", kind=self.kind, data=self.data)  # type: ignore[arg-type]


def png(dpi: float | None) -> bytes:
    buffer = io.BytesIO()
    image = Image.new("L", (10, 10), 255)
    image.save(buffer, "PNG", **({} if dpi is None else {"dpi": (dpi, dpi)}))
    return buffer.getvalue()


@pytest.fixture
def entries(monkeypatch: pytest.MonkeyPatch) -> None:
    import app.adapters.user_scale as module

    monkeypatch.setattr(module, "drawings_of", lambda status: status.entries)


def take(
    ingest: FakeIngest, message: str, selection: list[Selection] | None = None
) -> tuple[str, dict[str, Scale]]:
    status: Any = type(
        "S", (), {"entries": [type("E", (), {"drawing_id": d})() for d in ingest.drawings]}
    )()
    kept: dict[str, Scale] = {}
    said = take_scale(message, selection or [], ingest, status, {"d1": "Scan 1"}, kept.__setitem__)
    return said, kept


def test_take_scale_finds_the_drawing_by_the_room_and_keeps_it(entries: None) -> None:
    printed = drawing(PT).model_copy(update={"scale": Scale(status="scaled", m_per_unit=0.01)})
    ingest = FakeIngest({"d1": drawing(), "d2": printed})
    said, kept = take(ingest, "the kitchen is 12 m2")
    assert list(kept) == ["d1"] and "Scan 1" in said and "measured using the scale" in said
    scaled = ScaledIngest(ingest, kept).drawing("d1")
    assert scaled.rooms[0].area_m2 == pytest.approx(12)
    assert ScaledIngest(ingest, kept).drawing("d2") is printed  # no scale given: as it is


def test_take_scale_says_why_it_kept_nothing(entries: None) -> None:
    ingest = FakeIngest({"d1": drawing()}, png(None))
    said, kept = take(ingest, "the bedroom is 12 m2")
    assert kept == {} and "2 rooms fit" in said
    said, kept = take(ingest, "the scale is 1:100")  # L3: a PNG without a DPI
    assert kept == {} and "paper size" in said
    assert take(ingest, "how big is the kitchen?") == ("", {})


def test_s2_a_zero_ratio_is_no_scale_and_never_raises_in_the_turn(entries: None) -> None:
    ingest = FakeIngest({"d1": drawing(PT)})
    assert take(ingest, "the scale is 1:0") == ("", {})


def test_take_scale_reads_a_trusted_dpi_and_a_selected_room(entries: None) -> None:
    ingest = FakeIngest({"d1": drawing()}, png(200))
    _, kept = take(ingest, "the scale is 1:100")
    assert kept["d1"].m_per_unit == pytest.approx(100 * 0.0254 / 200, rel=1e-4)  # pHYs: per metre
    pick = Selection(id="sel_1", kind="room", drawing_id="d1", page=1, ref="r2")
    _, kept = take(FakeIngest({"d1": drawing()}), "this room is 4 m wide", [pick])
    assert kept["d1"].m_per_unit == pytest.approx(4 / 200)


def test_scales_are_kept_per_chat() -> None:
    scales = UserScales()
    scales.put("c1", "d1", Scale(status="estimated", m_per_unit=0.01, source="x"))
    assert list(scales.of("c1")) == ["d1"] and scales.of("c2") == {}


def test_l4_an_area_at_the_users_scale_is_never_sure_nor_high() -> None:
    plan = with_user_scale(drawing(), Scale(status="estimated", m_per_unit=0.02, source=USER))
    high = Level(level="high", basis="certified", text="High")
    line = Answer(id=1, answer=16.0, unit="m2", evidence=(), method="takeoff", cost_usd=0,
                  latency_s=0, sure=True)  # fmt: skip
    asked = Asked.model_construct(answer=line, refusal=None, level=high)
    shown = user_scaled(asked, plan)
    assert shown.answer.sure is False and shown.answer.estimate is True
    assert shown.level is not None and shown.level.level == "low"
    assert "the scale you gave" in shown.level.text
    count = asked.model_copy(update={"answer": line.model_copy(update={"unit": "count"})})
    assert user_scaled(count, plan) is count  # a count does not rest on the scale
    assert user_scaled(asked, drawing(PT, "scaled")) is asked  # the sheet's own scale


def test_a_scanned_pdf_takes_a_ratio_at_its_render_resolution(
    entries: None, make_pdf: Callable[..., bytes]
) -> None:
    scan = FakeIngest({"d1": drawing()}, make_pdf((720, 360)), kind="pdf")  # 10 in wide, 1000 px
    _, kept = take(scan, "the scale is 1:100")
    assert kept["d1"].m_per_unit == pytest.approx(100 * 0.0254 / 100)  # 100 px to the inch

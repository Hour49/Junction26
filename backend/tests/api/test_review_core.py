"""The review use cases on their own (app/core/review/review.py)."""

import pytest

from app.adapters.answer_prior import NoPrior
from app.adapters.question_templates import TemplateParser
from app.core.drawing.model import (
    Drawing,
    Element,
    Mark,
    MeasuredValue,
    Page,
    Room,
    RoomType,
    Scale,
    Table,
    TableRow,
)
from app.core.errors import InvalidInputError
from app.core.pipeline.model import Quantity, QuantityConflict
from app.core.pipeline.takeoff import known_quantities
from app.core.review.ask import Asked, ask, suggestions
from app.core.review.model import Edit, MethodValue, ReviewState
from app.core.review.review import (
    NotAllowedError,
    apply,
    disputes,
    label,
    mark_views,
    review_queue,
    row,
    sheet_row,
    sign,
    storey_twins,
    with_twins,
)

AT = "2026-11-14T01:00:00Z"
PAGE = Page(page=1, width=100, height=100, unit="pt")
BOX_A = (0.1, 0.1, 0.2, 0.2)
BOX_B = (0.3, 0.3, 0.4, 0.4)
DRAWING = Drawing(
    file="x.pdf",
    pages=(PAGE,),
    scale=Scale(status="no_scale"),
    rooms=(
        Room(id="r1", type="kitchen", label="Küche", page=1, box=BOX_A, area_m2=10.0),
        Room(id="r2", type="other", page=1, box=BOX_B, area_m2=None),
    ),
)


def quantity(
    key: str,
    value: float,
    unit: str,
    *boxes: tuple[float, float, float, float],
    conflict: QuantityConflict | None = None,
) -> Quantity:
    return Quantity.model_validate(
        {
            "key": key,
            "value": value,
            "unit": unit,
            "marks": [Mark(page=1, box=box) for box in boxes],
            "rule": "each-once",
            "conflict": conflict,
        }
    )


def disputed(resolved: bool) -> QuantityConflict:
    values = (
        MeasuredValue(value=2, method="parser"),
        MeasuredValue(value=3, method="ifc_model"),
    )
    rule = {"rule": "the sheet's own count", "value": 2} if resolved else None
    return QuantityConflict.model_validate({"values": values, "resolution": rule})


def test_a_count_without_marks_recounts_from_its_own_value() -> None:
    model_doors = quantity("door|model", 10, "count")  # a model's count: no marks on the sheet
    edit = Edit(quantity="door|model", action="add", page=1, box=BOX_A)
    state = apply(ReviewState(), edit, model_doors, DRAWING, AT)
    assert row(model_doors, DRAWING, state, {}).value == 11


def test_a_mark_is_named_by_the_room_it_marks() -> None:
    total = quantity("area:room", 30.0, "m2", BOX_A, BOX_B)
    first, second = mark_views(total, DRAWING, ReviewState())
    assert (first.label, first.ref, first.value) == ("Küche", "r1", 10.0)
    assert (second.label, second.value) == ("other", None)  # no printed label: the room type


def test_a_sum_with_a_room_of_unknown_area_is_not_recounted() -> None:
    total = quantity("area:room", 30.0, "m2", BOX_A, BOX_B)
    edit = Edit(quantity="area:room", action="reject", mark="m1")
    assert row(total, DRAWING, apply(ReviewState(), edit, total, DRAWING, AT), {}).value == 20.0
    edit = Edit(quantity="area:room", action="reject", mark="m2")
    state = apply(ReviewState(), edit, total, DRAWING, AT)
    assert row(total, DRAWING, state, {}).value == 30.0  # only settle can change it now


def test_marks_are_added_to_counts_only() -> None:
    total = quantity("area:room", 30.0, "m2", BOX_A)
    with pytest.raises(InvalidInputError, match="counts only"):
        edit = Edit(quantity="area:room", action="add", page=1, box=BOX_B)
        apply(ReviewState(), edit, total, DRAWING, AT)


def test_a_conflict_no_rule_decides_is_settled_before_sign_off() -> None:
    doors = quantity("door", 2, "count", BOX_A, BOX_B, conflict=disputed(resolved=False))
    shown = row(doors, DRAWING, ReviewState(), {})
    assert (shown.status, shown.needs_person) == ("conflict", True)
    assert shown.first is not None and shown.second is not None
    assert (shown.first.value, shown.second.value) == (2, 3)
    with pytest.raises(NotAllowedError, match="settle"):
        sign(ReviewState(), doors, DRAWING, "Ana", AT)
    state = apply(
        ReviewState(), Edit(quantity="door", action="settle", value=3), doors, DRAWING, AT
    )
    state = sign(state, doors, DRAWING, "Ana", AT)
    assert state.signed["door"].value == 3


def test_a_conflict_a_rule_decided_can_be_signed_off() -> None:
    doors = quantity("door", 2, "count", BOX_A, BOX_B, conflict=disputed(resolved=True))
    assert row(doors, DRAWING, ReviewState(), {}).needs_person is False
    assert sign(ReviewState(), doors, DRAWING, "Ana", AT).signed["door"].value == 2


def test_a_signed_quantity_is_locked_until_reset() -> None:
    doors = quantity("door", 2, "count", BOX_A, BOX_B)
    state = sign(ReviewState(), doors, DRAWING, "Ana", AT)
    with pytest.raises(NotAllowedError, match="signed off by Ana"):
        apply(state, Edit(quantity="door", action="settle", value=3), doors, DRAWING, AT)
    state = apply(state, Edit(quantity="door", action="reset"), doors, DRAWING, AT)
    assert state == ReviewState()


@pytest.mark.parametrize(
    ("key", "text"),
    [
        ("door", "door count"),
        ("room:sauna", "room sauna count"),
        ("area:room|indoor", "area of room (indoor)"),
        ("length:room|name=küche|storey=level 1", "length of room (name küche, storey level 1)"),
    ],
)
def test_a_key_reads_as_a_label(key: str, text: str) -> None:
    assert label(key) == text


def test_two_methods_that_agree_show_as_agree_with_both_values() -> None:
    values = (MeasuredValue(value=2, method="parser"), MeasuredValue(value=2, method="ifc_model"))
    agreed = QuantityConflict(values=values, resolution=None, status="agree")
    doors = quantity("door", 2, "count", BOX_A, BOX_B).model_copy(update={"agree": agreed})
    shown = row(doors, DRAWING, ReviewState(), {})
    assert shown.status == "agree"
    assert (shown.first, shown.second) == (
        MethodValue(method="parser", value=2),
        MethodValue(method="ifc_model", value=2),
    )
    assert shown.conflict is None


def test_a_second_reader_s_unlocated_marks_are_counted_but_never_drawn() -> None:
    plan = (0.0, 0.0, 1.0, 1.0)  # decide's count swap gives an added element the plan's box
    seen = (0.5, 0.5, 0.6, 0.6)
    drawing = DRAWING.model_copy(
        update={
            "elements": (
                Element(id="t1", class_="toilet", page=1, box=seen),
                Element(id="d1", class_="toilet", page=1, box=plan, attrs={"located": False}),
                Element(id="d2", class_="toilet", page=1, box=plan, attrs={"located": False}),
            )
        }
    )
    toilets = quantity("toilet", 3, "count", seen, plan, plan)
    shown = row(toilets, drawing, ReviewState(), {})
    assert [(mark.id, mark.n, mark.ref) for mark in shown.marks] == [("m1", 1, "t1")]
    assert (shown.value, shown.unlocated) == (3, {"toilet": 2})
    edit = Edit(quantity="toilet", action="reject", mark="m1")
    assert row(toilets, drawing, apply(ReviewState(), edit, toilets, drawing, AT), {}).value == 2


def test_suggestions_offer_a_schedule_an_area_and_the_building_model_s_totals_first() -> None:
    door_rows = tuple(TableRow(cells=(f"10{at}",), box=(0.1, 0.1 * at, 0.3, 0.1 * at + 0.05))
                      for at in range(1, 4))  # fmt: skip
    schedule = Table(id="t1", page=1, box=(0.1, 0.1, 0.3, 0.5), title="Door Schedule",
                     columns=("Door Number",), rows=door_rows)  # fmt: skip
    found = {
        "door": quantity("door", 3, "count", BOX_A),
        "window|model": quantity("window|model", 70, "count"),
        "volume:slab|model": quantity("volume:slab|model", 41.5, "m3"),
        "area:room|indoor": quantity("area:room|indoor", 52.3, "m2", BOX_A),
    }
    asked = [found.question for found in suggestions(found, TemplateParser(), 6, (schedule,))]
    assert asked == [
        "How many doors are listed in the door schedule?",
        "What is the total volume of all floor slabs in the building model?",
        "What is the net floor area of all indoor rooms in m²?",
        "How many doors are there?",
        "How many windows are there in the building model?",
    ]


def asked(text: str, drawing: Drawing) -> Asked:
    return ask(
        text,
        drawing,
        parser=TemplateParser(),
        clock=lambda: 0.0,
        prior=NoPrior(),
        state=ReviewState(),
    )


def scaled(*rooms: Room) -> Drawing:
    return Drawing(file="x.pdf", pages=(PAGE,), scale=Scale(status="scaled"), rooms=rooms)


def test_the_area_of_the_one_room_of_a_type_is_that_room_s_area() -> None:
    """R1-3-4: "the area of the kitchen" was refused as "isn't a count, area, length or volume"
    on a sheet with one kitchen whose area "room 2.01" answers."""
    kitchen = Room(
        id="r1", type="kitchen", label="Küche", page=1, box=BOX_A, area_m2=22.4,
        attrs={"number": "2.01"},
    )  # fmt: skip
    bath = Room(id="r2", type="bathroom", label="Bad", page=1, box=BOX_B, area_m2=5.0)
    drawing = scaled(kitchen, bath)
    by_number = asked("What is the net floor area of room 2.01?", drawing)
    for text in ("What is the area of the kitchen?", "What is the net floor area of the Küche?"):
        found = asked(text, drawing)
        assert found.refusal is None, found.refusal
        assert (found.answer.answer, found.answer.unit) == (22.4, "m2")
        assert found.query == by_number.query  # the same row: its conflict and review go along


def test_the_area_of_a_room_asked_by_its_printed_label_is_that_room_s_area() -> None:
    """R2-2-3: on flat-b "What is the area of the Reduit?" (the room printed "Reduit", whose type
    the parser has no word for) was refused as "isn't a count, area, length or volume"."""
    reduit = Room(
        id="r1", type="storage", label="Reduit", page=1, box=BOX_A, area_m2=2.49,
        attrs={"number": "1.02"},
    )  # fmt: skip
    bath = Room(id="r2", type="bathroom", label="Bad", page=1, box=BOX_B, area_m2=5.0)
    drawing = scaled(reduit, bath)
    by_number = asked("What is the net floor area of room 1.02?", drawing)
    for text in (
        "What is the area of the Reduit?",
        "What is the area of the storage room?",
        "How big is the Reduit?",
        "How big is room 1.02?",
    ):
        found = asked(text, drawing)
        assert found.refusal is None, (text, found.refusal)
        assert (found.answer.answer, found.answer.unit) == (2.49, "m2")
        assert found.query == by_number.query  # the same row: its conflict and review go along


def test_an_area_of_a_type_several_rooms_have_names_them_instead_of_guessing() -> None:
    rooms = [
        Room(id=f"r{at}", type="bedroom", label=f"MH {at}", page=1, box=box, area_m2=area)
        for at, box, area in ((1, BOX_A, 11.5), (2, BOX_B, 9.0))
    ]
    found = asked("What is the area of the bedroom?", scaled(*rooms))
    assert found.answer.answer is None and found.refusal is not None
    assert found.refusal.code == "not-in-drawing"
    assert "2 rooms" in found.refusal.text and "isn't one I can turn" not in found.refusal.text
    questions = [suggestion.question for suggestion in found.refusal.can_answer]
    assert questions == [
        "What is the net floor area of room 'mh 1'?",
        "What is the net floor area of room 'mh 2'?",
    ]
    for question in questions:  # each one answers
        assert asked(question, scaled(*rooms)).answer.answer in (11.5, 9.0)


def test_an_area_of_a_room_type_on_a_sheet_without_scale_says_so() -> None:
    kitchen = Room(id="r1", type="kitchen", label="K", page=1, box=BOX_A, area_m2=None)
    refusal = asked("What is the area of the kitchen?", replace_scale(kitchen)).refusal
    assert refusal is not None and refusal.code == "no-scale"


def replace_scale(*rooms: Room) -> Drawing:
    return Drawing(file="x.png", pages=(PAGE,), scale=Scale(status="no_scale"), rooms=rooms)


def test_suggestions_spell_room_kinds_in_plain_english_plurals() -> None:
    """R1-2-2: a Swiss sheet suggested "How many balconys are there?"."""
    found = {
        "room:balcony": quantity("room:balcony", 1, "count", BOX_A),
        "room:living": quantity("room:living", 1, "count", BOX_A),
        "room:kitchen": quantity("room:kitchen", 1, "count", BOX_A),
    }
    asked = [found.question for found in suggestions(found, TemplateParser(), 6)]
    assert asked == [
        "How many balconies are there?",
        "How many living rooms are there?",
        "How many kitchens are there?",
    ]


def test_a_disagreement_on_a_one_storey_sheet_is_listed_once() -> None:
    """R1-2-4: a one-storey IFC sheet listed "window count" and "window count (storey p1)" with
    the same 12 vs 18. The takeoff keeps the conflict on both rows (a question about the storey
    reads the storey's), but the review lists the disagreement once, on the sheet's row; a storey
    row whose sheet row measures something else (P2: 71 walls drawn, 70 of them on p2) stays."""
    windows, walls = disputed(True), disputed(False)
    rows = [
        row(quantity(key, value, "count", BOX_A, conflict=found), DRAWING, ReviewState(), {})
        for key, value, found in (
            ("window", 2, windows),
            ("window|storey=p1", 2, windows),
            ("wall", 5, None),
            ("wall|storey=p1", 2, walls),
        )
    ]
    assert review_queue(rows) == ["window", "wall|storey=p1"]
    assert [found.key for found in disputes(rows)] == ["window", "wall|storey=p1"]


def test_settling_or_signing_a_one_storey_sheet_s_row_decides_its_storey_twin_too() -> None:
    """K4: on a one-storey IFC sheet the review lists "window count" once (R1-2-4), but settling,
    keeping or signing it left "window count (storey p1)" disputed, so a question about the
    storey still showed the dispute. One disagreement, one decision."""
    windows, walls = disputed(False), disputed(False)
    found = {
        key: quantity(key, value, "count", BOX_A, conflict=conflict)
        for key, value, conflict in (
            ("window", 2, windows),
            ("window|storey=p1", 2, windows),
            ("wall", 5, None),
            ("wall|storey=p1", 2, walls),
        )
    }
    twins = storey_twins(found)
    assert twins == {"window|storey=p1": "window"}  # the walls differ: not twins
    state = apply(ReviewState(), Edit(quantity="window", action="settle", value=3), found["window"],
                  DRAWING, AT)  # fmt: skip
    twin = row(found["window|storey=p1"], DRAWING, with_twins(state, twins), {})
    assert (twin.value, twin.status, twin.needs_person) == (3, "edited", False)
    state = sign(state, found["window"], DRAWING, "Ana", AT)
    twin = row(found["window|storey=p1"], DRAWING, with_twins(state, twins), {})
    assert twin.status == "signed" and twin.signed is not None and twin.signed.by == "Ana"
    walls_row = row(found["wall|storey=p1"], DRAWING, with_twins(state, twins), {})
    assert walls_row.status == "conflict"
    # an edit or sign-off sent for the storey's row is made on the sheet's row
    assert sheet_row(found, "window|storey=p1").key == "window"
    assert sheet_row(found, "wall|storey=p1").key == "wall|storey=p1"


def test_the_area_of_every_room_type_is_that_room_s_area() -> None:
    """R3-qa-1-1: "What is the area of the sauna?" was refused as "isn't a count, area, length or
    volume" although the drawing has one sauna room with an area; so were the WC and the hall."""
    cases: tuple[tuple[RoomType, str, tuple[str, ...]], ...] = (
        ("sauna", "S", ("What is the area of the sauna?", "How big is the sauna room?")),
        ("wc", "WC", ("What is the area of the WC?", "How big is the toilet?")),
        ("hall", "ET", ("What is the area of the hall?", "How big is the hallway?")),
        ("outdoor", "TERASSI", ("What is the area of the terrace?",)),
    )
    for kind, printed, questions in cases:
        room = Room(id="r1", type=kind, label=printed, page=1, box=BOX_A, area_m2=5.55)
        bath = Room(id="r2", type="bathroom", label="KPH", page=1, box=BOX_B, area_m2=4.0)
        for text in questions:
            found = asked(text, scaled(room, bath))
            assert found.refusal is None, (text, found.refusal)
            assert (found.answer.answer, found.answer.unit) == (5.55, "m2"), text


def test_a_two_letter_printed_label_names_its_room_only_as_printed() -> None:
    """R3-qa-1-1: "What is the area of the MH?" was refused (printed names needed 3 letters). A
    2-letter name matches only in the drawing's own capitals, never a word ("of", "is")."""
    mh = Room(id="r1", type="bedroom", label="MH", page=1, box=BOX_A, area_m2=11.5)
    oh = Room(id="r2", type="living", label="OH", page=1, box=BOX_B, area_m2=20.0)
    found = asked("What is the area of the MH?", scaled(mh, oh))
    assert found.refusal is None and found.answer.answer == 11.5
    assert asked("What is the area of the mh?", scaled(mh, oh)).answer.answer is None
    is_room = Room(id="r3", type="other", label="IS", page=1, box=BOX_A, area_m2=3.0)
    assert asked("What is the area of the MH?", scaled(is_room, oh)).answer.answer is None


def test_a_refusal_says_the_room_was_not_recognised_not_that_areas_are_unsupported() -> None:
    """R3-qa-1-1: a supported kind of question whose room or element wasn't recognised said
    "isn't one I can turn into a count, area, length or volume"."""
    bath = Room(id="r2", type="bathroom", label="KPH", page=1, box=BOX_B, area_m2=4.0)
    for text in ("What is the area of the gazebo?", "What is the area of the doors?"):
        refusal = asked(text, scaled(bath)).refusal
        assert refusal is not None and refusal.code == "unsupported-question"
        assert "isn't one I can turn" not in refusal.text, text
    gazebo = asked("What is the area of the gazebo?", scaled(bath)).refusal
    assert gazebo is not None and "which room or element" in gazebo.text
    doors = asked("What is the area of the doors?", scaled(bath)).refusal
    assert doors is not None and "no area for doors" in doors.text


def test_the_area_of_the_one_room_of_a_type_without_a_printed_name_is_answered() -> None:
    """R3-qa-1-1 on colorful-444: the one sauna room was read from its furniture (no label, no
    number), so no room name keyed its area, and "the area of the sauna" was not-in-drawing."""
    sauna = Room(id="r16", type="sauna", page=1, box=BOX_A, area_m2=5.55)
    bath = Room(id="r2", type="bathroom", label="KPH", page=1, box=BOX_B, area_m2=4.0)
    for text in ("What is the area of the sauna?", "How big is the sauna room?"):
        found = asked(text, scaled(sauna, bath))
        assert found.refusal is None, (text, found.refusal)
        assert (found.answer.answer, found.answer.unit) == (5.55, "m2")
        assert len(found.marks) == 1


PHOTO_FLAG = "a phone photo, read without perspective correction"


def photo(*rooms: Room, elements: tuple[Element, ...] = ()) -> Drawing:
    """A phone photo of a plan: its raster reader looked for everything (`read` set)."""
    return Drawing(
        file="027.jpg",
        pages=(PAGE,),
        scale=Scale(status="no_scale"),
        rooms=rooms,
        elements=elements,
        read=("door", "window", "room"),
    )


def asked_flagged(
    text: str,
    drawing: Drawing,
    flags: tuple[str, ...],
    *,
    raster: bool = False,
    no_reader: bool = False,
) -> Asked:
    return ask(
        text,
        drawing,
        parser=TemplateParser(),
        clock=lambda: 0.0,
        prior=NoPrior(),
        state=ReviewState(),
        flags=flags,
        raster=raster,
        no_reader=no_reader,
    )


def test_a_flagged_photo_whose_reader_found_nothing_refuses_instead_of_counting_0() -> None:
    """R3-qa4-1: Commons 027.jpg, flagged at upload and read as 0 elements, 0 rooms, answered
    "door count 0 · One method". A 0 is a count only when the reader read the page."""
    for text, what in (("How many doors are there?", "elements"), ("How many rooms?", "rooms")):
        found = asked_flagged(text, photo(), (PHOTO_FLAG,))
        assert found.row is None and found.refusal is not None, text
        assert found.refusal.code == "no-reader"
        assert PHOTO_FLAG in found.refusal.text and f"no {what}" in found.refusal.text
    # Not flagged: the reader's 0 stays an answer (a clean scan with no doors has 0 doors)
    clean = asked_flagged("How many doors are there?", photo(), ())
    assert clean.refusal is None and clean.answer.answer == 0


def test_a_raster_page_with_no_rooms_read_refuses_room_questions_flagged_or_not() -> None:
    """F4-4 (qa-1's O3): an unflagged photo whose reader found 0 rooms answered "room count 0 ·
    One method". On a raster page no room read means 0 would be a guess; element counts stay
    answers (a page can have 0 saunas). A vector page with no rooms still counts 0."""
    door = Element(id="e1", class_="door", page=1, box=BOX_A)
    drawing = photo(elements=(door,))
    for text in ("How many rooms?", "How many bedrooms are there?"):
        found = asked_flagged(text, drawing, (), raster=True)
        assert found.row is None and found.refusal is not None, text
        assert found.refusal.code == "no-reader", text
        assert found.refusal.text == (
            "No rooms were read on this drawing, so 0 would be a guess, not a count."
        )
    for text, value in (("How many doors are there?", 1), ("How many windows are there?", 0)):
        found = asked_flagged(text, drawing, (), raster=True)
        assert found.refusal is None and found.answer.answer == value, text
        assert found.row is not None and found.row.status == "single"
    # F4-4b (qa-3): every room question is refused the same way, its key in the takeoff or not
    estimated = drawing.model_copy(update={"scale": Scale(status="estimated")})
    for text in (
        "What is the net floor area of all indoor rooms in m²?",
        "What is the area of the kitchen?",
        "How big is room 1.01?",
    ):
        for flags in ((), (PHOTO_FLAG,)):
            found = asked_flagged(text, estimated, flags, raster=True)
            assert found.refusal is not None and found.refusal.code == "no-reader", (text, flags)
    vector = asked_flagged("How many rooms?", drawing, (), raster=False)
    assert vector.refusal is None and vector.answer.answer == 0


def test_a_flagged_photo_s_answers_carry_the_flag_as_an_estimate() -> None:
    """R3-qa4-1 (2): any other answer on a flagged drawing says so on the card (status
    estimate, the flag in `estimate`), and a group it did read still counts 0 as read."""
    door = Element(id="e1", class_="door", page=1, box=BOX_A)
    drawing = photo(Room(id="r1", type="kitchen", page=1, box=BOX_B), elements=(door,))
    for text, value in (("How many doors are there?", 1), ("How many windows are there?", 0)):
        found = asked_flagged(text, drawing, (PHOTO_FLAG,))
        assert found.refusal is None and found.row is not None, text
        assert found.row.value == value and found.row.status == "estimate"
        assert found.row.estimate is not None and PHOTO_FLAG in found.row.estimate
        assert found.answer.estimate is True
    plain = asked_flagged("How many doors are there?", drawing, ())
    assert plain.row is not None and plain.row.status == "single" and plain.row.estimate is None


def test_a_printed_label_with_digits_names_its_room_only_as_printed() -> None:
    """R3-qa-5-2: "What is the area of the MH1?" on colorful-13019 was refused (printed names
    with digits were skipped). Letters and digits match as printed, case-sensitive, a whole
    token, one room only; a room number ("1.01") stays the room-number path."""
    mh1 = Room(id="r1", type="bedroom", label="MH1", page=1, box=BOX_A, area_m2=11.5)
    mh2 = Room(id="r2", type="bedroom", label="MH2", page=1, box=BOX_B, area_m2=9.0)
    found = asked("What is the area of the MH1?", scaled(mh1, mh2))
    assert found.refusal is None and found.answer.answer == 11.5
    assert asked("How big is MH2?", scaled(mh1, mh2)).answer.answer == 9.0
    for text in ("What is the area of the mh1?", "What is the area of the MH12?"):
        assert asked(text, scaled(mh1, mh2)).answer.answer is None, text
    twice = Room(id="r3", type="bedroom", label="MH1", page=1, box=BOX_B, area_m2=9.0)
    assert asked("What is the area of the MH1?", scaled(mh1, twice)).answer.answer is None


def test_what_the_user_reads_names_element_classes_in_words() -> None:
    """R3-qa-5-3: on colorful-444 the sauna card showed the left-out stove as "sauna_stove" and
    a quantity "sauna_stove count": a class key, not words."""
    sauna = Room(id="r1", type="sauna", label="S", page=1, box=BOX_A, area_m2=5.55)
    stove = Element.model_validate(
        {"id": "e1", "class": "sauna_stove", "page": 1, "box": BOX_B, "attrs": {}}
    )
    drawing = Drawing(
        file="x.pdf", pages=(PAGE,), scale=Scale(status="scaled"), rooms=(sauna,),
        elements=(stove,),
    )  # fmt: skip
    found = asked("How many saunas are there?", drawing)
    assert found.row is not None
    assert [mark.label for mark in found.row.marks] == ["S", "sauna stove"]
    assert label("sauna_stove") == "sauna stove count"
    assert label("shower+bathtub") == "shower and bathtub count"
    for key in known_quantities(drawing):
        assert "_" not in label(key) and "+" not in label(key), key


def test_a_room_s_name_in_the_card_title_is_as_printed() -> None:
    """R3 (F5): "What is the area of the MH1?" was titled "area of room (name mh1)"."""
    mh1 = Room(id="r1", type="bedroom", label="MH1", page=1, box=BOX_A, area_m2=11.5)
    found = asked("What is the area of the MH1?", scaled(mh1))
    assert found.row is not None and found.row.label == "area of room (name MH1)"


class Scored:
    """DECISIONS_CONFIDENCE's stand-in: every answer scores 0.99."""

    value: float | None = 0.99
    note: str = "decisions: 0.99"

    def probability(self, path: str, family: str, value: object) -> "Scored":
        return self


def test_a_flagged_page_s_answers_are_never_marked_sure() -> None:
    """O1 (orchestrator, 2026-11-14): the gate's certificate was earned on CubiCasa test scans,
    so a page ingest flagged (a phone photo, a scanned PDF) gets sure null, not true, even when
    its score clears the threshold; the score itself stays on the line."""
    door = Element(id="e1", class_="door", page=1, box=BOX_A)
    drawing = photo(Room(id="r1", type="kitchen", page=1, box=BOX_B), elements=(door,))

    def sure(flags: tuple[str, ...]) -> tuple[object, float | None, bool | None]:
        found = ask(
            "How many doors are there?", drawing, parser=TemplateParser(), clock=lambda: 0.0,
            prior=NoPrior(), state=ReviewState(), confidence=Scored(),
            sure_at={"door": 0.8}, flags=flags, raster=True,
        )  # fmt: skip
        return found.answer.answer, found.answer.confidence, found.answer.sure

    assert sure((PHOTO_FLAG,)) == (1, 0.99, None)
    assert sure(("a scanned PDF, read as an image",)) == (1, 0.99, None)
    assert sure(()) == (1, 0.99, True)  # the same page unflagged: the gate's verdict


def test_every_no_reader_refusal_says_so_when_the_route_has_no_reader() -> None:
    """A route on the stand-in has no reader, so no refusal blames one that "found no elements":
    the flagged photo's, the raster page's no rooms, and the empty drawing's."""
    nothing = photo().model_copy(update={"read": ()})
    cases = (
        ("How many doors are there?", nothing, (PHOTO_FLAG,)),  # flagged, nothing read
        ("How many rooms?", nothing, ()),  # a raster page with no rooms
        ("How many doors are there?", nothing, ()),  # read is empty
    )
    for text, drawing, flags in cases:
        found = asked_flagged(text, drawing, flags, raster=True, no_reader=True)
        assert found.refusal is not None and found.refusal.code == "no-reader", text
        assert found.refusal.text == (
            "Nothing was read from this sheet: there is no reader for this kind of sheet yet."
        ), (text, flags)
        again = asked_flagged(text, drawing, flags, raster=True)  # a reader that read nothing
        assert again.refusal is not None and "no reader" not in again.refusal.text


def test_a_room_s_names_are_one_disagreement_only_when_the_rows_point_at_one_room() -> None:
    """Two rooms whose readers disagree with the same numbers and that give no mark are two
    disagreements: merging them would settle one room with the other's decision."""
    both = disputed(False)

    def rooms(*boxes: tuple[float, float, float, float]) -> dict[str, Quantity]:
        return {
            f"area:room|name={name}": quantity(
                f"area:room|name={name}", 2, "m2", *boxes, conflict=both
            )
            for name in ("1.01", "kitchen")
        }

    assert storey_twins(rooms()) == {}  # no marks: not known to be one room
    assert len(disputes([row(q, DRAWING, ReviewState(), {}) for q in rooms().values()])) == 2
    assert storey_twins(rooms(BOX_A)) == {"area:room|name=kitchen": "area:room|name=1.01"}

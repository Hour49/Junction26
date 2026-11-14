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
    Plan,
    Room,
    RoomType,
    Scale,
    Table,
    TableRow,
)
from app.core.errors import InvalidInputError
from app.core.ingest.judge import CARBON_FLAG, CARBON_PART_FLAG
from app.core.pipeline.model import Quantity, QuantityConflict
from app.core.pipeline.takeoff import known_quantities
from app.core.review.ask import Asked, ask, suggestions
from app.core.review.check import CheckPolicy, Counts
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


def test_a_room_asked_by_a_type_word_or_its_printed_label_and_its_number_is_that_room() -> None:
    """Tudor's chat QA (#14), floor9178: two rooms printed "Bagno" (1.01, 1.09). "How big is
    bathroom 1.01?" said the takeoff has no area for bathrooms, and "How big is Bagno 1.01?" that
    the question names no room; "room 1.01" worked. The number picks the room whatever word goes
    with it; "Bagno" alone names two rooms and stays refused."""
    first = Room(
        id="r1", type="bathroom", label="Bagno", page=1, box=BOX_A, area_m2=7.557,
        attrs={"number": "1.01"},
    )  # fmt: skip
    second = Room(
        id="r2", type="bathroom", label="Bagno", page=1, box=BOX_B, area_m2=5.175,
        attrs={"number": "1.09"},
    )  # fmt: skip
    drawing = scaled(first, second)
    for number, area in (("1.01", 7.557), ("1.09", 5.175)):
        by_number = asked(f"How big is room {number}?", drawing)
        for text in (f"How big is bathroom {number}?", f"How big is Bagno {number}?",
                     f"What is the area of the bagno {number} in m2?"):  # fmt: skip
            found = asked(text, drawing)
            assert found.refusal is None, (text, found.refusal)
            assert (found.answer.answer, found.answer.unit) == (area, "m2")
            assert found.query == by_number.query
    alone = asked("How big is Bagno?", drawing)
    assert alone.answer.answer is None and alone.refusal is not None


def test_two_rooms_or_a_number_no_room_carries_are_refused_plainly() -> None:
    """review-313: "Bagno 1.01 and Bagno 1.09" answered 1.01 alone (S1); "Area 3.14?" and
    "level 1.5" read as a room named 3.14 / 1.5 and were refused as that room's missing area
    (S2). A number no room of the drawing carries names no room; "room 3.14" still asks for one."""
    rooms = [
        Room(id=f"r{at}", type="bathroom", label="Bagno", page=1, box=box, area_m2=area,
             attrs={"number": number})
        for at, box, area, number in ((1, BOX_A, 7.557, "1.01"), (2, BOX_B, 5.175, "1.09"))
    ]  # fmt: skip
    drawing = scaled(*rooms)
    both = asked("How big is Bagno 1.01 and Bagno 1.09?", drawing)
    assert both.answer.answer is None and both.refusal is not None
    assert both.refusal.text.startswith("This question names more than one room")
    for text in ("Area 3.14?", "How big is level 1.5?", "What is the length of 12.5?"):
        found = asked(text, drawing)
        assert found.answer.answer is None and found.refusal is not None, text
        assert found.refusal.text.startswith("I can see what this asks to measure"), text
        assert "name" not in (found.query or ""), text
    missing = asked("How big is room 3.14?", drawing)
    assert missing.refusal is not None and missing.refusal.code == "not-in-drawing"
    assert asked("How big is Bagno 1.09?", drawing).answer.answer == 5.175


def test_a_count_in_a_room_by_its_number_and_a_printed_name_two_rooms_share() -> None:
    """Tudor's chat QA (floor9178): "How many doors does Bagno 1.01 have?" counted the sheet's
    doors, and "How big is Bagno?" (two rooms printed Bagno) said only "not which room". A room
    count needs the room's outline; a printed name two rooms share lists both."""
    from app.core.drawing.model import Element

    def outline(x0: float, x1: float) -> tuple[tuple[float, float], ...]:
        return ((x0, 0.1), (x1, 0.1), (x1, 0.3), (x0, 0.3))

    first = Room(
        id="r1", type="bathroom", label="Bagno", page=1, box=(0.1, 0.1, 0.3, 0.3),
        polygon=outline(0.1, 0.3), area_m2=7.557, attrs={"number": "1.01"},
    )  # fmt: skip
    second = Room(
        id="r2", type="bathroom", label="Bagno", page=1, box=(0.5, 0.1, 0.7, 0.3),
        polygon=outline(0.5, 0.7), area_m2=5.175, attrs={"number": "1.09"},
    )  # fmt: skip
    boxed = Room(id="r3", type="bedroom", label="Stanza", page=1, box=(0.1, 0.5, 0.3, 0.7),
                 area_m2=12.0, attrs={"number": "1.02"})  # fmt: skip
    doors = tuple(
        Element.model_validate({"id": f"e{at}", "class": "door", "page": 1, "box": box})
        for at, box in enumerate(
            [(0.30, 0.18, 0.32, 0.22), (0.18, 0.08, 0.22, 0.10), (0.48, 0.18, 0.50, 0.22)]
        )
    )
    drawing = scaled(first, second, boxed).model_copy(
        update={"elements": doors, "read": ("door", "room")}
    )
    assert asked("How many doors are there?", drawing).answer.answer == 3
    for text, value in (("How many doors does Bagno 1.01 have?", 2),
                        ("How many doors are in room 1.09?", 1)):  # fmt: skip
        found = asked(text, drawing)
        assert found.refusal is None and found.answer.answer == value, (text, found.refusal)
    no_outline = asked("How many doors does Stanza 1.02 have?", drawing)
    assert no_outline.refusal is not None and "no outline" in no_outline.refusal.text
    nowhere = asked("How many doors are in room 7.77?", drawing)
    assert nowhere.refusal is not None
    assert nowhere.refusal.text == "No room on this drawing is numbered or named 7.77."
    which = asked("How big is Bagno?", drawing)
    assert which.answer.answer is None and which.refusal is not None
    assert which.refusal.text == (
        "2 rooms on this drawing are printed Bagno: Bagno 1.01 7.56 m², Bagno 1.09 5.17 m². "
        "Which one? Ask with its number."
    )
    asks = [suggestion.question for suggestion in which.refusal.can_answer]
    assert asks == [
        "What is the net floor area of room 1.01?",
        "What is the net floor area of room 1.09?",
    ]


def test_a_count_naming_a_printed_room_label_never_answers_the_sheet_silently() -> None:
    """fail-1, review-332 S1: "How many doors does Bagno have?" answered the sheet's doors while
    "the Cucina" refused. One room with the label: its count; several: which one; a label that is
    the counted thing's own word ("toilets (WC)"): the sheet's count, as before."""
    from app.core.drawing.model import Element

    def at(x0: float, x1: float) -> tuple[tuple[float, float], ...]:
        return ((x0, 0.1), (x1, 0.1), (x1, 0.3), (x0, 0.3))

    def made(n: int, kind: RoomType, label: str, x0: float, x1: float, number: str) -> Room:
        return Room(id=f"r{n}", type=kind, label=label, page=1, box=(x0, 0.1, x1, 0.3),
                    polygon=at(x0, x1), area_m2=5.0 + n, attrs={"number": number})  # fmt: skip

    rooms = (made(1, "bathroom", "Bagno", 0.1, 0.3, "1.01"),
             made(2, "kitchen", "Cucina", 0.3, 0.5, "1.03"),
             made(3, "bathroom", "Bagno", 0.6, 0.8, "1.09"),
             made(4, "wc", "WC", 0.8, 0.9, "1.11"))  # fmt: skip
    things = tuple(
        Element.model_validate({"id": f"e{n}", "class": cls, "page": 1, "box": box})
        for n, (cls, box) in enumerate(
            [
                ("door", (0.29, 0.18, 0.31, 0.22)),  # between Bagno 1.01 and Cucina
                ("door", (0.40, 0.08, 0.44, 0.10)),  # Cucina's top wall
                ("toilet", (0.82, 0.12, 0.86, 0.16)),  # in the WC
                ("toilet", (0.12, 0.12, 0.16, 0.16)),  # in Bagno 1.01
            ]
        )
    )
    drawing = scaled(*rooms).model_copy(
        update={"elements": things, "read": ("door", "toilet", "room")}
    )
    cucina = asked("How many doors does the Cucina have?", drawing)
    assert cucina.refusal is None and cucina.answer.answer == 2
    assert "counts for both rooms" in (cucina.answer.explanation or "")  # the shared door
    bagno = asked("How many doors does Bagno have?", drawing)
    assert bagno.answer.answer is None and bagno.refusal is not None
    assert bagno.refusal.text.startswith("2 rooms on this drawing are printed Bagno: Bagno 1.01")
    assert [s.question for s in bagno.refusal.can_answer] == [
        "How many doors are in room 1.01?",
        "How many doors are in room 1.09?",
    ]
    assert asked("How many toilets (WC) are there?", drawing).answer.answer == 2  # the sheet's
    # the WC label as the counted thing's own word, outside parentheses: still the sheet's
    assert asked("How many WC toilets are there?", drawing).answer.answer == 2
    assert asked("How many doors does the WC have?", drawing).answer.answer == 0  # the room's
    assert asked("How many doors are there?", drawing).answer.answer == 2
    # a name in a parenthesised hint is a gloss, not a place (golden's Finnish sinks question)
    assert (
        asked("How many toilets (Cucina and baths together) are drawn?", drawing).answer.answer == 2
    )


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


def test_a_class_carbon_counted_and_found_none_of_answers_0_flagged() -> None:
    """Brief r8 BD (#269 replay: fp10, fp12, fp13 refused 13 right zeros): on a large sheet whose
    elements are Carbon's, a class Carbon counted (in `read`) with no element is a read 0, still
    flagged. A class Carbon could not count stays refused, and so does every other flagged page
    with no elements (F4-4b)."""
    kitchen = Room(id="r1", type="kitchen", page=1, box=BOX_B)
    carbon = photo(kitchen).model_copy(update={"read": ("door", "window", "toilet", "room")})
    for flags in ((CARBON_FLAG,), (PHOTO_FLAG, CARBON_FLAG)):  # fp10 is a photo too
        for text in ("How many doors are there?", "How many toilets are there?"):
            found = asked_flagged(text, carbon, flags, raster=True)
            assert found.refusal is None and found.answer.answer == 0, (text, flags)
            assert found.row is not None and found.row.status == "estimate"
            assert found.row.estimate is not None and CARBON_FLAG in found.row.estimate
            assert found.answer.estimate is True and found.answer.sure is not True
        sinks = asked_flagged("How many sinks are there?", carbon, flags, raster=True)
        assert sinks.row is None and sinks.refusal is not None, flags  # Carbon could not count
    shipped = asked_flagged("How many doors are there?", carbon, (PHOTO_FLAG,), raster=True)
    assert shipped.refusal is not None and shipped.refusal.code == "no-reader"
    # fail-1's S-D: Carbon read a part (a composite's plans or rooms), so the elements are not
    # known to be Carbon's: no element is still unread, as F4-4b says
    part = asked_flagged("How many doors are there?", carbon, (CARBON_PART_FLAG,), raster=True)
    assert part.refusal is not None and part.refusal.code == "no-reader"


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
    agrees: bool | None = None

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
            "This sheet wasn't read, so nothing on it was counted or measured: this setup has no "
            "reader for this kind of sheet. You can still ask about the project's other drawings."
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


def floors_drawing(*storeys: str | None) -> Drawing:
    """A sheet of len(storeys) plans side by side (one per storey name, None: unnamed), each
    holding plan-number + 1 doors and, on the first and last, toilets."""
    plans = tuple(
        Plan(id=f"p{n}", page=1, box=(n / len(storeys), 0.1, (n + 1) / len(storeys), 0.4),
             storey=storey)
        for n, storey in enumerate(storeys)
    )  # fmt: skip
    things: list[Element] = []
    for n, plan in enumerate(plans):
        x = (plan.box[0] + plan.box[2]) / 2
        kinds = ["door"] * (n + 1) + (["toilet"] if n in (0, len(plans) - 1) else [])
        for at, kind in enumerate(kinds):
            things.append(
                Element.model_validate(
                    {
                        "id": f"e{n}-{at}",
                        "class": kind,
                        "page": 1,
                        "plan": plan.id,
                        "box": (x, 0.2 + at / 100, x + 0.005, 0.205 + at / 100),
                    }
                )
            )
    return Drawing(
        file="x.png", pages=(PAGE,), scale=Scale(status="no_scale"), plans=plans,
        elements=tuple(things),
    )  # fmt: skip


def test_a_floor_named_in_words_is_the_storey_the_drawing_prints_for_it() -> None:
    """fable-rooms r10 item 11: page 2 of a scanned set, titled FIRST FLOOR PLAN (its plan's
    storey, from Carbon), refused "How many doors are on the first floor?" as no count at all,
    and "on the 1st floor" answered the whole sheet's count."""
    drawing = floors_drawing("FIRST FLOOR")
    for text in ("How many doors are on the first floor?", "How many doors are on the 1st floor?"):
        found = asked(text, drawing)
        assert found.answer.answer == 1, text
        assert found.query == "door|storey=first floor"
    other = asked("How many doors are on the second floor?", drawing)
    assert other.answer.answer is None and other.refusal is not None
    assert other.refusal.text == (
        "This drawing's storeys are FIRST FLOOR; none of them is the second floor."
    )
    unnamed = asked("How many doors are on the 2nd floor?", floors_drawing(None))
    assert unnamed.answer.answer is None and unnamed.refusal is not None  # not the sheet's 1
    assert unnamed.refusal.text == (
        "This drawing doesn't say which floor it shows, so I can't tell if it is the 2nd floor."
    )
    two = asked("How many doors are on level 1?", floors_drawing("Level 1", "Intermediate level 1"))
    assert two.refusal is not None and two.refusal.text.startswith(
        "Several storeys of this drawing could be the level 1: Intermediate level 1, Level 1."
    )


def test_a_floor_on_a_sheet_of_unnamed_plans_says_what_each_plan_holds() -> None:
    """fable-rooms r10 item 10 (chat-eval's scan2, three plans on one image): "How many toilets
    are on the second floor?" was refused as no count; "... on floor 2" counted all three
    plans. Which plan is the second floor is not printed, so the answer gives each plan's count
    and asks, never the sheet's total as the floor's."""
    drawing = floors_drawing(None, None, None)
    found = asked("How many toilets are on the second floor?", drawing)
    assert found.answer.answer is None and found.refusal is not None
    assert found.refusal.code == "not-in-drawing"
    assert found.refusal.text == (
        "This drawing has 3 plans and none is labelled with its floor, so I can't tell which one "
        "is the second floor. Toilets on each: plan 1 (top left) 1, plan 2 (top) 0, "
        "plan 3 (top right) 1; 2 in all."
    )
    doors = asked("How many doors are there on floor 2?", drawing)
    assert doors.refusal is not None and doors.refusal.text.endswith(
        "Doors on each: plan 1 (top left) 1, plan 2 (top) 2, plan 3 (top right) 3; 6 in all."
    )
    assert asked("How many doors are there?", drawing).answer.answer == 6  # the sheet: unchanged


def test_a_basement_level_is_not_the_first_floor() -> None:
    """review-352 B1: "Level -1" read as floor 1, so "doors on the first floor" answered the
    basement's count."""
    drawing = floors_drawing("Level -1", "Level 0")
    first = asked("How many doors are on the first floor?", drawing)
    assert first.answer.answer is None and first.refusal is not None
    assert first.refusal.text == (
        "This drawing's storeys are Level -1, Level 0; none of them is the first floor."
    )
    assert asked("How many doors are on level -1?", drawing).answer.answer == 1
    assert asked("How many doors are on the ground floor?", drawing).answer.answer == 2


def test_a_hyphen_glued_to_a_floor_number_is_level_n_or_minus_n_and_is_refused() -> None:
    """review-352 N5: "LEVEL-1" read as level -1, but many sheets write LEVEL-1 for level 1. A
    hyphen glued between the word and the number names neither floor; a space before it makes
    it a minus ("Level -1")."""
    drawing = floors_drawing("LEVEL-1 PLAN", "LEVEL 2 PLAN")
    for text in ("How many doors are on level 1?", "How many doors are on level -1?"):
        found = asked(text, drawing)
        assert found.answer.answer is None and found.refusal is not None, text
        assert found.refusal.text.startswith(
            "This drawing's storey LEVEL-1 PLAN could be floor 1 or floor -1 (below ground), so "
            "I can't tell if it is the level"
        ), found.refusal.text
    assert asked("How many doors are on level 2?", drawing).answer.answer == 2
    plain = floors_drawing("Level 1", "Level -1")
    found = asked("How many doors are on level-1?", plain)
    assert found.answer.answer is None and found.refusal is not None
    assert found.refusal.text == (
        '"level-1" could be level 1 or level -1 (below ground), so I can\'t tell which is meant. '
        'Ask for "level 1" or "level -1".'
    )
    assert asked("How many doors are on level 1?", plain).answer.answer == 1
    assert asked("How many doors are on level -1?", plain).answer.answer == 2


def test_plans_that_share_a_floor_s_name_are_never_summed() -> None:
    """review-352 B2: three plans captioned "1st Floor Plan - Option 1/2/3" answered the first
    floor's doors as the sum of three alternative layouts."""
    found = asked("How many doors are on the first floor?", floors_drawing(*["1st Floor"] * 3))
    assert found.answer.answer is None and found.refusal is not None
    assert found.refusal.text == (
        "3 plans on this drawing are labelled 1st Floor, so I can't tell which one is meant, and "
        "I don't add them up: they may be alternatives or parts of the floor. Doors on each: "
        "plan 1 (top left) 1, plan 2 (top) 2, plan 3 (top right) 3."
    )


def test_storey_names_without_a_floor_number_are_not_said_to_be_another_floor() -> None:
    """review-352 S3: on storeys Erdgeschoss and 1. Obergeschoss the refusal said "none of them is
    the first floor", which is false (1. OG is the first floor)."""
    found = asked("How many doors are on the first floor?", floors_drawing("Erdgeschoss", "1. OG"))
    assert found.refusal is not None
    assert found.refusal.text.startswith(
        "This drawing's storeys are 1. OG, Erdgeschoss; I can't tell which of them is the first "
        "floor."
    )


def test_the_per_plan_counts_add_up_to_the_sheet_s() -> None:
    """review-352 N1: a door outside every plan is said, so the plans' counts and the total
    agree."""
    drawing = floors_drawing(None, None)
    loose = Element.model_validate({"id": "loose", "class": "door", "page": 1, "box": BOX_B})
    drawing = drawing.model_copy(update={"elements": (*drawing.elements, loose)})
    found = asked("How many doors are on the second floor?", drawing)
    assert found.refusal is not None and found.refusal.text.endswith(
        "Doors on each: plan 1 (top left) 1, plan 2 (top right) 2, 1 outside every plan; 4 in all."
    )


def test_a_room_number_printed_in_the_label_names_the_room() -> None:
    """fail-1, .agents/qa/r10/stanza-107.md: the raster room reader keeps "Stanza 1.07" as one
    label (the vector reader stores the number apart), so "What is the area of Stanza 1.07?"
    (the parser's name 1.07) was refused on the PNG while the PDF answered 19.98 m²."""

    def room(n: int, label: str, area: float, page: int = 1) -> Room:
        return Room(id=f"r{n}", type="bedroom", label=label, page=page, box=BOX_A, area_m2=area,
                    attrs={"reader": "gemini"})  # fmt: skip

    drawing = scaled(room(1, "Stanza 1.07", 19.98), room(2, "Bagno\n4.5 m²", 4.5))
    assert asked("What is the area of Stanza 1.07?", drawing).answer.answer == 19.98
    assert asked("What is the net floor area of room 1.07?", drawing).answer.answer == 19.98
    # a measure or a dimension in the label is not a room number (review-354 S1), and a sign
    # stays: a basement room -1.2 is not room 1.2
    assert asked("What is the net floor area of room 4.5?", drawing).answer.answer is None
    others = scaled(
        room(1, "Ripostiglio 3.50 x 4.20", 14.7), room(2, "Disimpegno x 1.5", 3.0),
        room(3, "Porta 0.9 \u00d7 2.1", 1.0), room(4, "Kammer 7.56 qm", 7.56),
        room(5, "Cantina -1.2", 9.0),
    )  # fmt: skip
    for number in ("3.50", "4.20", "1.5", "0.9", "2.1", "7.56", "1.2"):
        text = f"What is the net floor area of room {number}?"
        assert asked(text, others).answer.answer is None, number
    # ... and the basement room answers by its signed number, as typed (review-354 re-check)
    assert asked("What is the net floor area of room -1.2?", others).answer.answer == 9.0
    assert asked("What is the area of Cantina -1.2?", others).answer.answer == 9.0
    # a minus after a letter joins: "Zimmer-1.05" is room 1.05
    joined = scaled(room(1, "Zimmer-1.05", 12.0))
    assert asked("What is the net floor area of room 1.05?", joined).answer.answer == 12.0
    # a label printing two numbers ("-1.4 Room 0.5", a stored bimspeed plan) names the room by
    # neither, so it never takes another room's number from it (r2 is -1.4 by its IFC number)
    ifc = Room(id="r2", type="other", label="Room", page=1, box=BOX_B, area_m2=4.0,
               attrs={"number": "-1.4"})  # fmt: skip
    both = scaled(ifc, room(9, "-1.4 Room 0.5", 2.0))
    assert asked("What is the net floor area of room -1.4?", both).answer.answer == 4.0
    assert asked("What is the net floor area of room 0.5?", both).answer.answer is None
    # a number two rooms print names neither: never one room's area for both, never a sum
    two = scaled(room(1, "Stanza 1.07", 19.98), room(2, "Bagno 1.07", 5.0, page=2))
    assert asked("What is the net floor area of room 1.07?", two).answer.answer is None


def test_a_room_is_asked_by_its_label_s_words_or_whole_number() -> None:
    """fable-rooms r10 (USCG scanned PDFs): the raster room reader keeps "LOBBY\\n104" and "OPEN
    OFFICE\\n102" as one label each, so "What is the area of the lobby?" and "... of open office
    102?" were refused as "no element, room or apartment named"."""

    def room(n: int, label: str, area: float) -> Room:
        return Room(id=f"r{n}", type="other", label=label, page=1, box=BOX_A, area_m2=area,
                    attrs={"reader": "gemini"})  # fmt: skip

    drawing = scaled(
        room(1, "LOBBY\n104", 45.51), room(2, "OPEN OFFICE\n102", 17.46),
        room(3, "OPEN OFFICE\n110", 1.2), room(4, "OPEN OFFICE\n114", 1.3),
    )  # fmt: skip
    assert asked("What is the area of the lobby?", drawing).answer.answer == 45.51
    assert asked("What is the area of room 104?", drawing).answer.answer == 45.51
    # three rooms print OPEN OFFICE: the number after it says which
    assert asked("What is the area of open office 102?", drawing).answer.answer == 17.46
    which = asked("What is the area of the open office?", drawing)
    assert which.answer.answer is None and which.refusal is not None
    assert which.refusal.text.startswith(
        "3 rooms on this drawing are printed open office: OPEN OFFICE 102 17.46 m², "
    )
    # a whole number names a room only after "room": never any number in the question
    assert asked("What is the area of 102?", drawing).answer.answer != 17.46


def labelled(n: int, label: str, area: float | None = 5.0, kind: RoomType = "other") -> Room:
    return Room(id=f"r{n}", type=kind, label=label, page=1, box=BOX_A, area_m2=area,
                attrs={"reader": "gemini"})  # fmt: skip


def test_a_plain_noun_that_is_a_printed_label_points_at_the_label_count() -> None:
    """vocab-nouns P2 without P1 (line 3 failed): "How many porches are there?" with rooms printed
    Porch is not answered from the label, and the refusal doesn't say no room is printed porches;
    it names the label and the question that counts it. A label that only starts with the noun
    ("CLASSROOM 104") is not it."""
    drawing = scaled(
        labelled(1, "CLOSET"), labelled(2, "CLOSET"), labelled(3, "Closet"),
        labelled(4, "Porch", kind="outdoor"), labelled(5, "PORCH", kind="outdoor"),
        labelled(6, "GUARD ROOM"), labelled(7, "MUSIC"), labelled(8, "LIBRARY"),
        labelled(9, "CLASSROOM 104"),
    )  # fmt: skip
    for question, printed, value in (
        ("How many closets are there?", "CLOSET", 3),
        ("How many porches are there?", "Porch", 2),
        ("How many guard rooms are there?", "GUARD ROOM", 1),
        ("How many music rooms are there?", "MUSIC", 1),
        ("How many libraries are there?", "LIBRARY", 1),
        ("What is the number of porches on this floor?", "Porch", 2),
    ):
        got = asked(question, drawing)
        assert got.answer.answer is None and got.refusal is not None, question
        assert "no room on this drawing is printed" not in got.refusal.text, question
        pointed = f"How many rooms labelled '{printed}' are there?"
        assert got.refusal.text.endswith(f'ask "{pointed}"'), question
        assert asked(pointed, drawing).answer.answer == value, question
    classrooms = asked("How many classrooms are there?", drawing).refusal
    assert classrooms is not None and "no room on this drawing is printed classrooms" in (
        classrooms.text
    )


def test_a_noun_no_room_is_printed_with_is_refused_by_name() -> None:
    """vocab-nouns P2: "How many telephone booths are there?" said "not which room or element it
    is about"; it names the noun and the labels the drawing does print."""
    drawing = scaled(labelled(1, "LOBBY"), labelled(2, "VAULT"), labelled(3, "PUBLIC SPACE"))
    got = asked("How many telephone booths are there?", drawing)
    assert got.answer.answer is None and got.refusal is not None
    assert got.refusal.text.startswith("I don't count telephone booths: ")
    assert "no room on this drawing is printed telephone booths" in got.refusal.text
    assert "Rooms printed here: LOBBY, VAULT, PUBLIC SPACE." in got.refusal.text
    bare = scaled(Room(id="r1", type="other", page=1, box=BOX_A, area_m2=5.0))
    none = asked("How many fireplaces are there?", bare).refusal
    assert none is not None and "No room on this drawing has a printed name." in none.text


def test_no_and_hash_before_a_room_number_are_its_number_sign() -> None:
    """vocab-nouns P3 (jf02-q08): "Bed Room No 2" did not find the room printed "BED ROOM № 2"."""
    drawing = scaled(labelled(1, "BED ROOM № 1", 22.1), labelled(2, "BED ROOM № 2", 18.4))
    for question in (
        "What is the area of Bed Room No 2?",
        "What is the area of bed room no. 2?",
        "What is the area of Bed Room Nr 2?",
        "What is the area of Bed Room #2?",
        "What is the area of Bed Room № 2?",
        "What is the area of Bed Room 2?",
    ):
        assert asked(question, drawing).answer.answer == 18.4, question
    assert asked("What is the area of Bed Room No 3?", drawing).answer.answer is None


def test_a_named_room_with_no_area_says_the_drawing_does_not_give_it() -> None:
    """review-349 S3: "What is the area of LOBBY 104?" on a room whose box was refused said "not
    which room or element it is about"; the room is named, its area is what is missing."""
    lobby = labelled(1, "LOBBY\n104", None)
    note = "room area: r1 not measured, its box is 0.40 x 0.50 m (0.20 m²), smaller than any room"
    drawing = scaled(lobby, labelled(2, "OFFICE\n105", 12.0)).model_copy(update={"notes": (note,)})
    for question in ("What is the area of the lobby?", "What is the area of LOBBY 104?"):
        got = asked(question, drawing)
        assert got.answer.answer is None and got.refusal is not None, question
        assert got.refusal.code == "not-in-drawing", question
        assert "doesn't give the area of" in got.refusal.text, question
        assert got.refusal.text.endswith(
            "Not measured: its box is 0.40 x 0.50 m (0.20 m²), smaller than any room."
        ), question


def test_apartments_no_reader_read_are_not_counted_as_none() -> None:
    """jf06 (judge-fresh): "How many apartments are on this floor?" answered 0 on a raster sheet
    of five flats: only the Swiss vector reader reads apartments, so a sheet without any has an
    unknown count, not 0."""
    flat = Drawing(file="x.png", pages=(PAGE,), scale=Scale(status="scaled"),
                   rooms=(labelled(1, "Kök", 9.0, kind="kitchen"),))  # fmt: skip
    got = asked("How many apartments are on this floor?", flat)
    assert got.answer.answer is None and got.refusal is not None


LOW_POLICY = CheckPolicy(
    thresholds={"door": 0.8},
    counts={"high": Counts(units=10, exact=10), "medium": Counts(units=10, exact=9),
            "low": Counts(units=10, exact=5)},
)  # fmt: skip


def test_a_low_answer_with_or_without_a_partial_total_is_asked() -> None:
    """main 8354e31: `found` (the takeoff row, which carries `partial`) was replaced by the
    dispute finder's Found for every answer not High, so `found.partial` in the reply raised
    AttributeError on each of them."""
    rooms = tuple(
        Room(id=f"r{n}", type="other", label=label, page=1, box=box, area_m2=area,
             area_status="exact", area_source="geometry_x_scale",
             attrs={"number": f"10{n}", "reader": "gemini"})
        for n, label, box, area in ((1, "OFFICE", BOX_A, 10.0), (2, "HALL", BOX_B, 5.5))
    )  # fmt: skip
    drawing = Drawing(
        file="scan.png", pages=(PAGE,), scale=Scale(status="estimated", m_per_unit=0.05),
        rooms=rooms, elements=(Element(id="e1", class_="door", page=1, box=BOX_A),),
    )  # fmt: skip
    for text, partial in (("How many doors are there?", False),
                          ("What is the total area of all rooms?", True)):  # fmt: skip
        got = ask(
            text, drawing, parser=TemplateParser(), clock=lambda: 0.0, prior=NoPrior(),
            state=ReviewState(), check=LOW_POLICY, raster=True, route="raster",
        )  # fmt: skip
        assert got.answer.answer is not None and got.check is not None, text
        assert got.level is not None and got.level.level != "high", text
        assert (got.partial is not None) is partial, text

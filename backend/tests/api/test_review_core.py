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
    takeoff_twins,
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


def test_which_room_is_the_largest_builds_the_drawing_s_takeoff_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """integ r12 chat latency: each room's area question under "Which room is the largest?"
    rebuilt the same drawing's takeoff and its storey twins (159 takeoffs, 1.7 s of one chat
    tool call on the demo project). The comparison reads them from the one takeoff, and answers
    as before."""
    import app.core.review.ask as asking

    built: list[Drawing] = []

    def counted(drawing: Drawing) -> dict[str, Quantity]:
        built.append(drawing)
        return known_quantities(drawing)

    twinned: list[int] = []

    def twins(found: dict[str, Quantity]) -> dict[str, str]:
        twinned.append(len(found))
        return takeoff_twins(found)

    monkeypatch.setattr(asking, "known_quantities", counted)
    monkeypatch.setattr(asking, "takeoff_twins", twins)
    kitchen = Room(id="r1", type="kitchen", label="Küche", page=1, box=BOX_A, area_m2=22.4)
    bath = Room(id="r2", type="bathroom", label="Bad", page=1, box=BOX_B, area_m2=5.0)
    found = asked("Which room is the largest?", scaled(kitchen, bath))
    assert found.refusal is None, found.refusal
    assert found.answer.answer == "Küche"
    assert len(built) == 1
    assert len(twinned) == 1


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
    no_symbols: str | None = None,
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
        no_symbols=no_symbols,
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


# triage.sheet_flag on T3 (USACE M-101A piping plan): what asked_on adds to the page's flags
SERVICES_FLAG = (
    "the sheet may not be a floor plan: it looks like a piping, plumbing, ventilation or "
    "electrical plan"
)


def test_a_sheet_triage_is_sure_is_a_services_plan_refuses_door_and_fixture_counts() -> None:
    """R3-C3/B7 (Tudor's QA round 3): T3, a piping plan the sheet-kind step flagged, answered
    "6 toilets" (1 WC + 5 marks on filter-separator tanks) with only an estimate note. When
    triage is sure it is a services plan (`no_symbols`: triage.symbols_refused), a symbol is not a
    door or a fixture, so those counts are refused with the flag's words; rooms are still
    answered, flagged. Any other flag, the sheet flag too, keeps the count, flagged (review-596:
    refusing on every doubted kind hit 30 of 327 real plans)."""
    toilets = tuple(Element(id=f"e{at}", class_="toilet", page=1, box=BOX_A) for at in range(1, 7))
    door = Element(id="d1", class_="door", page=1, box=BOX_B)
    drawing = photo(
        Room(id="r1", type="bathroom", page=1, box=BOX_B), elements=(*toilets, door)
    ).model_copy(update={"read": ("door", "window", "toilet", "sink", "room")})
    for text in (
        "How many toilets are there?",
        "How many doors are there?",
        "How many sinks are there?",
        "How many windows are there?",
    ):
        for flags in ((SERVICES_FLAG,), (PHOTO_FLAG, SERVICES_FLAG)):
            found = asked_flagged(text, drawing, flags, raster=True, no_symbols=SERVICES_FLAG)
            assert found.row is None and found.refusal is not None, (text, flags)
            assert found.refusal.code == "not-in-drawing", (text, flags)
            assert found.refusal.text == (
                "The sheet may not be a floor plan: it looks like a piping, plumbing, "
                "ventilation or electrical plan, so its symbols are not counted as doors, "
                'windows or fixtures. If it is a floor plan, use "Read it as a floor plan" on '
                "its file."
            ), (text, flags)
    rooms = asked_flagged(
        "How many bathrooms are there?", drawing, (SERVICES_FLAG,), raster=True,
        no_symbols=SERVICES_FLAG,
    )  # fmt: skip
    assert rooms.refusal is None and rooms.answer.answer == 1
    assert rooms.row is not None and rooms.row.estimate is not None
    assert SERVICES_FLAG in rooms.row.estimate
    # The sheet flag alone (a doubted evacuation plan, a map): the count, flagged
    warned = asked_flagged("How many toilets are there?", drawing, (SERVICES_FLAG,), raster=True)
    assert warned.refusal is None and warned.answer.answer == 6
    assert warned.row is not None and warned.row.estimate is not None
    assert SERVICES_FLAG in warned.row.estimate
    # Another flag (a photo) keeps its counts, flagged; no flag (read as a plan): plain counts
    photo_only = asked_flagged("How many toilets are there?", drawing, (PHOTO_FLAG,), raster=True)
    assert photo_only.refusal is None and photo_only.answer.answer == 6
    plain = asked_flagged("How many toilets are there?", drawing, (), raster=True)
    assert plain.refusal is None and plain.answer.answer == 6


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


BOX_C = (0.5, 0.5, 0.6, 0.6)
BOX_D = (0.7, 0.7, 0.8, 0.8)


def room(at: str, kind: RoomType, label: str | None, area: float | None, **more: object) -> Room:
    box = {"r1": BOX_A, "r2": BOX_B, "r3": BOX_C}.get(at, BOX_D)
    return Room(id=at, type=kind, label=label, page=1, box=box, area_m2=area, **more)  # type: ignore[arg-type]


def test_which_room_is_the_largest_or_smallest_names_it_from_the_rooms_areas() -> None:
    """judge-fresh §10: "Which room is the largest?" was refused as "isn't one I can turn into a
    count, area, length or volume" although every room's area answers. Outdoor rooms are left
    out; the answer names the room and gives both areas it rests on."""
    drawing = scaled(
        room("r1", "kitchen", "Küche", 12.0), room("r2", "living", "Wohnen", 31.5),
        room("r3", "bathroom", "Bad", 5.25), room("r4", "balcony", "Balkon", 40.0, outdoor=True),
    )  # fmt: skip
    for text in ("Which room is the largest?", "What is the biggest room?",
                 "Which room has the largest area?"):  # fmt: skip
        found = asked(text, drawing)
        assert found.refusal is None, (text, found.refusal)
        assert (found.answer.answer, found.answer.unit) == ("Wohnen", None)
        assert found.answer.explanation is not None
        assert found.answer.explanation.replace("biggest", "largest").startswith(
            "Wohnen (31.50 m²) is the largest of the 3 rooms; next is Küche (12.00 m²)"
        )
        assert [mark.ref for mark in found.marks] == ["r2"]
    smallest = asked("Which room is the smallest?", drawing)
    assert smallest.answer.answer == "Bad", smallest.refusal
    # other questions that start the same way are not this one (review-368 M1)
    for text in (
        "Which room has the largest window?",
        "Which room has the largest number of doors?",
        "What is the largest room's area?",
    ):
        assert asked(text, drawing).answer.answer not in ("Wohnen", "Küche", "Bad"), text


def test_which_of_two_rooms_is_larger_or_smaller() -> None:
    drawing = scaled(room("r1", "kitchen", "Küche", 12.0), room("r2", "bathroom", "Bad", 5.25))
    larger = asked("Which is larger, the kitchen or the Bad?", drawing)
    assert larger.answer.answer == "Küche", larger.refusal
    assert larger.answer.explanation is not None
    assert larger.answer.explanation.startswith("Küche (12.00 m²) is larger than Bad (5.25 m²)")
    smaller = asked("Which room is smaller: the Küche or the bathroom?", drawing)
    assert smaller.answer.answer == "Bad", smaller.refusal


def test_rooms_without_a_name_of_their_own_are_ranked_by_their_label_s_or_type_s_largest() -> None:
    """jf01/jf02 (fresh set): two rooms printed "BED ROOM" and three "CLOSET" have no area
    question of their own, which refused the whole comparison. For the largest, each is asked as
    the largest room of its printed label, an unlabelled room as the largest of its type."""
    drawing = scaled(
        room("r1", "bedroom", "BED ROOM", 14.0), room("r2", "bedroom", "BED ROOM", 12.0),
        room("r3", "kitchen", "KITCHEN", 9.0), room("r4", "living", None, 23.0),
    )  # fmt: skip
    found = asked("Which room is the largest?", drawing)
    assert found.answer.answer == "the unlabelled living room", found.refusal
    assert found.answer.explanation is not None
    assert "; next is BED ROOM (14.00 m²)" in found.answer.explanation
    first = asked("Which room is the largest?", replace_rooms(drawing, r4=5.0))
    assert first.answer.answer == "BED ROOM", first.refusal
    assert [mark.ref for mark in first.marks] == ["r1"]
    # the smallest has no such row: a room that no name gives alone refuses it, plainly
    smallest = asked("Which room is the smallest?", drawing)
    assert smallest.answer.answer is None and smallest.refusal is not None
    assert (
        "(BED ROOM, BED ROOM, the unlabelled living room) have no name or number"
        in smallest.refusal.text
    )


def replace_rooms(drawing: Drawing, **areas: float) -> Drawing:
    rooms = tuple(
        r.model_copy(update={"area_m2": areas.get(r.id, r.area_m2)}) for r in drawing.rooms
    )
    return drawing.model_copy(update={"rooms": rooms})


def test_which_room_refuses_when_an_area_it_needs_is_unknown() -> None:
    no_scale = scaled(room("r1", "kitchen", "Küche", None), room("r2", "bathroom", "Bad", None))
    found = asked("Which room is the largest?", no_scale)
    assert found.answer.answer is None and found.refusal is not None
    assert found.refusal.text == (
        "I can't tell which room is the largest: 2 of its rooms (Küche, Bad) have no area measured."
    )
    one = scaled(room("r1", "kitchen", "Küche", 12.0), room("r2", "bathroom", "Bad", 5.0))
    named = asked("Which is larger, the Küche or the sauna?", one)  # no sauna on the sheet
    assert named.answer.answer is None and named.refusal is not None
    assert named.refusal.text.startswith("I can't tell which is larger: the area of sauna isn't")


def test_two_areas_within_each_other_s_estimate_band_are_not_ranked() -> None:
    def two(a: float, b: float) -> Drawing:
        return scaled(
            room("r1", "kitchen", "Küche", a, area_uncertainty=0.1),
            room("r2", "living", "Wohnen", b, area_uncertainty=0.1),
        )

    close = asked("Which room is the largest?", two(10.0, 11.5))  # 11.5 * 0.9 <= 10 * 1.1
    assert close.answer.answer is None and close.refusal is not None
    assert "within each other's estimate band, so either could be" in close.refusal.text
    apart = asked("Which room is the largest?", two(10.0, 12.5))  # 11.25 > 11
    assert apart.answer.answer == "Wohnen", apart.refusal
    # equal measured areas (no band) are a tie: refused, not the first one listed (review-368)
    tie = scaled(room("r1", "kitchen", "Küche", 10.0), room("r2", "living", "Wohnen", 10.0))
    tied = asked("Which room is the largest?", tie)
    assert tied.answer.answer is None and tied.refusal is not None
    assert "within each other's estimate band" in tied.refusal.text


def test_two_names_that_read_as_one_room_are_not_compared() -> None:
    """jf04 (fresh set): "the Assistant Superintendent's office" read as the room printed
    SUPERINTENDENT, the other side's room, and was ranked against itself."""
    drawing = scaled(room("r1", "kitchen", "Küche", 12.0), room("r2", "bathroom", "Bad", 5.0))
    found = asked("Which is larger, the kitchen or the Küche?", drawing)
    assert found.answer.answer is None and found.refusal is not None
    assert found.refusal.text == (
        "I can't tell which is larger: the kitchen and the Küche both read as Küche, so I can't "
        "find them as two rooms."
    )


def space(at: str, storey: str, name: str, long_name: str | None, area: float | None) -> dict:
    quantities = {} if area is None else {"area_m2": area}
    return {"id": at, "class": "space", "storey": storey, "name": name, "long_name": long_name,
            "quantities": quantities}  # fmt: skip


def model_file(*spaces: dict) -> Drawing:
    """A building model asked on its own (an uploaded .ifc): no page, no drawn room, its spaces."""
    return Drawing.model_validate(
        {
            "file": "duplex.ifc",
            "pages": [],
            "scale": {"status": "no_scale"},
            "model_objects": list(spaces),
        }
    )


def test_the_largest_room_of_a_model_file_is_ranked_from_its_spaces() -> None:
    """Tudor's QA batch 1 B6: on the duplex .ifc, "How many rooms are there?" said 21 (the model's
    spaces) while "What is the largest room?" said "this drawing has 0 rooms to compare": the
    comparison read only the rooms a sheet draws, and a model file draws none."""
    drawing = model_file(
        space("m1", "Level 1", "A102", "Living Room", 39.4),
        space("m2", "Level 2", "A203", "Bedroom 2", 22.04),
        space("m3", "Level 2", "B203", "Bedroom 2", 22.04),
        space("m4", "Level 1", "A104", "Bathroom", 4.1),
    )
    assert asked("How many rooms are there?", drawing).answer.answer == 4
    found = asked("What is the largest room?", drawing)
    assert found.refusal is None, found.refusal
    assert found.answer.answer == "Living Room (A102)"
    assert found.answer.explanation is not None
    assert found.answer.explanation.startswith(
        "Living Room (A102) (39.40 m²) is the largest of the 4 rooms; next is "
    )
    smallest = asked("Which room is the smallest?", drawing)
    assert smallest.answer.answer == "Bathroom (A104)", smallest.refusal
    # a space whose area the model doesn't state is named, not skipped
    unknown = model_file(
        *[space("m1", "L1", "A1", "Hall", 9.0), space("m2", "L1", "A2", "Store", None)]
    )
    refused = asked("Which room is the largest?", unknown)
    assert refused.refusal is not None
    assert "Store (A2)" in refused.refusal.text and "no area" in refused.refusal.text
    # two spaces of one stated area: either could be, both named (the duplex's two living rooms)
    tie = model_file(
        space("m1", "Level 1", "A102", "Living Room", 27.66),
        space("m2", "Level 1", "B102", "Living Room", 27.66),
        space("m3", "Level 1", "A104", "Bathroom", 3.2),
    )
    tied = asked("What is the largest room?", tie)
    assert tied.refusal is not None and "either could be" in tied.refusal.text
    assert "Living Room (A102)" in tied.refusal.text and "Living Room (B102)" in tied.refusal.text


def test_a_model_space_that_cannot_be_ranked_is_named_with_its_own_reason() -> None:
    """review-479 S1/S2: the refusal gave every space left out one reason ("no name or storey to
    ask by") though one had no area and two were only named alike on one storey."""
    mixed = model_file(
        space("m1", "L1", "A1", "Hall", 9.0),
        space("m2", "L1", "A2", "Store", None),
        {**space("m3", "L1", "A3", "Odd", 4.0), "storey": None},
    )
    why = asked("Which room is the largest?", mixed).refusal
    assert why is not None
    assert "Store (A2) has no area in the model" in why.text
    assert "Odd (A3) has no storey" in why.text
    alike = model_file(
        space("m1", "L1", "A1", "Hall", 9.0),
        space("m2", "L1", "B", "Bedroom", 11.0),
        space("m3", "L1", "B", "Bedroom", 12.0),
    )
    why = asked("Which room is the largest?", alike).refusal
    assert why is not None
    assert "Bedroom (B) and Bedroom (B) on L1 can't be told apart by name" in why.text


def test_a_model_space_of_no_area_is_left_out_of_the_ranking_and_named() -> None:
    """Orchestrator, 2026-11-15: a space whose stated area is 0.00 m² (a void, a shaft) is not the
    smallest room; it is left out and named. The room count still counts it."""
    drawing = model_file(
        space("m1", "L1", "A1", "Hall", 9.0),
        space("m2", "L1", "A2", "Void", 0.0),
        space("m3", "L1", "A3", "Bath", 4.0),
    )
    assert asked("How many rooms are there?", drawing).answer.answer == 3
    found = asked("Which room is the smallest?", drawing)
    assert found.answer.answer == "Bath (A3)", found.refusal
    assert found.answer.explanation is not None
    assert found.answer.explanation.startswith(
        "Bath (A3) (4.00 m²) is the smallest of the 2 rooms; next is Hall (A1) (9.00 m²); "
        "leaving out Void (A2), 0.00 m²"
    )
    alone = model_file(space("m1", "L1", "A1", "Hall", 9.0), space("m2", "L1", "A2", "Void", 0.0))
    assert asked("Which room is the largest?", alone).refusal is not None


def test_a_model_file_counts_its_spaces_of_a_room_type() -> None:
    """qa-a, 2026-11-15: on the vitoria .ifc alone (spaces "4IZQ-HAB1", "4IZQ-COC"...) "How many
    bedrooms?" gave no count, so "Which plan has the most bedrooms?" lost to a drawn plan's 7. A
    model file counts its spaces of each room type (`attrs["room_type"]`, set by the IFC reader)
    on the rows a sheet's rooms use, for the whole model and each storey."""

    def typed(at: str, storey: str, name: str, kind: str | None) -> dict:
        found = space(at, storey, name, None, 10.0)
        return {**found, "attrs": {"room_type": kind}} if kind else found

    drawing = model_file(
        typed("m1", "P1", "1IZQ-HAB1", "bedroom"),
        typed("m2", "P1", "1IZQ-HAB2", "bedroom"),
        typed("m3", "P2", "2IZQ-HAB1", "bedroom"),
        typed("m4", "P1", "1IZQ-COC", "kitchen"),
        typed("m5", "P1", "1RELLANO", None),
    )
    assert asked("How many bedrooms are there?", drawing).answer.answer == 3
    assert asked("How many kitchens are there?", drawing).answer.answer == 1
    assert asked("How many bedrooms are there in the building model?", drawing).answer.answer == 3
    assert asked("How many bedrooms are on 'P2'?", drawing).answer.answer == 1
    assert asked("How many rooms are there?", drawing).answer.answer == 5  # unchanged


BIM_POLICY = CheckPolicy(
    thresholds={},
    routes=frozenset({"bim"}),
    route_levels={"bim": "high"},
    route_counts={"bim": Counts(units=372, exact=372)},
    counts={"high": Counts(units=10, exact=10), "medium": Counts(units=10, exact=9),
            "low": Counts(units=10, exact=5)},
)  # fmt: skip


def test_a_room_type_count_from_a_model_s_space_names_is_never_sure() -> None:
    """review-527 M1: the bim route is certified (High) on IFC sheets, and the typed-space counts
    of a model file rode on it, though the type is a word table's guess at the space's name
    (the clinic's "FUNDUS CAMERA ROOM" is a bedroom by "camera"). They are Low, unrated, and ask;
    the room count stays as the model gives it."""
    drawing = model_file(
        {**space("m1", "L1", "A202", "Bedroom 1", 12.0), "attrs": {"room_type": "bedroom"}},
        {**space("m2", "L1", "B202", "Bedroom 1", 12.0), "attrs": {"room_type": "bedroom"}},
    )

    def on_bim(text: str) -> Asked:
        return ask(text, drawing, parser=TemplateParser(), clock=lambda: 0.0, prior=NoPrior(),
                   state=ReviewState(), check=BIM_POLICY, route="bim")  # fmt: skip

    bedrooms = on_bim("How many bedrooms are there?")
    assert bedrooms.answer.answer == 2
    assert bedrooms.answer.sure is False
    assert bedrooms.level is not None
    assert (bedrooms.level.level, bedrooms.level.basis) == ("low", "unrated")
    assert bedrooms.check is not None  # Low always asks
    rooms = on_bim("How many rooms are there?")
    assert rooms.answer.sure is True and rooms.level is not None and rooms.level.level == "high"


def test_a_model_space_listed_twice_is_one_room_of_its_type() -> None:
    """review-527: duplex-m-rooms-and-spaces lists each room twice (same number, name and storey),
    so its bedrooms came out 8 for 4. A space whose number, name and storey repeat another's is
    counted once by type, a "<name> MEP Space" copy not at all; spaces that only share a name are
    not twins."""
    twin = {"attrs": {"room_type": "bedroom"}}
    drawing = model_file(
        {**space("m1", "L2", "A202", "Bedroom 1", 12.0), **twin},
        {**space("m2", "L2", "A202", "Bedroom 1", 12.0), **twin},
        {**space("m3", "L2", "A203", "Bedroom 2", 11.0), **twin},
        {**space("m4", "L2", "B203", "Bedroom 2", 11.0), **twin},
        # duplex-mep: the room again as its services copy
        {**space("m5", "L2", "A203-M", "Bedroom 2 MEP Space", 11.0), **twin},
    )
    assert asked("How many bedrooms are there?", drawing).answer.answer == 3


def test_a_room_type_no_space_has_is_0_when_every_space_is_typed() -> None:
    """R4-C4 (Tudor): "How many bathrooms?" on a model whose spaces are all typed by their names,
    none a bathroom, was refused ("doesn't give the room bathroom count"): the takeoff wrote
    rows only for the types present. 0, Low like every typed count, and the rule says when."""
    typed = model_file(
        {**space("m1", "Level 1", "A202", "Bedroom 1", 12.0), "attrs": {"room_type": "bedroom"}},
        {**space("m2", "Level 1", "A203", "Kitchen", 8.0), "attrs": {"room_type": "kitchen"}},
        space("m3", "Level 1", "A203-M", "Kitchen MEP Space", 8.0),  # a services copy: not a room
        {**space("m4", "Level 2", "B202", "Bedroom 2", 11.0), "attrs": {"room_type": "bedroom"}},
    )
    bathrooms = ask("How many bathrooms are there?", typed, parser=TemplateParser(),
                    clock=lambda: 0.0, prior=NoPrior(), state=ReviewState(), check=BIM_POLICY,
                    route="bim")  # fmt: skip
    assert bathrooms.refusal is None and bathrooms.answer.answer == 0
    assert bathrooms.answer.sure is False
    assert bathrooms.level is not None and bathrooms.level.level == "low"
    assert bathrooms.row is not None and "no space is typed" in bathrooms.row.rule.text
    assert asked("How many bathrooms are there on Level 1?", typed).answer.answer == 0
    assert asked("How many bedrooms are there on Level 1?", typed).answer.answer == 1  # the storey
    assert asked("How many bedrooms are there?", typed).answer.answer == 2  # unchanged


def test_a_wc_is_not_0_bathrooms_nor_a_bathroom_0_wcs() -> None:
    """review-663 M1: people and the dataset ("bathrooms/toilets: 12") read a WC and a bathroom
    as one kind of room, so a fully typed model with a WC is not "0 bathrooms": refused, as
    before."""
    with_wc = model_file(
        {**space("m1", "Level 1", "A101", "WC", 2.0), "attrs": {"room_type": "wc"}},
        {**space("m2", "Level 1", "A102", "Kitchen", 8.0), "attrs": {"room_type": "kitchen"}},
    )
    for text in ("How many bathrooms are there?", "Is there a bathroom?"):
        found = asked(text, with_wc)
        assert found.answer.answer is None and found.refusal is not None, text
    assert asked("How many bedrooms are there?", with_wc).answer.answer == 0  # other types: 0
    with_bath = model_file(
        {**space("m1", "Level 1", "A101", "Bathroom", 5.0), "attrs": {"room_type": "bathroom"}},
    )
    assert asked("How many bathrooms are there?", with_bath).answer.answer == 1
    assert asked("How many bedrooms are there?", with_bath).answer.answer == 0


def test_a_room_type_count_stays_refused_when_a_space_is_not_typed() -> None:
    """R4-C4: a space whose name says no room type ("Void", "Raum 12") could be the bathroom, so
    0 would be a guess: refused as before."""
    partly = model_file(
        {**space("m1", "L1", "A202", "Bedroom 1", 12.0), "attrs": {"room_type": "bedroom"}},
        space("m2", "L1", "A204", "Raum 12", 6.0),
    )
    bathrooms = asked("How many bathrooms are there?", partly)
    assert bathrooms.answer.answer is None and bathrooms.refusal is not None


def test_which_of_two_spaces_of_a_model_file_is_larger() -> None:
    """After #479: "Which is larger, the Living Room (B102) or the Kitchen?" on the duplex .ifc
    alone was refused ("the area of ... isn't known"): the two-room form asked only the rooms a
    sheet draws. Each name is found among the model's spaces (by "<LongName> (<Name>)", its
    number or its long name) and asked through that space's takeoff row."""
    drawing = model_file(
        space("m1", "Level 1", "B102", "Living Room", 27.66),
        space("m2", "Level 1", "B103", "Kitchen", 12.95),
        space("m3", "Level 1", "A103", "Kitchen", 12.95),
        space("m4", "Level 2", "B205", "Utility", 1.4),
    )
    larger = asked("Which is larger, the Living Room (B102) or the Kitchen (B103)?", drawing)
    assert larger.refusal is None, larger.refusal
    assert larger.answer.answer == "Living Room (B102)"
    assert larger.answer.explanation is not None
    assert larger.answer.explanation.startswith(
        "Living Room (B102) (27.66 m²) is larger than Kitchen (B103) (12.95 m²)"
    )
    by_number = asked("Which room is smaller: B205 or the Living Room?", drawing)
    assert by_number.answer.answer == "Utility (B205)", by_number.refusal
    # a name two spaces share: which one, with both named
    shared = asked("Which is larger, the Living Room or the Kitchen?", drawing)
    assert shared.refusal is not None
    assert "Kitchen (A103)" in shared.refusal.text and "Kitchen (B103)" in shared.refusal.text


def test_a_model_space_of_no_area_is_not_compared_with_another() -> None:
    """review-513: "Which is smaller, the Void (A2) or the Kitchen (B103)?" on a model file said
    "Void (A2) (0.00 m²) is smaller". A space of 0.00 m² (a void, a shaft) is no room to rank
    (#479); compared by name, it is refused and named, not called the smaller room."""
    drawing = model_file(
        space("m1", "Level 1", "B103", "Kitchen", 12.95),
        space("m2", "Level 1", "A2", "Void", 0.0),
    )
    for question in (
        "Which is smaller, the Void (A2) or the Kitchen (B103)?",
        "Which is larger, the Kitchen or the Void?",
    ):
        got = asked(question, drawing)
        assert got.refusal is not None, got.answer.explanation
        assert "Void (A2)" in got.refusal.text and "0.00 m²" in got.refusal.text


def test_a_schedule_s_largest_room_is_left_to_the_schedule() -> None:
    """golden 89437 asks the finish room schedule which room is largest: not the rooms drawn."""
    drawing = scaled(room("r1", "kitchen", "Küche", 12.0), room("r2", "bathroom", "Bad", 5.0))
    for text in ("Which room in the finish room schedule has the largest area?",
                 "Which room has the largest area in the room schedule?"):  # fmt: skip
        assert asked(text, drawing).answer.answer != "Küche", text


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
    assert classrooms is not None and "no room on this drawing is printed" not in classrooms.text
    assert "CLASSROOM 104 (1)" in classrooms.text  # R3-A4: named, not denied


def test_a_noun_printed_inside_labels_is_refused_with_those_labels_not_denied() -> None:
    """R3-A4 (Tudor's QA round 3, T1 DfE special school): "How many classrooms?" said "no room on
    this drawing is printed classrooms" while listing "Secondary Classroom" among the rooms. The
    noun is still not counted from labels (vocab-nouns line 3), but the refusal names each label
    that holds it, with its count, and the question that counts it."""
    drawing = scaled(
        *(labelled(n, "Secondary Classroom") for n in range(1, 7)),
        labelled(7, "Secondary Classroom (Severe Needs)"),
        labelled(8, "Secondary Classroom (Severe Needs)"),
        labelled(9, "Group Room"), labelled(10, "Classroomette"),
    )  # fmt: skip
    got = asked("How many classrooms are there?", drawing)
    assert got.answer.answer is None and got.refusal is not None
    text = got.refusal.text
    assert "no room on this drawing is printed" not in text, text
    assert "Secondary Classroom (6)" in text and "Secondary Classroom (Severe Needs) (2)" in text
    assert "Group Room" not in text and "Classroomette" not in text, text
    pointed = "How many rooms labelled 'Secondary Classroom' are there?"
    assert f'"{pointed}"' in text, text
    assert asked(pointed, drawing).answer.answer == 6


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


def test_a_printed_name_holding_a_type_word_names_that_room_whatever_its_type() -> None:
    """R3-A5 (Tudor's QA round 3, T1): "the area of the Multi-Purpose Hall" was refused as "11
    rooms on this drawing are of the type hall" though one room is printed Multi-Purpose Hall
    (typed other by the reader). The bare type word with no such name still refuses."""
    hall = Room(id="r1", type="other", label="Multi-Purpose Hall", page=1, box=BOX_A,
                area_m2=152.4)  # fmt: skip
    corridors = [Room(id=f"r{n}", type="hall", label=name, page=1, box=BOX_B, area_m2=float(n))
                 for n, name in ((2, "Corridor"), (3, "Corridor"), (4, "Lobby"))]  # fmt: skip
    drawing = scaled(hall, *corridors)
    found = asked("What is the area of the Multi-Purpose Hall?", drawing)
    assert found.refusal is None, found.refusal
    assert found.answer.answer == 152.4
    assert asked("What is the area of the multi-purpose hall?", drawing).answer.answer == 152.4
    assert asked("What is the area of the hall?", drawing).refusal is not None


@pytest.mark.parametrize(
    "question",
    [
        "What is the area of the Multi-Purpose Hall?",
        "What is the area of the Sports Hall?",
        "What is the area of the hall?",
    ],
)
def test_a_room_printed_only_the_type_word_answers_no_longer_name(question: str) -> None:
    """review-595 MUST (qa-a): with one room printed just "Hall" (typed other) among rooms typed
    hall, "the Multi-Purpose Hall" and "the Sports Hall" found "Hall" inside them and answered
    its 100 m². A printed name of the type's own words keeps main's rule: it names a room only
    among the rooms of that type; "the hall" stays refused (decided)."""
    printed = Room(id="r1", type="other", label="Hall", page=1, box=BOX_A, area_m2=100.0)
    corridors = [Room(id=f"r{n}", type="hall", label="Corridor", page=1, box=BOX_B,
                      area_m2=float(n)) for n in (2, 3)]  # fmt: skip
    found = asked(question, scaled(printed, *corridors))
    assert found.refusal is not None and found.answer.answer != 100.0, found.answer


def test_a_printed_name_with_more_than_the_type_word_answers_among_any_type() -> None:
    """review-595: "Sports Hall" printed on a room typed other still answers "the Sports Hall"."""
    sports = Room(id="r1", type="other", label="Sports Hall", page=1, box=BOX_A, area_m2=288.0)
    corridors = [Room(id=f"r{n}", type="hall", label="Corridor", page=1, box=BOX_B,
                      area_m2=float(n)) for n in (2, 3)]  # fmt: skip
    found = asked("What is the area of the Sports Hall?", scaled(sports, *corridors))
    assert found.refusal is None and found.answer.answer == 288.0, found.refusal


@pytest.mark.parametrize("word", ["largest", "smallest"])
def test_the_largest_room_refusal_names_the_unmeasured_room_not_a_missing_name(word: str) -> None:
    """R3-G6 (Tudor's QA round 3, T1): one of the rooms printed "Group Room" had no area (its box
    refused), so none of the Group Rooms could be compared, and the refusal said they "have no
    name or number to ask their area by". It names the room with no area and why, and says the
    largest (or the smallest, as asked: review-595) of the rooms printed that way isn't known."""
    groups = [labelled(n, "Group Room", area=12.0 + n) for n in range(1, 4)]
    unmeasured = labelled(4, "Group Room", area=None)
    hall = labelled(5, "Multi-Purpose Hall", area=150.0)
    library = labelled(6, "Library", area=27.5)
    drawing = scaled(*groups, unmeasured, hall, library).model_copy(
        update={"notes": ("room area: r4 not measured, its box is 0.40 x 0.50 m (0.20 m²)",)}
    )
    found = asked(f"Which room is the {word}?", drawing)
    assert found.refusal is not None, found.answer
    text = found.refusal.text
    assert "no name or number" not in text, text
    assert "1 of its rooms (Group Room) has no area measured" in text, text
    assert "its box is 0.40 x 0.50 m" in text, text
    assert f"the {word} of the 4 rooms printed Group Room isn't known" in text, text


def test_a_type_word_two_rooms_share_names_the_one_printed_with_it() -> None:
    """judge-fresh §10 (r11): "the living room" was refused because the dining room is typed
    living too, though only one room is printed LIVING ROOM. Two rooms printed so, or none,
    still refuse; the count of living rooms is unchanged."""
    living = Room(id="r1", type="living", label="LIVING ROOM", page=1, box=BOX_A, area_m2=23.16)
    dining = Room(id="r2", type="living", label="DINING ROOM", page=1, box=BOX_B, area_m2=10.62)
    found = asked("What is the area of the living room?", scaled(living, dining))
    assert found.refusal is None, found.refusal
    assert found.answer.answer == 23.16
    assert asked("How many living rooms are there?", scaled(living, dining)).answer.answer == 2
    # a number or letter the label lacks names another room: refused, as before (review-415)
    for text in ("What is the area of the living room 1?", "What is the area of the living room B?",
                 "What is the area of the living room no. 2?"):  # fmt: skip
        assert asked(text, scaled(living, dining)).refusal is not None, text
    found = asked("What is the area of the living room in m2?", scaled(living, dining))
    assert found.answer.answer == 23.16, found.refusal
    twice = dining.model_copy(update={"label": "LIVING ROOM"})
    assert asked("What is the area of the living room?", scaled(living, twice)).refusal is not None
    unlabelled = dining.model_copy(update={"label": None})
    plain = living.model_copy(update={"label": None})
    assert asked("What is the area of the living room?", scaled(plain, unlabelled)).refusal


def test_a_room_count_read_off_a_scan_says_it_counts_only_the_rooms_found() -> None:
    """Tudor's QA round 3 R3-G3/R3-G2: on a scan the room count led with the reader's total (36
    rooms where 100+ are drawn, room numbers 1, 4, 20, 28 missing; 28 where the sheet prints 48)
    as if it were all of them. A count of rooms a reader picked off a picture is partial, as the
    area total over the same rooms already was: Low, in words that say what it counts and which
    room numbers between the ones found were not read."""
    rooms = tuple(
        Room(id=f"r{n}", type="other", label="DORM", page=1, box=BOX_A if n % 2 else BOX_B,
             attrs={"number": str(n), "reader": "gemini"})
        for n in (2, 3, 5, 6, 7, 8, 9, 10)
    )  # fmt: skip
    drawing = Drawing(
        file="scan.png", pages=(PAGE,), scale=Scale(status="estimated", m_per_unit=0.05),
        rooms=rooms, elements=(Element(id="e1", class_="door", page=1, box=BOX_A),),
    )  # fmt: skip
    got = ask(
        "How many rooms are there?", drawing, parser=TemplateParser(), clock=lambda: 0.0,
        prior=NoPrior(), state=ReviewState(), check=LOW_POLICY, raster=True, route="raster",
    )  # fmt: skip
    assert got.answer.answer == 8 and got.answer.sure is False
    assert got.partial is not None and got.level is not None and got.level.level == "low"
    said = (
        "These are the 8 rooms the reader found; rooms it missed are not counted. "
        "Room numbers it did not find between them: 1 and 4."
    )
    assert said in got.level.text
    assert got.check is not None and said in got.check.reason
    # rooms drawn on a vector sheet are all of them: no partial, as before
    drawn = drawing.model_copy(
        update={"rooms": tuple(r.model_copy(update={"attrs": {"number": r.attrs["number"]}})
                               for r in rooms)}
    )  # fmt: skip
    got = ask(
        "How many rooms are there?", drawn, parser=TemplateParser(), clock=lambda: 0.0,
        prior=NoPrior(), state=ReviewState(), check=LOW_POLICY, raster=False, route="vector",
    )  # fmt: skip
    assert got.partial is None


def _in(flat: str | None, *rooms: Room) -> list[Room]:
    return [r.model_copy(update={"apartment": flat}) for r in rooms]


def _site1677(*flats: str) -> Drawing:
    """site1677's shape: a flat whose largest room is a Zimmer of 36.53 m², and outside every
    flat a far larger common room (Raum, 153.97 m²); `flats` beyond the first add one each."""
    from app.core.drawing.model import Apartment

    rooms = [
        *_in("aA", room("r1", "bedroom", "Zimmer", 36.53), room("r2", "kitchen", "Küche", 11.34)),
        *_in(None, room("r3", "other", "Raum", 153.97)),
        *[r for at, f in enumerate(flats[1:], 4)
          for r in _in(f"a{f}", room(f"r{at}", "bedroom", "Pièce", 15.0))],
    ]  # fmt: skip
    found = scaled(*rooms)
    return found.model_copy(
        update={"apartments": tuple(Apartment(id=f"a{f}", label=f) for f in flats)}
    )


@pytest.mark.parametrize(
    "text",
    ["Which is the largest room in the flat?", "Which room is the largest in this apartment?"],
)
def test_r1_7_the_largest_room_in_the_flat_ranks_that_flat_s_rooms(text: str) -> None:
    """Big QA R1 row 7: "Which is the largest room in the flat?" was refused as no count or
    area. In the flat: the flat's rooms, not the common room outside it."""
    found = asked(text, _site1677("A"))
    assert found.refusal is None, found.refusal
    assert found.answer.answer == "Zimmer"


def test_r1_7_the_flat_on_a_sheet_of_several_flats_is_refused() -> None:
    found = asked("Which is the largest room in the flat?", _site1677("A", "B", "C"))
    assert found.refusal is not None and found.answer.answer is None
    assert "3 apartments" in (found.answer.explanation or ""), found.answer.explanation


@pytest.mark.parametrize(
    "text", ["Wie viele Fenster hat diese Wohnung?", "How many windows does this apartment have?"]
)
def test_r1_8_this_flat_is_the_scope_of_a_count_not_a_second_thing(text: str) -> None:
    """Big QA R1 row 8: "Wie viele Fenster hat diese Wohnung?" was refused as naming two kinds
    of thing (Fenster, Wohnung). "This flat" already counted the sheet; "diese Wohnung" now does
    too, on a sheet of one flat; on a sheet of several it says which ones there are."""
    windows = tuple(
        Element(id=f"w{n}", class_="window", page=1, box=(0.1 * n, 0.5, 0.1 * n + 0.05, 0.55))
        for n in range(1, 4)
    )
    one = _site1677("A").model_copy(update={"elements": windows})
    found = asked(text, one)
    assert (found.refusal, found.answer.answer) == (None, 3)
    several = _site1677("A", "B").model_copy(update={"elements": windows})
    refused = asked(text, several)
    assert refused.refusal is not None and refused.answer.answer is None
    assert "apartment" in refused.refusal.text, refused.refusal

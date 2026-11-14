"""Printed room words (app/adapters/raster/room_words.py) and the answer check that reads them
(check.room_word_doubt): think-acc's certified-wrong bathroom count on a Swiss floor PNG
(.agents/exp/certified-bathroom.md). On `site980_bldg2055_floor9178.png` the image route read all
ten room labels right and typed "Bagno 1.09" `other`, so it answered 1 bathroom (gold 2) at High.
Synthetic rooms with the labels as that reader gives them."""

from pathlib import Path

import pytest

from app.adapters.answer_prior import NoPrior
from app.adapters.question_templates import TemplateParser
from app.adapters.raster.room_words import room_word, swiss_label_rooms, swiss_name, swiss_type
from app.composition import _room_policy, build_answering, build_ingest
from app.core.drawing.model import Box, CarbonCheck, Drawing, Element, Plan, Room, Scale
from app.core.review.ask import Asked, ask
from app.core.review.check import (
    UNMEASURED_TEXT,
    CheckPolicy,
    RoomWord,
    RoomWords,
    no_room_words,
)
from app.core.review.model import ReviewState
from app.settings import Settings
from tests.test_carbon_ladder import Agreeing
from tests.test_levels import COUNTS, PAGE, PHOTO_FLAG, made


def room(at: int, kind: str, label: str | None) -> Room:
    box: Box = (0.1 * (at - 1), 0.1, 0.1 * at, 0.2)
    return Room(id=f"r{at}", type=kind, label=label, page=1, box=box)  # type: ignore[arg-type]


# site980's rooms as the image route read them (label as read, type)
SITE980 = (
    room(1, "bathroom", "Bagno\n1.01"),
    room(2, "bedroom", "Stanza\n1.02"),
    room(3, "kitchen", "Cucina\n1.03"),
    room(4, "hall", "Corridoio\n1.04"),
    room(5, "balcony", "Balcone\n1.05"),
    room(6, "other", "Bagno\n1.09"),
    room(7, "other", "Vano scala\n1.10"),
)


@pytest.mark.parametrize(
    ("label", "name"),
    [
        ("Bagno\n1.09", "Bagno"),
        ("Bain 4.03", "Bain"),  # the image reader puts the number on the name's line
        ("Whg. A\nKorridor\n3.05", "Korridor"),  # the unit's label is not the room's name
        ("Vano scala\n1.10", "Vano scala"),
        ("Küche\n9,5 m²\n2.03", "Küche"),
        ("KPH", "KPH"),
        ("1.09", None),
        (None, None),
    ],
)
def test_the_name_is_read_from_an_image_label_as_the_drawn_route_reads_it(
    label: str | None, name: str | None
) -> None:
    assert swiss_name(label) == name


@pytest.mark.parametrize(
    ("label", "kind"),
    [("Bagno\n1.09", "bathroom"), ("Pièce 4.07", "bedroom"), ("Lift\n2.38", "shaft"),
     ("Balkon\n2.01", "balcony"), ("Terrasse\n3.03", "outdoor"), ("KPH", None), ("MH", None),
     ("bagno", None), ("Bagnolet", None), ("Wohnen/Essen\n2.02", "living")],
)  # fmt: skip
def test_the_swiss_table_types_a_name_and_nothing_else(label: str, kind: str | None) -> None:
    assert swiss_type(label) == kind


def test_a_room_whose_label_is_a_swiss_name_takes_that_type_and_keeps_the_reader_s() -> None:
    retyped = swiss_label_rooms(SITE980)
    assert retyped[5] == SITE980[5].model_copy(
        update={"type": "bathroom", "attrs": {"retyped_from": "other"}}
    )
    assert retyped[6].type == "shaft" and retyped[6].attrs == {"retyped_from": "other"}
    assert retyped[:5] == SITE980[:5]  # the reader's type agrees: nothing changes
    assert sum(r.type == "bathroom" for r in retyped) == 2  # gold: 2


def test_a_finnish_or_unlabelled_room_keeps_its_reader_s_type() -> None:
    rooms = (room(1, "other", "KPH"), room(2, "bedroom", None), room(3, "wc", "Bad 3.05 x"))
    assert swiss_label_rooms(rooms) == rooms


def test_every_raster_room_policy_starts_with_the_swiss_names() -> None:
    unlabelled_bedroom = room(8, "bedroom", None)
    rooms = (*SITE980, unlabelled_bedroom)
    furniture = _room_policy("furniture")(rooms)
    assert [r.type for r in furniture][5:] == ["bathroom", "shaft", "bedroom"]
    gold = _room_policy("gold-labels")(rooms)
    assert [r.type for r in gold][5:] == ["bathroom", "shaft", "other"]


def test_the_swiss_names_are_part_of_the_ingest_reuse_key_of_the_composite(tmp_path: Path) -> None:
    from tests.ingest.test_ingest_kind_wiring import drawing_png

    def readers(**on: str) -> dict[str, str]:
        settings = Settings(_env_file=None, **on)  # pyright: ignore[reportCallIssue]
        ingest = build_ingest(settings, tmp_path / "projects", background=False)
        status = ingest.status(ingest.start("plan.png", drawing_png()))
        ingest.close()
        return status.readers

    composite = readers(extractor_raster="composite", raster_components="plans=one-plan")
    assert composite["room_words"] == "swiss:v1"
    assert "room_words" not in readers(extractor_raster="hello")


def test_what_a_label_names_for_the_check() -> None:
    assert room_word("Bagno\n1.09") == RoomWord(kind="bathroom", unmeasured=True)
    assert room_word("KPH") == RoomWord(kind="bathroom", unmeasured=False)
    assert room_word("K") == RoomWord(kind="kitchen", unmeasured=False)
    assert room_word("Makuuhuone 1") is None  # a word the gold table does not hold
    assert room_word("Bain 4.03") == RoomWord(kind="bathroom", unmeasured=True)
    # a Swiss word without a Swiss room number is any plan's (review-358: a UK school's "Lift")
    assert room_word("Lift") == RoomWord(kind="shaft", unmeasured=False)
    assert build_answering(Settings(_env_file=None)).room_words is room_word  # pyright: ignore[reportCallIssue]


# Bathrooms certified at 0.8, Medium from 0.4
POLICY = CheckPolicy(
    thresholds={"room:bathroom": 0.8, "room:kitchen": 0.8, "toilet": 0.8},
    routes=frozenset({"vector"}),
    medium={"room:bathroom": 0.4, "room:kitchen": 0.4, "toilet": 0.4},
    route_levels={"vector": "high"},
    counts=COUNTS,
)


PLANS = (Plan(id="p1", page=1, box=(0.0, 0.0, 1.0, 1.0)),)  # a read page (check.found_nothing)
TOILETS = (Element(id="e1", class_="toilet", page=1, box=(0.1, 0.1, 0.15, 0.15)),)


def words(**table: RoomWord) -> RoomWords:
    """A label table by the label's first line."""
    return lambda label: table.get(label.split("\n")[0])


SWISS = words(Bagno=RoomWord("bathroom", unmeasured=True))
FINNISH = words(KPH=RoomWord("bathroom", unmeasured=False), MH=RoomWord("bedroom", False))


def asked(
    rooms: tuple[Room, ...],
    room_words: RoomWords = no_room_words,
    *,
    text: str = "How many bathrooms are there?",
    score: float = 0.9,
    route: str = "raster",
    flags: tuple[str, ...] = (),
    carbon: CarbonCheck | None = None,
    policy: CheckPolicy | None = None,
) -> Asked:
    drawing = Drawing(
        file="plan.png", pages=(PAGE,), scale=Scale(status="no_scale"), plans=PLANS,
        elements=TOILETS, rooms=rooms, carbon_check=carbon,
    )  # fmt: skip
    return ask(
        text, drawing, parser=TemplateParser(), clock=lambda: 0.0, prior=NoPrior(),
        state=ReviewState(), confidence=Agreeing(score, None), flags=flags,
        raster=route == "raster", check=policy or POLICY, route=route, room_words=room_words,
        carbon_ladder=carbon is not None,
    )  # fmt: skip


FINNISH_ROOMS = (room(1, "bathroom", "KPH"), room(2, "other", "KPH\n4,5 m²"))


def test_a_room_labelled_the_asked_type_but_typed_otherwise_holds_the_certificate() -> None:
    """B(1): the second KPH is read as `other`; the score's own level stays (on CubiCasa val the
    two Medium answers with such a room keep Medium)."""
    assert made(asked(FINNISH_ROOMS)) == ("high", "certified")  # no table: as before
    found = asked(FINNISH_ROOMS, FINNISH)
    assert found.answer.answer == 1 and found.answer.sure is False
    assert made(found) == ("medium", "score")
    assert found.check is not None
    assert found.check.reason == (
        "Please double-check the bathroom: a room is labelled as the type asked about but read "
        "as another type."
    )
    [place] = found.check.disputed
    assert (place.mark_id, place.box) == (None, FINNISH_ROOMS[1].box)  # not counted: add it
    assert place.why == (
        'Labelled "KPH", which names a bathroom, but read as type "other", so it is not counted.'
    )
    assert made(asked(FINNISH_ROOMS, FINNISH, score=0.3)) == ("low", "score")


def test_a_label_of_another_type_or_a_counted_room_holds_nothing() -> None:
    assert made(asked((room(1, "bathroom", "KPH"),), FINNISH)) == ("high", "certified")
    other = (room(1, "bathroom", "KPH"), room(2, "other", "MH"))  # a bedroom label, not asked
    assert made(asked(other, FINNISH)) == ("high", "certified")


def test_room_counts_on_an_image_with_swiss_room_names_are_never_high() -> None:
    """B(2): the readers and the signal carry CubiCasa's conventions; no Swiss image was in the
    validation. Even an answer whose labels all agree with their types asks."""
    rooms = (room(1, "bathroom", "Bagno\n1.01"), room(2, "bathroom", "Bagno\n1.09"))
    found = asked(rooms, SWISS)
    assert found.answer.answer == 2 and found.answer.sure is False
    assert made(found) == ("low", "unrated") and found.check is not None
    assert found.check.reason == (
        'Please double-check the bathrooms: this image prints room names such as "Bagno", and '
        "counts on plans of this kind are not in our validation, so none is certified."
    )
    assert found.check.disputed == ()
    assert made(asked(rooms)) == ("high", "certified")  # without the table: as before


def test_no_element_count_on_an_image_with_swiss_room_names_is_high() -> None:
    """B(2) widened (orchestrator gen 29, 21:59): think-acc's paid read of 19 lone Swiss PNGs
    found its two High-and-wrong answers in toilet counts, certified by a local gate."""
    swiss = (room(1, "bathroom", "Bagno\n1.01"),)
    toilets = "How many toilets are there?"
    assert made(asked(swiss, text=toilets)) == ("high", "certified")  # without the table
    found = asked(swiss, SWISS, text=toilets)
    assert found.answer.answer == 1 and found.answer.sure is False
    assert made(found) == ("low", "unrated") and found.check is not None
    assert "not in our validation" in found.check.reason
    # a Finnish label is a sheet of the validation's kind: its element counts are as before
    assert made(asked(FINNISH_ROOMS, FINNISH, text=toilets)) == ("high", "certified")


@pytest.mark.parametrize("score", [0.95, 0.79, 0.4, 0.1])
@pytest.mark.parametrize("text", ["How many toilets are there?", "How many bathrooms are there?"])
def test_a_count_on_an_image_with_swiss_room_names_is_low_whatever_its_score(
    score: float, text: str
) -> None:
    """Orchestrator gen 29, 2026-11-14: a Medium there would quote "on our validation plans,
    92% ... were exact" beside "this kind of plan is not in our validation"; element Medium on
    think-acc's 19 paid Swiss sheets was 8 of 25 exact."""
    rooms = (room(1, "bathroom", "Bagno\n1.01"), room(2, "bathroom", "Bagno\n1.09"))
    found = asked(rooms, SWISS, text=text, score=score)
    assert found.level is not None and (found.level.level, found.level.basis) == ("low", "unrated")
    assert found.level.text == UNMEASURED_TEXT


def test_the_low_rule_is_for_raster_counts_only() -> None:
    """review-358 M11, M17/M18: a drawn route keeps its own level on a sheet with Swiss words, and
    an area answer on a Swiss image gets neither the Low text nor the validation reason."""
    rooms = (room(1, "bathroom", "Bagno\n1.01"),)
    medium = POLICY.model_copy(update={"routes": frozenset(), "route_levels": {"vector": "medium"}})
    assert made(asked(rooms, SWISS, route="vector", policy=medium)) == ("medium", "route")
    sized = (rooms[0].model_copy(update={"area_m2": 5.0}),)
    area = asked(sized, SWISS, text="What is the area of the bathroom?")
    assert area.answer.answer == 5.0 and area.level is not None
    assert area.level.text != UNMEASURED_TEXT
    assert area.check is not None and "not in our validation" not in area.check.reason


def test_the_doubt_is_for_the_raster_route_only() -> None:
    rooms = (room(1, "bathroom", "Bagno\n1.01"), room(2, "other", "Bagno\n1.09"))
    assert made(asked(rooms, SWISS, route="vector")) == ("high", "route")  # the drawn route
    toilets = asked(rooms, SWISS, text="How many toilets are there?", route="vector")
    assert made(toilets) == ("high", "route")
    photo = asked(rooms, SWISS, flags=(PHOTO_FLAG,))
    assert made(photo) == ("low", "page")  # a flagged page stays as it was


def test_carbon_agreeing_does_not_make_a_doubted_count_high() -> None:
    rooms = (room(1, "bathroom", "Bagno\n1.01"), room(2, "bathroom", "Bagno\n1.09"))
    carbon = CarbonCheck(read=("room",), plans=PLANS, rooms=rooms)
    assert made(asked(rooms, score=0.5, carbon=carbon)) == ("high", "carbon")  # no table
    assert made(asked(rooms, SWISS, score=0.5, carbon=carbon)) == ("low", "unrated")
    things = CarbonCheck(read=("toilet", "room"), plans=PLANS, elements=TOILETS, rooms=rooms)
    toilets = "How many toilets are there?"
    assert made(asked(rooms, score=0.5, carbon=things, text=toilets)) == ("high", "carbon")
    assert made(asked(rooms, SWISS, score=0.5, carbon=things, text=toilets)) == ("low", "unrated")
    # a label naming the asked type on a room typed otherwise keeps its Medium, not Carbon's High
    finnish = CarbonCheck(read=("room",), plans=PLANS, rooms=FINNISH_ROOMS)
    assert made(asked(FINNISH_ROOMS, score=0.5, carbon=finnish)) == ("high", "carbon")
    assert made(asked(FINNISH_ROOMS, FINNISH, score=0.5, carbon=finnish)) == ("medium", "score")

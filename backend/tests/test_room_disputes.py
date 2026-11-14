"""room_disputes: the places where room readers disagree about a room type. Synthetic rooms."""

from app.core.drawing.model import Box, Room
from app.core.pipeline.room_disputes import room_disputes

A: Box = (0.10, 0.10, 0.30, 0.30)
B: Box = (0.50, 0.10, 0.70, 0.30)
C: Box = (0.10, 0.50, 0.30, 0.70)
IN_A: Box = (0.18, 0.18, 0.22, 0.20)  # a printed label's box inside A
IN_B: Box = (0.58, 0.18, 0.62, 0.20)


def room(kind: str, box: Box = A, label: str | None = None, name: str = "r1", **attrs: str) -> Room:
    return Room(id=name, type=kind, label=label, page=1, box=box, attrs=attrs)  # type: ignore[arg-type]


def test_a_room_every_reader_confirms_is_not_disputed() -> None:
    rooms = [room("bedroom", label="MH 2\n11,5 m²")]
    assert (
        room_disputes("bedroom", rooms, second=[room("bedroom")], printed=[room("bedroom", IN_A)])
        == ()
    )


def test_a_counted_room_the_second_reader_types_differently_is_listed_with_its_id() -> None:
    rooms = [room("bathroom", label="KH", name="r7")]
    (place,) = room_disputes("bathroom", rooms, second=[room("wc")])
    assert place.mark_id == "r7"
    assert (place.page, place.box) == (1, A)
    assert place.why == "Counted as a bathroom; the segmentation reader sees a wc room here."
    assert place.readers["reader"] == "bathroom"
    assert place.readers["segmentation"] == "wc"


def test_an_open_kitchen_inside_the_living_rooms_box_is_confirmed_by_the_kitchen_there() -> None:
    living = room("living", (0.05, 0.05, 0.60, 0.60))
    kitchen = room("kitchen", (0.11, 0.11, 0.29, 0.29))
    rooms = [room("kitchen", label="K")]
    assert room_disputes("kitchen", rooms, second=[living, kitchen]) == ()
    assert room_disputes("kitchen", rooms, second=[kitchen, living]) == ()


def test_a_counted_room_where_the_second_reader_has_no_room_is_listed() -> None:
    rooms = [room("balcony", label="PARVEKE")]
    (place,) = room_disputes("balcony", rooms, second=[room("living", B)])
    assert "finds no room at this place" in place.why
    assert place.readers["segmentation"] is None


def test_a_room_no_other_reader_confirms_is_listed_only_when_another_reader_ran() -> None:
    rooms = [room("balcony", label="PARVEKE")]
    assert room_disputes("balcony", rooms) == ()
    (place,) = room_disputes("balcony", rooms, printed=[])
    assert place.why.startswith("Counted as a balcony by one reader only")
    assert room_disputes("balcony", rooms, printed=[room("balcony", IN_A)]) == ()


def test_an_unlabelled_room_is_listed_even_when_no_other_reader_ran() -> None:
    (place,) = room_disputes("balcony", [room("balcony")])
    assert place.why.endswith("no printed label was read in the room.")
    (place,) = room_disputes("balcony", [room("balcony")], printed=[])
    assert place.why.endswith("no printed label was read and no other reader confirms it.")


def test_a_label_that_is_not_a_label_of_the_type_is_listed() -> None:
    second = [room("bedroom")]
    (place,) = room_disputes("bedroom", [room("bedroom", label="TH")], second=second)
    assert (
        place.why
        == 'Counted as a bedroom, but its printed label "TH" is not a usual bedroom label.'
    )
    assert place.readers["label"] == "TH"
    for label in ("MH", "MH2", "mh 3", "MAK.H.", "SOVRUM"):
        assert room_disputes("bedroom", [room("bedroom", label=label)], second=second) == ()


def test_printed_text_of_another_type_inside_a_counted_room_is_listed() -> None:
    rooms = [room("bathroom", label="KH")]
    (place,) = room_disputes(
        "bathroom", rooms, second=[room("bathroom")], printed=[room("sauna", IN_A)]
    )
    assert place.why == "Counted as a bathroom, but the printed text read inside it names a sauna."
    assert place.readers["printed_label"] == "sauna"


def test_a_room_typed_from_its_furniture_alone_is_listed() -> None:
    (place,) = room_disputes("kitchen", [room("kitchen")], second=[room("other")], printed=[])
    assert "segmentation reader sees a other room" in place.why
    (place,) = room_disputes("kitchen", [room("kitchen")], second=[room("kitchen")])
    assert place.why.endswith("no printed label was read in the room.")


def test_a_place_two_other_readers_type_and_the_answer_does_not_count_is_listed_without_an_id() -> (
    None
):
    rooms = [room("wc", A, "WC"), room("storage", B, "KHH", name="r2")]
    (place,) = room_disputes(
        "wc",
        rooms,
        second=[room("wc", A), room("wc", B)],
        printed=[room("wc", IN_A), room("wc", IN_B)],
    )
    assert place.mark_id is None
    assert place.box == B
    assert place.why == (
        "Not counted: a printed label and the segmentation reader see a separate WC here. "
        'The answer has a storage room here (label "KHH").'
    )
    assert place.readers == {
        "reader": "storage",
        "label": "KHH",
        "segmentation": "wc",
        "printed_label": "wc",
        "typer": None,
    }


def test_one_other_reader_alone_does_not_list_an_uncounted_place() -> None:
    rooms = [room("wc", A, "WC")]
    confirmed = [room("wc", A)]
    assert (
        room_disputes("wc", rooms, second=[*confirmed, room("wc", B)], printed=[room("wc", IN_A)])
        == ()
    )
    assert (
        room_disputes("wc", rooms, second=confirmed, printed=[room("wc", IN_A), room("wc", IN_B)])
        == ()
    )


def test_the_typer_is_a_reader_of_its_own() -> None:
    rooms = [room("bedroom", A, "MH")]
    second = [room("bedroom", A), room("bedroom", B)]
    (place,) = room_disputes(
        "bedroom", rooms, second=second, typed=[room("bedroom", A), room("bedroom", B)]
    )
    assert place.mark_id is None
    assert place.why.startswith(
        "Not counted: the segmentation reader and the room-type model see a bedroom"
    )
    (place,) = room_disputes("bedroom", rooms, second=second[:1], typed=[room("other", A)])
    assert (
        place.why
        == "Counted as a bedroom; the room-type model reads it as a room without a printed label."
    )


def test_a_room_the_label_policy_retyped_is_listed_as_not_counted() -> None:
    rooms = [room("other", B, name="r4", retyped_from="bedroom")]
    (place,) = room_disputes("bedroom", rooms)
    assert place.mark_id is None
    assert place.box == B
    assert place.why.startswith("Not counted: this room looks like a bedroom")
    assert room_disputes("kitchen", rooms) == ()


def test_an_answer_that_is_not_the_rooms_read_lists_every_counted_room() -> None:
    rooms = [room("kitchen", A, "K"), room("kitchen", B, "KK", name="r2")]
    second = [room("kitchen", A), room("kitchen", B)]
    assert room_disputes("kitchen", rooms, second=second) == ()
    places = room_disputes("kitchen", rooms, answer=1, second=second)
    assert [place.mark_id for place in places] == ["r1", "r2"]
    assert places[0].why == "2 kitchen rooms were read on this page; the answer says 1."
    assert room_disputes("kitchen", rooms, answer=2, second=second) == ()


def test_the_strongest_disputes_come_first_and_the_list_is_capped() -> None:
    weak = room("bedroom", C, name="weak")  # confirmed by the second reader, but no label read
    strong = room("bedroom", A, "MH", name="strong")  # the second reader types it differently
    second = [room("bedroom", C), room("storage", A)]
    places = room_disputes("bedroom", [weak, strong], second=second)
    assert [place.mark_id for place in places] == ["strong", "weak"]
    assert [
        place.mark_id for place in room_disputes("bedroom", [weak, strong], second=second, limit=1)
    ] == ["strong"]

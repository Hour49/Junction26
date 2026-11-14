"""A room source without a sauna class (the room segmentation) gets its sauna rooms from the
sauna stoves: the `other` room that holds one. Synthetic rooms only."""

from app.core.drawing.model import Box, Polygon, Room
from app.core.pipeline.sauna_rooms import sauna_rooms

LEFT: Box = (0.0, 0.0, 0.5, 1.0)
RIGHT: Box = (0.5, 0.0, 1.0, 1.0)
IN_LEFT: Box = (0.2, 0.4, 0.3, 0.5)
IN_RIGHT: Box = (0.7, 0.4, 0.8, 0.5)


def room(kind: str, box: Box, polygon: Polygon | None = None) -> Room:
    return Room(id="x", type=kind, page=1, box=box, polygon=polygon)  # type: ignore[arg-type]


def types(rooms: tuple[Room, ...]) -> list[str]:
    return [r.type for r in rooms]


def test_the_other_room_that_holds_a_stove_is_a_sauna_and_says_what_it_was() -> None:
    steam, spare = room("other", LEFT), room("other", RIGHT)
    found = sauna_rooms([steam, spare], [IN_LEFT])
    assert found == (
        steam.model_copy(update={"type": "sauna", "attrs": {"retyped_from": "other"}}),
        spare,
    )


def test_two_stoves_in_one_room_make_one_sauna() -> None:
    found = sauna_rooms(
        [room("other", LEFT), room("other", RIGHT)], [IN_LEFT, (0.1, 0.1, 0.2, 0.2)]
    )
    assert types(found) == ["sauna", "other"]


def test_stoves_in_two_rooms_make_two_saunas() -> None:
    found = sauna_rooms([room("other", LEFT), room("other", RIGHT)], [IN_LEFT, IN_RIGHT])
    assert types(found) == ["sauna", "sauna"]


def test_a_room_of_a_known_type_is_never_retyped() -> None:
    rooms = [room("bathroom", LEFT), room("bedroom", RIGHT)]
    assert sauna_rooms(rooms, [IN_LEFT, IN_RIGHT]) == tuple(rooms)


def test_a_stove_outside_every_room_or_no_stove_changes_nothing() -> None:
    rooms = [room("other", LEFT)]
    assert sauna_rooms(rooms, [IN_RIGHT]) == tuple(rooms)
    assert sauna_rooms(rooms, []) == tuple(rooms)


def test_the_rooms_outline_decides_not_its_box() -> None:
    # An L-shaped room: its box holds the stove's centre, its outline does not.
    ell: Polygon = ((0.0, 0.0), (0.5, 0.0), (0.5, 0.2), (0.1, 0.2), (0.1, 1.0), (0.0, 1.0))
    assert types(sauna_rooms([room("other", LEFT, ell)], [IN_LEFT])) == ["other"]
    assert types(sauna_rooms([room("other", LEFT, ell)], [(0.3, 0.05, 0.4, 0.15)])) == ["sauna"]


def test_of_two_rooms_that_hold_the_stove_the_smaller_one_is_the_sauna() -> None:
    whole, closet = room("other", (0.0, 0.0, 1.0, 1.0)), room("other", (0.15, 0.35, 0.35, 0.55))
    assert types(sauna_rooms([whole, closet], [IN_LEFT])) == ["other", "sauna"]

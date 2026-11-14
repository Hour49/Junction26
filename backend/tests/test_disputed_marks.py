"""The marks a person is asked to double-check: where the other readers disagree with a count.
Synthetic boxes only."""

import pytest

from app.core.drawing.model import Box, Element
from app.core.pipeline.disputed_marks import DisputedMark, disputed_marks

A: Box = (0.10, 0.10, 0.20, 0.20)
A_NEAR: Box = (0.11, 0.10, 0.21, 0.20)  # the same thing as A, read a little to the right
B: Box = (0.50, 0.50, 0.60, 0.60)
C: Box = (0.70, 0.10, 0.80, 0.20)
D: Box = (0.30, 0.70, 0.40, 0.80)


def door(name: str, box: Box, score: float | None = 0.9, page: int = 1, **attrs: str) -> Element:
    scored = {} if score is None else {"score": score}
    return Element(id=name, class_="door", page=page, box=box, attrs={**scored, **attrs})


def doors(*boxes: Box, score: float = 0.8) -> list[Element]:
    return [door(f"r{at}", box, score) for at, box in enumerate(boxes, start=1)]


def test_a_mark_every_reader_sees_is_not_disputed() -> None:
    found = disputed_marks([door("e1", A)], {"M": doors(A_NEAR), "seg": doors(A)}, noun="door", k=1)

    assert found == ()


def test_a_counted_mark_a_reader_does_not_see_is_disputed_under_its_id() -> None:
    found = disputed_marks(
        [door("e1", A), door("e2", B)],
        {"L one view": doors(A, B), "M": doors(A), "seg": doors(A_NEAR, B)},
        noun="door",
        k=1,
    )

    assert found == (
        DisputedMark(
            mark_id="e2",
            page=1,
            box=B,
            why="Counted as a door, but 1 of the 3 other readers sees nothing here.",
            readers={
                "answer": "door, score 0.90",
                "L one view": "door, score 0.80",
                "M": "nothing",
                "seg": "door, score 0.80",
            },
        ),
    )


def test_a_place_a_reader_sees_and_the_answer_did_not_count_has_no_mark_id() -> None:
    found = disputed_marks(
        [door("e1", A)],
        {"M": doors(A), "seg": [door("s1", A, 0.8), door("s2", B, 0.72)]},
        noun="sauna stove",
        k=1,
    )

    assert found == (
        DisputedMark(
            mark_id=None,
            page=1,
            box=B,
            why="Not counted, but 1 of the 2 other readers sees a sauna stove here.",
            readers={"answer": "nothing", "M": "nothing", "seg": "sauna stove, score 0.72"},
        ),
    )


def test_readers_that_see_the_same_uncounted_place_make_one_item_at_the_surest_box() -> None:
    found = disputed_marks(
        [],
        {"M": [door("m1", A_NEAR, 0.6)], "seg": [door("s1", A, 0.95)]},
        noun="door",
        k=1,
    )

    assert [(item.mark_id, item.box) for item in found] == [(None, A)]
    assert found[0].why == "Not counted, but 2 of the 2 other readers see a door here."


def test_k_is_how_many_readers_must_disagree() -> None:
    counted = [door("e1", A), door("e2", B), door("e3", C)]
    readers = {"L one view": doors(A, B), "M": doors(A), "seg": doors(A, D)}

    def ids(k: int) -> list[tuple[str | None, Box]]:
        return [(m.mark_id, m.box) for m in disputed_marks(counted, readers, noun="door", k=k)]

    assert ids(1) == [("e3", C), ("e2", B), (None, D)]
    assert ids(2) == [("e3", C), ("e2", B)]
    assert ids(3) == [("e3", C)]


def test_two_boxes_are_one_thing_from_three_tenths_of_the_smaller_one() -> None:
    big: Box = (0.10, 0.10, 0.50, 0.50)
    inside: Box = (0.20, 0.20, 0.30, 0.30)  # all of it is in `big`
    corner: Box = (0.45, 0.45, 0.55, 0.55)  # a quarter of it is in `big`

    assert disputed_marks([door("e1", big)], {"M": doors(inside)}, noun="door", k=1) == ()
    apart = disputed_marks([door("e1", big)], {"M": doors(corner)}, noun="door", k=1)
    assert [(item.mark_id, item.box) for item in apart] == [(None, corner), ("e1", big)]


def test_the_same_box_on_another_page_is_another_place() -> None:
    found = disputed_marks(
        [door("e1", A, page=1)], {"M": [door("m1", A, 0.8, page=2)]}, noun="door", k=1
    )

    assert [(item.mark_id, item.page) for item in found] == [(None, 2), ("e1", 1)]


def test_a_reader_counts_once_at_one_place() -> None:
    """Two boxes of one reader on one counted mark: the second is a thing the answer has not."""
    found = disputed_marks(
        [door("e1", A)],
        {"M": [door("m1", A, 0.8), door("m2", A_NEAR, 0.5)]},
        noun="door",
        k=1,
    )

    assert [(item.mark_id, item.box) for item in found] == [(None, A_NEAR)]


def test_the_strongest_disputes_come_first_and_the_list_stops_at_the_limit() -> None:
    """More readers against comes first. Among equals: the counted mark the detector was least
    sure of, the uncounted place a reader was surest of."""
    counted = [door("weak", A, 0.35), door("firm", B, 0.95)]
    readers = {
        "M": [door("m1", C, 0.9), door("m2", D, 0.5)],
        "seg": [door("s1", C, 0.6)],
    }

    def ids(limit: int | None) -> list[str | None]:
        found = disputed_marks(counted, readers, noun="door", k=1, limit=limit)
        return [item.mark_id or f"at {item.box[0]}" for item in found]

    # against: weak 2, firm 2, C 2 (M and seg see it), D 1
    # how strong: weak 1 - 0.35, C 0.9, firm 1 - 0.95
    assert ids(None) == ["at 0.7", "weak", "firm", "at 0.3"]
    assert ids(2) == ["at 0.7", "weak"]
    assert len(disputed_marks(counted, readers, noun="door", k=1)) == 4  # the default is 5


def test_a_mark_the_detector_saw_in_some_of_its_views_says_so() -> None:
    found = disputed_marks(
        [door("e1", A, 0.41, views="10110000")], {"M": [], "seg": doors(A)}, noun="door", k=1
    )

    assert found[0].why == (
        "Counted as a door, but 1 of the 2 other readers sees nothing here"
        " and the detector saw it in 3 of its 8 views."
    )
    assert found[0].readers["answer"] == "door, score 0.41, 3 of 8 views"


def test_a_mark_seen_in_every_view_does_not_mention_views_in_the_reason() -> None:
    found = disputed_marks([door("e1", A, views="11111111")], {"M": []}, noun="door", k=1)

    assert found[0].why == "Counted as a door, but 1 of the 1 other reader sees nothing here."


def test_a_mark_without_a_score_is_listed_without_one() -> None:
    """A count that did not come from the detector (a swapped-in count) has marks with no score."""
    found = disputed_marks([door("e1", A, score=None)], {"M": []}, noun="door", k=1)

    assert found[0].readers == {"answer": "door", "M": "nothing"}


def test_a_reader_cannot_be_called_answer() -> None:
    with pytest.raises(ValueError, match="answer"):
        disputed_marks([door("e1", A)], {"answer": doors(A)}, noun="door", k=1)

"""Windows counted two ways and the places to double-check. Synthetic boxes on a 1,000 px page,
so a box coordinate of 0.1 is 100 px."""

from app.core.drawing.model import Box, Element, Page
from app.core.pipeline.window_panes import LONG, WindowPanes, request, window_panes

PAGE = Page(page=1, width=1000, height=1000, unit="px")
A: Box = (0.1, 0.1, 0.2, 0.11)  # three windows of one size, far apart
B: Box = (0.5, 0.3, 0.6, 0.31)
C: Box = (0.1, 0.6, 0.11, 0.7)  # this one upright
A_NEXT: Box = (0.202, 0.1, 0.3, 0.11)  # continues A after 2 px
LEFT: Box = (0.1, 0.1, 0.148, 0.11)  # the two halves of A
RIGHT: Box = (0.152, 0.1, 0.2, 0.11)
ELSEWHERE: Box = (0.7, 0.8, 0.8, 0.81)


def window(box: Box, name: str = "w", score: float = 0.9, page: int = 1) -> Element:
    return Element.model_validate(
        {"id": name, "class": "window", "page": page, "box": box, "attrs": {"score": score}}
    )


def windows(*boxes: Box, score: float = 0.9) -> list[Element]:
    return [window(box, f"w{i}", score) for i, box in enumerate(boxes, 1)]


def check(
    counted: list[Element],
    views: list[list[Element]] | None = None,
    seg: list[Element] | None = None,
    limit: int | None = 5,
) -> WindowPanes:
    """Eight views and the segmentation network that see the counted windows, unless given."""
    views = [list(counted) for _ in range(8)] if views is None else views
    return window_panes(
        counted, views, {"seg": counted if seg is None else seg}, [PAGE], limit=limit
    )


def test_windows_every_reader_sees_alone_are_clean_and_need_no_request() -> None:
    found = check(windows(A, B, C))
    assert found == WindowPanes(whole=3, panes=3, clean=True, places=())
    assert request(found) is None


def test_boxes_that_continue_each_other_are_one_whole_window_and_a_place_to_check() -> None:
    found = check(windows(A, A_NEXT, B))
    assert (found.whole, found.panes, found.clean) == (2, 3, False)
    (place,) = found.places
    assert (place.mark_id, place.marks) == ("w1", ("w1", "w2"))
    assert place.box == (0.1, 0.1, 0.3, 0.11)
    assert place.why == "These 2 boxes may be one window."
    assert place.readers["answer"] == "2 windows"


def test_an_upright_box_does_not_continue_a_flat_one_and_a_far_one_does_not_either() -> None:
    corner: Box = (0.2, 0.1, 0.21, 0.2)  # starts where A ends, at a right angle
    far: Box = (0.22, 0.1, 0.3, 0.11)  # on A's line, 20 px on
    assert check(windows(A, corner, far, B)).whole == 4


def test_a_window_one_view_splits_in_two_counts_as_two_panes() -> None:
    counted = windows(A, B, C)
    views = [list(counted) for _ in range(7)] + [[*windows(LEFT, RIGHT), *counted[1:]]]
    found = check(counted, views)
    assert (found.whole, found.panes, found.clean) == (3, 4, False)
    (place,) = found.places
    assert (place.mark_id, place.why) == ("w1", "This window may count as 2 panes.")
    assert place.readers == {
        "answer": "1 window",
        "detector views": "a window in 8 of 8 views",
        "seg": "1 window",
    }


def test_a_window_far_longer_than_the_others_is_a_place_but_adds_no_pane() -> None:
    long: Box = (0.5, 0.3, 0.75, 0.31)
    counted = windows(A, long, C)
    found = check(counted, seg=[*counted, window(ELSEWHERE, "s9")])
    assert (found.whole, found.panes, found.clean) == (3, 3, False)
    assert [(place.mark_id, place.why) for place in found.places] == [
        ("w2", LONG),
        (None, "Not counted, but 1 of 9 readers sees a window here."),
    ]


def test_a_long_window_alone_does_not_make_a_page_unclean() -> None:
    long: Box = (0.5, 0.3, 0.75, 0.31)
    assert check(windows(A, long, C)) == WindowPanes(whole=3, panes=3, clean=True, places=())


def test_a_window_every_reader_sees_but_scores_low_says_its_reading_is_weak() -> None:
    """The reason is the score, not the readers: "only 2 of 2 readers see" was false here."""
    counted = [window(A, "w1", 0.3), window(B, "w2"), window(C, "w3")]
    found = check(counted)
    assert not found.clean
    (place,) = found.places
    assert place.mark_id == "w1"
    assert place.why == "Counted as a window, but the reading of this one is weak."


def test_a_counted_window_few_readers_see_is_a_place_to_check() -> None:
    counted = windows(A, B, C)
    views = [list(counted) for _ in range(3)] + [counted[:2] for _ in range(5)]
    found = check(counted, views, seg=counted[:2])
    assert not found.clean
    (place,) = found.places
    assert place.mark_id == "w3"
    assert place.why == "Counted as a window, but only 3 of 9 readers see a window here."
    assert place.readers == {
        "answer": "1 window",
        "detector views": "a window in 3 of 8 views",
        "seg": "nothing",
    }


def test_a_low_score_alone_makes_a_place_only_at_the_looser_settings() -> None:
    counted = [*windows(A, B), window(C, "w3", score=0.75)]
    found = check(counted)
    assert not found.clean
    assert [place.mark_id for place in found.places] == ["w3"]


def test_a_place_the_segmentation_sees_that_was_not_counted_has_no_mark() -> None:
    counted = windows(A, B, C)
    found = check(counted, seg=[*counted, window(ELSEWHERE, "s9")])
    assert not found.clean
    (place,) = found.places
    assert (place.mark_id, place.marks, place.box) == (None, (), ELSEWHERE)
    assert place.why == "Not counted, but 1 of 9 readers sees a window here."
    assert place.readers == {
        "answer": "nothing",
        "detector views": "a window in 0 of 8 views",
        "seg": "1 window",
    }


def test_a_weak_box_of_one_view_is_a_place_only_from_the_second_setting_on() -> None:
    counted = windows(A, B, C)
    faint = [window(ELSEWHERE, "v", score=0.2)]
    views = [[*counted, *faint], *[list(counted) for _ in range(7)]]
    found = check([*counted, window(A_NEXT, "w4")], [[*v, window(A_NEXT, "w4")] for v in views])
    assert [place.why for place in found.places] == [
        "These 2 boxes may be one window.",  # found at the first setting, so it comes first
        "Not counted, but 1 of 9 readers sees a window here.",
    ]
    too_faint = [[*counted, window(ELSEWHERE, "v", score=0.05)], *views[1:]]
    assert check(counted, too_faint).clean


def test_a_reader_that_counts_other_whole_windows_stops_the_page_being_clean() -> None:
    counted = windows(A, B, C)
    merged: Box = (0.1, 0.1, 0.6, 0.31)  # one box of the segmentation over A and B
    found = check(counted, seg=[window(merged, "s1"), counted[2]])
    assert not found.clean


def test_the_list_stops_at_the_limit_and_none_gives_all() -> None:
    boxes = [(0.1, 0.05 * row, 0.2, 0.05 * row + 0.01) for row in range(1, 9)]
    counted = windows(*boxes, score=0.5)
    assert len(check(counted).places) == 5
    assert len(check(counted, limit=None).places) == 8


def test_pages_are_checked_one_by_one_and_their_counts_add_up() -> None:
    wide = Page(page=2, width=2000, height=1000, unit="px")
    first = [window(A, "a"), window(A_NEXT, "b")]
    # on the wide page the same fractions are 4 px apart along the line: still one whole window
    second = [window(A, "c", page=2), window(A_NEXT, "d", page=2)]
    counted = [*first, *second]
    found = window_panes(counted, [counted], {}, [PAGE, wide])
    assert (found.whole, found.panes) == (2, 4)
    assert [(place.page, place.marks) for place in found.places] == [
        (1, ("a", "b")),
        (2, ("c", "d")),
    ]


def test_the_request_gives_both_counts_when_they_differ_and_says_why() -> None:
    assert request(check(windows(A, A_NEXT, B))) == (
        "Please double-check the windows: we count 2 windows if a window with several panes is "
        "one window, 3 if every pane is counted. Drawings differ in whether a window with several "
        "panes is one window or several, and we cannot tell which way this one was counted; "
        "1 place is marked on the drawing."
    )
    counted = windows(A, B, C)
    unsure = check(counted, seg=[*counted, window(ELSEWHERE, "s9")])
    assert request(unsure) == (
        "Please double-check the windows: we count 3 windows. Drawings differ in whether a window "
        "with several panes is one window or several, and we cannot tell which way this one was "
        "counted; 1 place is marked on the drawing."
    )

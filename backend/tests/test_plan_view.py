"""plan_views: the plan view(s) on a whole sheet, as boxes (spec #457 c6887370808, its three
synthetic pages: 3 px lines on a 3000 x 4500 1-bit-like page)."""

import numpy as np

from app.adapters.discipline_pictures.plan_view import Box, candidates, plan_views

H, W = 3000, 4500


def blank() -> np.ndarray:
    return np.full((H, W), 255, np.uint8)


def hline(img: np.ndarray, y: int, x0: int, x1: int) -> None:
    img[y : y + 3, min(x0, x1) : max(x0, x1) + 3] = 0


def vline(img: np.ndarray, x: int, y0: int, y1: int) -> None:
    img[min(y0, y1) : max(y0, y1) + 3, x : x + 3] = 0


def rect(img: np.ndarray, x0: int, y0: int, x1: int, y1: int) -> None:
    hline(img, y0, x0, x1)
    hline(img, y1, x0, x1)
    vline(img, x0, y0, y1)
    vline(img, x1, y0, y1)


def frame(img: np.ndarray) -> None:
    rect(img, 180, 120, 4320, 2880)


def plan(
    img: np.ndarray, x0: int, y0: int, x1: int, y1: int, seed: int = 0, broken: bool = False
) -> None:
    """Outer walls, 5 vertical and 3 horizontal partitions (>= 500 px), 40 short symbols;
    `broken`: every wall drawn as 60 px pieces with 20 px gaps."""

    def h(y: int, a: int, b: int) -> None:
        for x in range(a, b, 80) if broken else [a]:
            hline(img, y, x, min(b, x + 60) if broken else b)

    def v(x: int, a: int, b: int) -> None:
        for y in range(a, b, 80) if broken else [a]:
            vline(img, x, y, min(b, y + 60) if broken else b)

    h(y0, x0, x1)
    h(y1, x0, x1)
    v(x0, y0, y1)
    v(x1, y0, y1)
    for i in range(1, 6):
        v(x0 + (x1 - x0) * i // 6, y0, y0 + max(500, (y1 - y0) * 2 // 3))
    for i in range(1, 4):
        h(y0 + (y1 - y0) * i // 4, x0, x0 + max(600, (x1 - x0) // 2))
    rng = np.random.default_rng(seed)
    for _ in range(40):
        x, y, n = (
            int(rng.integers(x0, x1 - 60)),
            int(rng.integers(y0, y1 - 60)),
            int(rng.integers(20, 60)),
        )
        hline(img, y, x, x + n)


def title_and_table(img: np.ndarray) -> None:
    rect(img, 3400, 2300, 4300, 2860)
    for i in range(1, 8):
        hline(img, 2300 + 70 * i, 3400, 4300)
    for r in range(11):  # 10 rows x 4 columns of 120 x 40 cells at (200, 300)
        hline(img, 300 + 40 * r, 200, 680)
    for c in range(5):
        vline(img, 200 + 120 * c, 300, 700)


def contains(box: Box, inner: tuple[int, int, int, int], slack: float = 0.0) -> bool:
    s = slack * max(H, W)
    return (
        box[0] <= inner[0] + s
        and box[1] <= inner[1] + s
        and box[2] >= inner[2] - s
        and box[3] >= inner[3] - s
    )


def overlap(box: Box, other: tuple[int, int, int, int]) -> float:
    """Share of `other` inside `box`."""
    w = max(0, min(box[2], other[2]) - max(box[0], other[0]))
    h = max(0, min(box[3], other[3]) - max(box[1], other[1]))
    return w * h / ((other[2] - other[0]) * (other[3] - other[1]))


def within(box: Box, inner: tuple[int, int, int, int], margin: float) -> bool:
    """`box` holds `inner` and is no more than `margin` of the long side bigger on any side."""
    m = margin * max(H, W)
    return contains(box, inner) and all(abs(a - b) <= m for a, b in zip(box, inner, strict=True))


def test_one_plan_beside_a_frame_a_title_block_and_a_table() -> None:
    img = blank()
    frame(img)
    the_plan = (900, 500, 3300, 2000)
    plan(img, *the_plan)
    title_and_table(img)
    boxes = plan_views(img)
    assert boxes, boxes
    first = boxes[0]
    assert within(first, the_plan, 0.03), first
    assert overlap(first, (3400, 2300, 4300, 2860)) < 0.05
    assert overlap(first, (200, 300, 680, 700)) < 0.05
    assert candidates(img)[0] == first and candidates(img)[-1] == (0, 0, W, H)


def test_two_views_both_returned_the_bigger_first() -> None:
    img = blank()
    frame(img)
    upper, lower = (900, 300, 2700, 900), (900, 1200, 3400, 2500)
    plan(img, *upper, seed=1)
    plan(img, *lower, seed=2)
    boxes = plan_views(img)
    assert len(boxes) == 2, boxes
    assert contains(boxes[0], lower) and contains(boxes[1], upper), boxes
    assert overlap(boxes[0], upper) < 0.05 and overlap(boxes[1], lower) < 0.05


def test_a_plan_that_fills_the_page_puts_the_whole_page_first() -> None:
    """The outer walls span the page and go with the frame; a block of rooms inside them is
    left as a view, which must not come before the whole page (Bldg 550 West: the finder boxed
    a sub-region, the whole sheet registered right). The spec's numbers: the top and bottom
    walls 250 px from the edges lie outside a frame band of 6% of the height (180 px)."""
    img = blank()
    the_plan = (300, 250, 4200, 2750)
    rect(img, *the_plan)
    for x in (800, 2000, 3200):
        vline(img, x, 250, 2750)
    for y in (600, 1500, 2400):  # dashed grid lines: no run
        for x in range(0, W - 40, 60):
            hline(img, y, x, x + 40)
    plan(img, 2150, 700, 3050, 2100, seed=3)  # rooms free of the outer walls (550 West)
    found = candidates(img)
    assert found[0] == (0, 0, W, H), found
    assert len(found) > 1, found  # the rooms' box is still tried


def test_broken_walls_still_give_the_plan_never_the_frame_or_nothing() -> None:
    img = blank()
    frame(img)
    the_plan = (900, 500, 3300, 2000)
    plan(img, *the_plan, broken=True)
    title_and_table(img)
    found = candidates(img)
    assert found, found
    first = found[0]
    assert first != (180, 120, 4320, 2880)
    assert first == (0, 0, W, H) or within(first, the_plan, 0.10), found

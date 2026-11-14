"""Windows counted two ways, and the places a person is asked to double-check.

A drawing does not say whether a window with several panes is one window or several, and the
people who labelled our reference drawings went both ways, often on one sheet. So a window count
comes with two numbers and a list of places:

- `whole`: the counted boxes, with boxes that continue each other end to end merged into one;
- `panes`: the counted boxes, plus the extra boxes a reader sees inside one of them;
- `places`: where the count could change. A box that may be several panes, boxes that may be one
  window, a counted box that few readers see, a place readers see that was not counted. The
  strongest come first and the list stops at `limit`: a person checks five places, not forty;
- `clean`: at the loosest setting no counted box is weak and no place is uncounted, every reader
  counts the same whole windows, and no reader splits or joins a box. Only then is the count
  given without a request, and no place is listed (a window that is merely long does not count
  against a page: on its own it was not a sign of a wrong count).

The readers are the detector's views one by one (every box of a view, also the weak ones) and any
other reader of windows (the detector's first view after its threshold, the segmentation
network). Geometry is in page pixels: the settings were set by hand on CubiCasa scans about
1,000 px long, and not fitted to a score.

Measured on CubiCasa val (376 sheets, the detector's eight views, its first view and the
segmentation network as readers): the window count is right on 54% of sheets; 37 sheets are
clean and 36 of those are right; on the others the first five places cover 55% of the count's
errors and at least one error on 87% of the wrong sheets, and the reference count lies between
`whole` and `panes` on 69% of sheets. The settings and the clean rule were chosen on those
sheets, so the numbers are in-sample.
"""

from collections.abc import Mapping, Sequence
from statistics import median
from typing import NamedTuple

from app.core.drawing.model import Box, Element, Page
from app.core.model import Frozen

type Px = tuple[float, float, float, float]

GAP = 8.0  # px between two boxes on one line that still makes them one whole window
SAME = 0.5  # of the smaller box: from here two boxes are the same place
NEAR = 0.3  # of the smaller box: from here a reader's box belongs to a counted box
SHORTER = 0.75  # a box at most this long, against another, is a part of it


class Setting(NamedTuple):
    """How readily a place is called disputed; the looser, the more places."""

    floor: float  # a view's box counts from this score
    long: float  # a box this many times the page's median window may be several panes
    weak: float  # a counted box under this score is weak
    seen: float  # and so is one that less than this share of the readers see
    views: int  # an uncounted place needs this many views, or one other reader


# Strongest first: a place found at an earlier setting comes earlier in the list.
SETTINGS = (
    Setting(floor=0.3, long=1.8, weak=0.6, seen=0.55, views=3),
    Setting(floor=0.15, long=1.3, weak=0.7, seen=0.73, views=1),
    Setting(floor=0.1, long=1.2, weak=0.8, seen=0.91, views=1),
)
COUNTS_AT = 1  # the setting whose pane count is reported
MERGE, SPLIT, WEAK, UNCOUNTED = "merge", "split", "weak", "uncounted"
LONG = "This window is much longer than the others on the page and may count as several panes."


class WindowPlace(Frozen):
    """One place to double-check, in the shape the review screen draws (as a disputed mark)."""

    mark_id: str | None  # the first counted window here; None: a place that was not counted
    marks: tuple[str, ...]  # every counted window here (several when they may be one window)
    page: int
    box: Box
    why: str  # one plain sentence
    readers: dict[str, str]  # what the answer and each reader say is here


class WindowPanes(Frozen):
    whole: int
    panes: int
    clean: bool
    places: tuple[WindowPlace, ...]


type _Place = tuple[str, Px, tuple[int, ...], str]  # kind, box, counted windows, sentence


class _Found(NamedTuple):
    tier: int
    page: int
    box: Px
    marks: tuple[int, ...]  # indexes into the page's counted windows
    why: str


def window_panes(
    counted: Sequence[Element],
    views: Sequence[Sequence[Element]],
    others: Mapping[str, Sequence[Element]],
    pages: Sequence[Page],
    *,
    limit: int | None = 5,
) -> WindowPanes:
    """The two counts of `counted` (the answer's windows) and its places to double-check, at
    most `limit` (None: all). `views` holds the detector's windows view by view, each with its
    score; `others` the windows of every other reader, by the reader's name."""
    sizes = {page.page: (page.width, page.height) for page in pages}
    whole = panes = 0
    clean = True
    places: list[tuple[int, WindowPlace]] = []
    for number in sorted({e.page for group in (counted, *views, *others.values()) for e in group}):
        width, height = sizes[number]

        def px(element: Element, w: float = width, h: float = height) -> Px:
            x0, y0, x1, y1 = element.box
            return (x0 * w, y0 * h, x1 * w, y1 * h)

        mine = [e for e in counted if e.page == number]
        boxes = [px(e) for e in mine]
        scores = [_score(e) for e in mine]
        seen = [[(px(e), _score(e)) for e in view if e.page == number] for view in views]
        other = {name: [px(e) for e in found if e.page == number] for name, found in others.items()}
        listed: list[_Found] = []
        for tier, setting in enumerate(SETTINGS):
            readers = [[box for box, score in view if score >= setting.floor] for view in seen]
            found, sub = _disputed(boxes, scores, readers, list(other.values()), setting)
            for _, box, marks, why in found:
                if not any(_over(box, earlier.box) >= SAME for earlier in listed):
                    listed.append(_Found(tier, number, box, marks, why))
            if tier == COUNTS_AT:
                panes += sum(sub)
            if tier == len(SETTINGS) - 1:
                strips = len(_strips(boxes))
                clean = (
                    clean
                    and not any(kind in (WEAK, UNCOUNTED) for kind, *_ in found)
                    and all(len(_strips(theirs)) == strips for theirs in other.values())
                    and strips == len(boxes) == sum(sub)
                )
        whole += len(_strips(boxes))
        loosest = [[box for box, score in view if score >= SETTINGS[-1].floor] for view in seen]
        for item in listed:
            says = {"answer": _say(len(item.marks))}
            if views:
                at = [sum(_over(item.box, box) >= NEAR for box in view) for view in loosest]
                says["detector views"] = f"a window in {sum(n > 0 for n in at)} of {len(at)} views"
            says.update(
                {
                    name: _say(sum(_over(item.box, b) >= NEAR for b in found))
                    for name, found in other.items()
                }
            )
            x0, y0, x1, y1 = item.box
            place = WindowPlace(
                mark_id=mine[item.marks[0]].id if item.marks else None,
                marks=tuple(mine[i].id for i in item.marks),
                page=number,
                box=(_unit(x0 / width), _unit(y0 / height), _unit(x1 / width), _unit(y1 / height)),
                why=item.why,
                readers=says,
            )
            places.append((item.tier, place))
    places.sort(key=lambda entry: entry[0])
    shown = () if clean else tuple(place for _, place in places[:limit])
    return WindowPanes(whole=whole, panes=panes, clean=clean, places=shown)


def request(check: WindowPanes) -> str | None:
    """The sentence that asks for the double-check; None when the count needs none."""
    if check.clean:
        return None
    if check.whole == check.panes:
        count = f"we count {check.whole} windows"
    else:
        count = (
            f"we count {check.whole} windows if a window with several panes is one window, "
            f"{check.panes} if every pane is counted"
        )
    marked = len(check.places)
    where = (
        f"; {marked} place{'s are' if marked != 1 else ' is'} marked on the drawing"
        if marked
        else ""
    )
    return (
        f"Please double-check the windows: {count}. Drawings differ in whether a window with "
        f"several panes is one window or several, and we cannot tell which way this one was "
        f"counted{where}."
    )


def _disputed(
    boxes: list[Px],
    scores: list[float],
    views: list[list[Px]],
    others: list[list[Px]],
    setting: Setting,
) -> tuple[list[_Place], list[int]]:
    """The disputed places of one page at one setting, and per
    counted window the most boxes a single reader sees inside it (1: nobody splits it)."""
    readers = [*views, *others]
    seen = [0] * len(boxes)
    sub = [1] * len(boxes)
    for reader in readers:
        for i, box in enumerate(boxes):
            here = [found for found in reader if _over(box, found) >= SAME]
            seen[i] += bool(here)
            parts = [found for found in here if _length(found) <= SHORTER * _length(box)]
            if len(parts) >= 2:
                sub[i] = max(sub[i], len(parts))
    found: list[_Place] = []
    # boxes that may be one window: a strip of them, or one box of a reader over several
    groups = [strip for strip in _strips(boxes) if len(strip) > 1]
    for reader in readers:
        for big in reader:
            under = [
                i
                for i, box in enumerate(boxes)
                if _over(box, big) >= SAME and _length(box) <= SHORTER * _length(big)
            ]
            if len(under) >= 2 and not any(set(under) <= set(group) for group in groups):
                groups = [group for group in groups if not set(group) <= set(under)] + [under]
    grouped: set[int] = set()
    for group in groups:
        box = _union([boxes[i] for i in group])
        found.append((MERGE, box, tuple(group), f"These {len(group)} boxes may be one window."))
        grouped.update(group)
    usual = median(_length(box) for box in boxes) if boxes else 0.0
    few = round(setting.seen * len(readers))
    for i, box in enumerate(boxes):
        if i in grouped:
            continue
        if sub[i] >= 2:
            found.append((SPLIT, box, (i,), f"This window may count as {sub[i]} panes."))
        elif len(boxes) >= 3 and _length(box) >= setting.long * usual:
            found.append((SPLIT, box, (i,), LONG))
        elif seen[i] < few or scores[i] < setting.weak:
            why = f"Counted as a window, but only {_of(seen[i], len(readers))} a window here."
            found.append((WEAK, box, (i,), why))
    # places readers see that were not counted, one per place
    apart: list[tuple[Px, set[int]]] = []
    for index, reader in enumerate(readers):
        for box in reader:
            if any(_over(mine, box) >= NEAR for mine in boxes):
                continue
            for seed, who in apart:
                if _over(seed, box) >= SAME:
                    who.add(index)
                    break
            else:
                apart.append((box, {index}))
    for seed, who in apart:
        if sum(i < len(views) for i in who) >= setting.views or any(i >= len(views) for i in who):
            why = f"Not counted, but {_of(len(who), len(readers))} a window here."
            found.append((UNCOUNTED, seed, (), why))
    return found, sub


def _strips(boxes: Sequence[Px]) -> list[list[int]]:
    """The boxes grouped into whole windows: boxes on one line that touch end to end."""
    parent = list(range(len(boxes)))

    def root(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for i in range(len(boxes)):
        for j in range(i + 1, len(boxes)):
            if _continues(boxes[i], boxes[j]):
                parent[root(i)] = root(j)
    groups: dict[int, list[int]] = {}
    for i in range(len(boxes)):
        groups.setdefault(root(i), []).append(i)
    return list(groups.values())


def _continues(a: Px, b: Px) -> bool:
    """Two boxes lying the same way, on one line, at most GAP apart along it."""
    across_a, across_b = a[2] - a[0] >= a[3] - a[1], b[2] - b[0] >= b[3] - b[1]
    if across_a != across_b:
        return False
    along, side = (0, 1) if across_a else (1, 0)
    gap = max(a[along], b[along]) - min(a[along + 2], b[along + 2])
    thin = min(a[side + 2] - a[side], b[side + 2] - b[side])
    off = abs((a[side] + a[side + 2]) / 2 - (b[side] + b[side + 2]) / 2)
    return off <= max(2.0, 0.5 * thin) and gap <= GAP


def _over(a: Px, b: Px, pad: float = 2.0) -> float:
    """The overlap of two boxes as a share of the smaller. Each is grown by `pad` first: a
    window is a thin box, and a reader that is 2 px off must still land on it."""
    ax0, ay0, ax1, ay1 = a[0] - pad, a[1] - pad, a[2] + pad, a[3] + pad
    bx0, by0, bx1, by1 = b[0] - pad, b[1] - pad, b[2] + pad, b[3] + pad
    both = max(0.0, min(ax1, bx1) - max(ax0, bx0)) * max(0.0, min(ay1, by1) - max(ay0, by0))
    return both / min((ax1 - ax0) * (ay1 - ay0), (bx1 - bx0) * (by1 - by0))


def _length(box: Px) -> float:
    return max(box[2] - box[0], box[3] - box[1])


def _union(boxes: Sequence[Px]) -> Px:
    return (
        min(b[0] for b in boxes),
        min(b[1] for b in boxes),
        max(b[2] for b in boxes),
        max(b[3] for b in boxes),
    )


def _score(element: Element) -> float:
    score = element.attrs.get("score")
    return float(score) if isinstance(score, int | float) and not isinstance(score, bool) else 1.0


def _unit(value: float) -> float:
    return min(1.0, max(0.0, round(value, 5)))


def _say(count: int) -> str:
    return "nothing" if count == 0 else "1 window" if count == 1 else f"{count} windows"


def _of(count: int, readers: int) -> str:
    return f"{count} of {readers} readers see{'s' if count == 1 else ''}"

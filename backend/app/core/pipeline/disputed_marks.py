"""Where the other readers disagree with a count: the marks a person is asked to double-check.

An answer that is not certain keeps its value and asks for a second look. This says where to
look. The counted marks of one kind of thing (the doors, say) are set against what each other
reader saw of the same kind on the same sheet. Boxes that overlap by three tenths of the smaller
one are one place; a reader is at a place once. A place is disputed when at least `k` readers
disagree with the answer about it:

- a counted mark that they do not see: it carries the mark's id, a person can reject it;
- a place they see that the answer did not count: it has no id, a person can add it.

The strongest disputes come first (the most readers against; then the counted mark with the
lowest score, or the uncounted place with the highest), and the list stops at `limit`, because a
person checks five places and not forty.

Measured on CubiCasa val, doors and fixtures, with the readers that fit a live upload's time (the
detector's first view, a second detector in one view, the segmentation network's icons) at
k = 1: an error of 93 of the 170 wrong answers is among the places listed, 1.39 places per answer
that is not sure (docs/EXPERIMENTS.md section 13, "Double-check marks"). Errors that every reader
makes alike are not found this way.
"""

from collections.abc import Mapping, Sequence

from app.core.drawing.model import Box, Element
from app.core.model import Frozen

ANSWER = "answer"
OVERLAP = 0.3  # of the smaller box: from here two boxes are one place


class DisputedMark(Frozen):
    """One place to double-check, in the shape the review screen draws."""

    mark_id: str | None  # the counted element's id; None: a place the answer did not count
    page: int
    box: Box
    why: str  # one plain sentence
    readers: dict[str, str]  # what the answer and each reader say is here


def disputed_marks(
    counted: Sequence[Element],
    readers: Mapping[str, Sequence[Element]],
    *,
    noun: str,
    k: int,
    limit: int | None = 5,
) -> tuple[DisputedMark, ...]:
    """The places where at least `k` of `readers` disagree with `counted`, strongest first, at
    most `limit` (None: all). `counted` is the answer's elements of one kind of thing and each
    reader's elements are the same kind, as the caller selects them (a count of two classes
    together gets both); `noun` is that kind in the singular, for the sentences."""
    if ANSWER in readers:
        raise ValueError(f"a reader cannot be called {ANSWER!r}: that is the count itself")
    found: list[tuple[int, float, DisputedMark]] = []
    for seed, by in _places({ANSWER: counted, **readers}):
        mark = by.get(ANSWER)
        saw = [name for name in readers if name in by]
        against = len(readers) - len(saw) if mark is not None else len(saw)
        if against < k:
            continue
        says = {name: _says(by.get(name), noun) for name in (ANSWER, *readers)}
        if mark is not None:
            strength = 1.0 - _score(mark)
            why = f"Counted as a {noun}, but {_of(against, len(readers))} nothing here"
            if (views := _views(mark)) and "0" in views:
                why += f" and the detector saw it in {views.count('1')} of its {len(views)} views"
        else:
            strength = max(_score(by[name]) for name in saw)
            why = f"Not counted, but {_of(against, len(readers))} a {noun} here"
        item = DisputedMark(
            mark_id=None if mark is None else mark.id,
            page=seed.page,
            box=seed.box if mark is None else mark.box,
            why=why + ".",
            readers=says,
        )
        found.append((against, strength, item))
    found.sort(key=lambda entry: (-entry[0], -entry[1]))
    return tuple(item for _, _, item in found[:limit])


def _places(boxes: Mapping[str, Sequence[Element]]) -> list[tuple[Element, dict[str, Element]]]:
    """Every box put at a place, surest box first: it joins the first place whose first box it
    overlaps on its page and where its reader is not yet, else it starts a place. A place is its
    first box and each reader's box there."""
    order = sorted(
        ((name, element) for name, elements in boxes.items() for element in elements),
        key=lambda item: -_score(item[1]),
    )
    places: list[tuple[Element, dict[str, Element]]] = []
    for name, element in order:
        for seed, by in places:
            if (
                name not in by
                and seed.page == element.page
                and _overlap(element.box, seed.box) >= OVERLAP
            ):
                by[name] = element
                break
        else:
            places.append((element, {name: element}))
    return places


def _overlap(a: Box, b: Box) -> float:
    """The two boxes' intersection as a share of the smaller one."""
    width = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    height = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    smaller = min((a[2] - a[0]) * (a[3] - a[1]), (b[2] - b[0]) * (b[3] - b[1]))
    return width * height / max(smaller, 1e-12)


def _score(element: Element) -> float:
    score = element.attrs.get("score")
    return float(score) if isinstance(score, int | float) and not isinstance(score, bool) else 0.0


def _views(element: Element) -> str:
    """The views the detector saw the element in, one 0 or 1 per view; "" when it does not say."""
    views = element.attrs.get("views")
    return views if isinstance(views, str) and views and set(views) <= {"0", "1"} else ""


def _of(against: int, readers: int) -> str:
    return (
        f"{against} of the {readers} other reader{'s' if readers != 1 else ''} "
        f"{'sees' if against == 1 else 'see'}"
    )


def _says(element: Element | None, noun: str) -> str:
    if element is None:
        return "nothing"
    parts = [noun]
    if "score" in element.attrs:
        parts.append(f"score {_score(element):.2f}")
    if views := _views(element):
        parts.append(f"{views.count('1')} of {len(views)} views")
    return ", ".join(parts)

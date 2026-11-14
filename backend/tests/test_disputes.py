"""The places a double-check request points at, from the dispute finders on what the drawing
keeps (app/core/review/disputes.py), and the bedroom count that always asks under
ROOM_POLICY=furniture (app/core/review/check.py)."""

from app.adapters.answer_prior import NoPrior
from app.adapters.question_templates import TemplateParser
from app.composition import build_answering
from app.core.drawing.model import Drawing, Element, Page, ReaderView, Room, Scale
from app.core.review.ask import Asked, ask
from app.core.review.check import UNLABELLED, CheckPolicy
from app.core.review.disputes import find_disputes
from app.core.review.model import ReviewState
from app.settings import Settings

PAGE = Page(page=1, width=1000, height=1000, unit="px")
POLICY = CheckPolicy(thresholds={"door": 0.8, "room:bedroom": 0.8})


class Scored:
    def __init__(self, value: float) -> None:
        self.value, self.note = value, "decisions: stand-in"

    def probability(self, path: str, family: str, value: object) -> "Scored":
        return self


def sheet(**update: object) -> Drawing:
    return Drawing(file="plan.png", pages=(PAGE,), scale=Scale(status="no_scale")).model_copy(
        update=update
    )


def asked(text: str, drawing: Drawing, score: float = 0.1) -> Asked:
    return ask(
        text, drawing, parser=TemplateParser(), clock=lambda: 0.0, prior=NoPrior(),
        state=ReviewState(), confidence=Scored(score), raster=True, check=POLICY,
        route="raster", disputes=find_disputes,
    )  # fmt: skip


def window(n: int, x0: float, x1: float, y: float) -> Element:
    return Element(
        id=f"w{n}", class_="window", page=1, box=(x0, y, x1, y + 0.01), attrs={"score": 0.9}
    )


def test_a_window_whose_panes_may_be_one_window_is_one_item() -> None:
    counted = (window(1, 0.10, 0.15, 0.5), window(2, 0.152, 0.20, 0.5),
               window(3, 0.40, 0.45, 0.3), window(4, 0.60, 0.65, 0.7))  # fmt: skip
    seen = (window(9, 0.10, 0.20, 0.5), window(10, 0.40, 0.45, 0.3), window(11, 0.60, 0.65, 0.7))
    drawing = sheet(
        elements=counted, double_check={"l1": ReaderView(read=("window",), elements=seen)}
    )
    found = asked("How many windows are there?", drawing)
    assert found.check is not None
    w1 = next(mark.id for mark in found.marks if mark.ref == "w1")
    assert [d.mark_id for d in found.check.disputed] == [w1]
    assert found.check.disputed[0].why == "These 2 boxes may be one window."


def test_doors_point_where_another_reader_disagrees() -> None:
    doors = tuple(
        Element(id=f"e{n}", class_="door", page=1, box=box, attrs={"score": 0.9})
        for n, box in ((1, (0.1, 0.1, 0.2, 0.2)), (2, (0.3, 0.3, 0.4, 0.4)))
    )
    seen = (Element(id="s1", class_="door", page=1, box=(0.1, 0.1, 0.2, 0.2)),
            Element(id="s2", class_="door", page=1, box=(0.6, 0.6, 0.7, 0.7)))  # fmt: skip
    drawing = sheet(elements=doors, double_check={"l1": ReaderView(read=("door",), elements=seen)})
    found = asked("How many doors are there?", drawing)
    assert found.check is not None
    m2 = next(mark.id for mark in found.marks if mark.ref == "e2")
    assert sorted(str(d.mark_id) for d in found.check.disputed) == sorted([m2, "None"])
    alone = asked("How many doors are there?", sheet(elements=doors)).check
    assert alone is not None and alone.disputed == ()  # no reader ran: nothing to set it against


BEDROOMS = (
    Room(id="r1", type="bedroom", page=1, box=(0.05, 0.5, 0.25, 0.7), label="MH"),
    Room(id="r2", type="bedroom", page=1, box=(0.3, 0.5, 0.5, 0.7)),
)


def test_a_bedroom_count_with_an_unlabelled_bedroom_always_asks_and_names_it() -> None:
    """ROOM_POLICY=furniture counts a room drawn with a bed and no printed label as a bedroom;
    the reference answers would not: a high score does not certify it."""
    found = asked("How many bedrooms are there?", sheet(rooms=BEDROOMS), score=0.95)
    assert found.check is not None
    assert found.check.reason == (
        "Please double-check the room bedroom count: 1 room is drawn as a bedroom with no "
        "printed label; please confirm."
    )
    r2 = next(mark.id for mark in found.marks if mark.ref == "r2")
    first = found.check.disputed[0]
    assert (first.mark_id, first.why) == (r2, UNLABELLED)
    assert [d.mark_id for d in found.check.disputed].count(r2) == 1  # not listed twice


def test_labelled_bedrooms_are_certified_on_their_score() -> None:
    labelled = (BEDROOMS[0], BEDROOMS[1].model_copy(update={"label": "MH2"}))
    assert asked("How many bedrooms are there?", sheet(rooms=labelled), score=0.95).check is None


def test_the_api_answers_with_the_finders() -> None:
    assert build_answering(Settings()).disputes is find_disputes

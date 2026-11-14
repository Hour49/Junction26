"""The double-check request (CHECK_POLICY): an answer we can't vouch for keeps its value and asks a
person to look, at the places where the readers disagree.

An answer is certified when golden's check policy (chosen on val by D455: per family, the
threshold that maximises answers certified - 10 x wrong ones) clears it: on the raster route its
score is at or above its family's threshold on a page ingest did not flag (a phone photo, a scan:
the policy was chosen on CubiCasa scans); on another route the route itself was certified on
golden v2's holdout. Every other answer, a family the policy has no threshold for included, gets
`Check`: a sentence and the disputed places (`Disputes`, at most a few), each pointing at the
review mark a person can reject or settle (`mark_id`) or, with no mark, at a place the answer did
not count, which a person can add. A refusal has no value to check; a quantity a person signed off
is theirs, not ours, so neither gets one.
"""

from collections.abc import Callable, Mapping, Sequence

from app.core.drawing.model import Box, Drawing
from app.core.model import Frozen
from app.core.review.model import MarkView, Row

NOTHING = "nothing"  # what a reader that sees nothing at a place says
LIMIT = 5  # places listed per answer: a person checks five, not forty
SCHEDULE = "schedule"  # the route a value read from a printed schedule is certified as
SCHEDULE_REASON = (
    "Please double-check this value against the schedule printed on the sheet: values read "
    "from schedules are not yet checked often enough to be sure."
)


class CheckPolicy(Frozen):
    """golden's check policy as the API applies it (app/adapters/check_policy.py)."""

    thresholds: dict[str, float]  # family -> lowest score certified, raster route
    routes: frozenset[str] = frozenset()  # routes whose answers are certified as they are


class Place(Frozen):
    """A place a dispute finder lists, by the drawing model's ids (core/pipeline/disputed_marks,
    room_disputes): `item_id` the counted element or room, None for a place it did not count."""

    item_id: str | None
    page: int
    box: Box
    why: str
    readers: Mapping[str, str | None]  # what the answer and each reader say there


class Disputed(Frozen):
    """One place to double-check, as the answer gives it."""

    mark_id: str | None  # the review mark (MarkView.id); None: not counted, a person can add it
    page: int
    box: Box
    why: str  # one plain sentence
    readers: dict[str, str]  # reader -> what it says here ("nothing": it sees nothing)


class Check(Frozen):
    """The double-check request on an answer that is not certified."""

    reason: str  # one plain sentence for the person
    disputed: tuple[Disputed, ...]  # strongest first; empty: no reader points anywhere


# (the drawing, the answer's row) -> the places to look at for it
Disputes = Callable[[Drawing, Row], Sequence[Place]]


def no_disputes(drawing: Drawing, row: Row) -> Sequence[Place]:
    """No dispute finder: the request asks for a look without pointing at a place."""
    return ()


def certified(
    policy: CheckPolicy,
    *,
    route: str | None,
    family: str | None,
    score: float | None,
    flags: Sequence[str],
) -> bool:
    if flags:
        return False  # the policy was chosen on scans of plans, not on photos
    if route != "raster":
        return route in policy.routes
    threshold = None if family is None else policy.thresholds.get(family)
    return threshold is not None and score is not None and score >= threshold


def double_check(row: Row, marks: Sequence[MarkView], places: Sequence[Place]) -> Check | None:
    """The request for `row`'s answer, which is not certified; None once a person signed it off.
    A place whose counted item has no mark in `marks` is left out: there is nothing to point
    at. At most `LIMIT` places, in the finder's order (strongest first)."""
    if row.signed is not None:
        return None
    mark_of = {mark.ref: mark.id for mark in marks if mark.ref is not None}
    disputed: list[Disputed] = []
    for place in places:
        if place.item_id is not None and place.item_id not in mark_of:
            continue
        disputed.append(
            Disputed(
                mark_id=None if place.item_id is None else mark_of[place.item_id],
                page=place.page,
                box=place.box,
                why=place.why,
                readers={name: says or NOTHING for name, says in place.readers.items()},
            )
        )
    listed = tuple(disputed[:LIMIT])
    return Check(reason=_reason(row, len(listed)), disputed=listed)


def schedule_check(policy: CheckPolicy) -> Check | None:
    """The request on a value read from a schedule: none when the policy certified the route."""
    return None if SCHEDULE in policy.routes else Check(reason=SCHEDULE_REASON, disputed=())


def _reason(row: Row, places: int) -> str:
    what = row.noun or row.label  # "doors"; "room bedroom count" for a count of no one class
    if places:
        where = "one place" if places == 1 else f"{places} places"
        return (
            f"Please double-check the {what}: the readers disagree at {where}, marked on the "
            "drawing."
        )
    return (
        f"Please double-check the {what}: on drawings like this one we can't be sure enough to "
        "give it without a look."
    )

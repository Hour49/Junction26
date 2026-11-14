"""The double-check request (CHECK_POLICY): an answer we can't vouch for keeps its value and asks a
person to look, at the places where the readers disagree.

An answer is certified when golden's check policy (chosen on val by D455: per family, the
threshold that maximises answers certified - 10 x wrong ones) clears it: on the raster route its
score is at or above its family's threshold on a page ingest did not flag (a phone photo, a scan:
the policy was chosen on CubiCasa scans); on another route the route itself was certified on
golden v2's holdout. Every other answer, a family the policy has no threshold for included, gets
`Check`: a sentence and the disputed places (`Disputes`, at most a few), each pointing at the
review mark a person can reject or settle (`mark_id`) or, with no mark, at a place the answer did
not count, which a person can add; a mark the person rejected is never pointed at again.

Some answers are never certified, whatever their score (`held`; D452 "if it doesn't agree, show it
to the user", review of #129 B1, 2026-11-14): two methods disagree (also when a rule picked one
value), the value is an estimate, a person changed its marks (the score rated the pipeline's
value, not theirs), or a bedroom count includes a room typed a bedroom from what is drawn in it,
with no printed label (orchestrator, golden-22: the demo's ROOM_POLICY=furniture counts those; the
reference answers type a room by its label alone). A refusal has no value to check; a quantity a
person settled or signed off is theirs, not ours, so neither gets one.
"""

from collections.abc import Callable, Mapping, Sequence

from app.core.drawing.model import Box, Drawing, Room
from app.core.model import Frozen
from app.core.review.model import MarkView, Row
from app.core.review.proof import SHOWN_UNITS

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


class Found(Frozen):
    """What a dispute finder says about an answer: the places to look at, strongest first, and,
    when it knows why the count is uncertain, the sentence to ask with."""

    places: tuple[Place, ...] = ()
    reason: str | None = None


# (the drawing, the answer's row) -> the places to look at for it
Disputes = Callable[[Drawing, Row], Found]


def no_disputes(drawing: Drawing, row: Row) -> Found:
    """No dispute finder: the request asks for a look without pointing at a place."""
    return Found()


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


UNLABELLED = "Drawn as a bedroom, no label: please confirm."


def unlabelled_bedrooms(row: Row, drawing: Drawing) -> list[Room]:
    """The bedrooms `row` counts (its marks not rejected) that carry no printed label: typed a
    bedroom from what is drawn in them."""
    if row.measure != "count" or row.subject != "room:bedroom":
        return []
    counted = {mark.ref for mark in row.marks if mark.state != "rejected" and mark.ref}
    return [
        room
        for room in drawing.rooms
        if room.id in counted and room.type == "bedroom" and not (room.label or "").strip()
    ]


def held(row: Row, drawing: Drawing) -> str | None:
    """Why `row`'s answer is never certified, whatever its score, as the request's sentence: two
    methods disagree (a rule's pick included), it is an estimate, a person changed its marks
    and has not signed off, or it counts bedrooms with no printed label. None: nothing holds
    it."""
    what = row.noun or row.label
    if row.conflict is not None:
        if row.first is None or row.second is None:
            return f"Please double-check the {what}: two methods disagree."
        unit = "" if row.unit == "count" else f" {SHOWN_UNITS.get(row.unit, row.unit)}"
        values = [_shown(row, v) for v in (row.first.value, row.second.value, row.value)]
        return (
            f"Please double-check the {what}: two methods disagree: {values[0]} vs {values[1]}"
            f"{unit}; we show {values[2]}."
        )
    if row.estimate is not None:
        return f"Please double-check the {what}: it is an estimate ({row.estimate})."
    if row.status == "edited":
        return f"Please double-check the {what}: edited by you: sign off to confirm."
    if unlabelled := unlabelled_bedrooms(row, drawing):
        some = "1 room is" if len(unlabelled) == 1 else f"{len(unlabelled)} rooms are"
        return (
            f"Please double-check the {what}: {some} drawn as a bedroom with no printed label; "
            "please confirm."
        )
    return None


def double_check(
    row: Row, marks: Sequence[MarkView], found: Found, reason: str | None = None
) -> Check | None:
    """The request for `row`'s answer, which is not certified, with `reason` (`held`'s), else
    the finder's sentence, else the policy's; None once a person settled or signed it off. A
    place whose counted item has no mark in `marks`, or only one the person rejected, is left
    out: there is nothing to point at. At most `LIMIT` places, in the finder's order (strongest
    first)."""
    if row.signed is not None or row.settled is not None:
        return None
    mark_of = {
        mark.ref: mark.id for mark in marks if mark.ref is not None and mark.state != "rejected"
    }
    disputed: list[Disputed] = []
    for place in found.places:
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
    return Check(reason=reason or found.reason or _reason(row, len(listed)), disputed=listed)


def schedule_check(policy: CheckPolicy) -> Check | None:
    """The request on a value read from a schedule: none when the policy certified the route."""
    return None if SCHEDULE in policy.routes else Check(reason=SCHEDULE_REASON, disputed=())


def _shown(row: Row, value: float) -> str:
    return str(round(value)) if row.unit == "count" else f"{value:.2f}"


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

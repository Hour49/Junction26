"""The double-check request (CHECK_POLICY): an answer we can't vouch for keeps its value and asks a
person to look, at the places where the readers disagree.

An answer is certified when golden's check policy (chosen on val by D455: per family, the
threshold that maximises answers certified - 10 x wrong ones) clears it: on the raster route its
score is at or above its family's threshold on a page ingest did not flag (a phone photo, a scan:
the policy was chosen on CubiCasa scans); on another route the route itself was certified on
golden v2's holdout. A family's score is the answer confidence's (DECISIONS_CONFIDENCE) or, when
its threshold was chosen on a local gate's signal (local-dec's lgate models, LOCAL_GATES), that
gate's score of the answered count (`Scorer`). Every other answer, a family the policy has no
threshold for included, gets
`Check`: a sentence and the disputed places (`Disputes`, at most a few), each pointing at the
review mark a person can reject or settle (`mark_id`) or, with no mark, at a place the answer did
not count, which a person can add; a mark the person rejected is never pointed at again.

Some answers are never certified, whatever their score (`held`; D452 "if it doesn't agree, show it
to the user", review of #129 B1, 2026-11-14): two methods disagree (also when a rule picked one
value), the value is an estimate, a person changed its marks (the score rated the pipeline's
value, not theirs), or a bedroom count includes a room typed a bedroom from what is drawn in it,
with no printed label (orchestrator, golden-22: the demo's ROOM_POLICY=furniture counts those; the
reference answers type a room by its label alone). A plan count is certified only when the answer
confidence's own most likely count is the answered one (`AGREEING_FAMILIES`, #174: hand-drawn
sketches got wrong plan counts with a high score where Gemini counted otherwise). Nothing is
certified on a raster drawing on which the detector found no plan and no located element
(`found_nothing`; a disclosed safety rule, chosen after seeing it fail on 50 archive sheets, AR,
orchestrator 2026-11-14 17:24): every reader then agrees on 0 because none of them saw the
drawing, and that agreement is no evidence; its answers are Low. A refusal has no value to
check; a quantity a person settled or signed off is theirs, not ours, so neither gets one.

The same verdict gives each rated answer a confidence level (`level_of`, decision 0011): High
exactly when it is certified, so a level never contradicts the request; an answer that asks is
Medium when its score is at or above its family's second threshold (`medium`: the calibrated
P(wrong) is at most the policy's cut), Low below it; a route takes the level its own reference
answers gave it. The words under a level quote the counts it was measured on, from the policy file.
"""

from collections.abc import Callable, Iterable, Mapping, Sequence
from types import MappingProxyType
from typing import Literal, NamedTuple

from pydantic import Field

from app.core.answering.answer import AGREEING_FAMILIES
from app.core.answering.local_gate import READER_FAMILIES, LocalGateModel, reading_of, score
from app.core.drawing.model import Box, CarbonCheck, Drawing, Room, RoomType
from app.core.model import Frozen
from app.core.pipeline.count_arbiter import count_arbiter_reading
from app.core.pipeline.room_policy import says_only_room
from app.core.review.model import MarkView, Row
from app.core.review.proof import SHOWN_UNITS

NOTHING = "nothing"  # what a reader that sees nothing at a place says
LIMIT = 5  # places listed per answer: a person checks five, not forty
SCHEDULE = "schedule"  # the route a value read from a printed schedule is certified as
SCHEDULE_REASON = (
    "Please double-check this value against the schedule printed on the sheet: values read "
    "from schedules are not yet checked often enough to be sure."
)


LevelName = Literal["high", "medium", "low"]
LEVELS: tuple[LevelName, ...] = ("low", "medium", "high")  # lowest first
# What a level rests on: the policy's certificate on a raster answer; the route's own reference
# answers; the answer's score against its family's Medium threshold; a page flagged at upload; a
# value held for a check whatever its score; nothing measured; Gemini Carbon reading it otherwise
# (Low), or the same (High, CARBON_LEVELS=ladder)
Basis = Literal["certified", "route", "score", "page", "held", "unrated", "carbon"]


class Counts(Frozen):
    """The measured answers a level's sentence quotes: how many, and how many were exact."""

    units: int
    exact: int


class CheckPolicy(Frozen):
    """golden's check policy as the API applies it (app/adapters/check_policy.py)."""

    thresholds: dict[str, float]  # family -> lowest score certified, raster route
    routes: frozenset[str] = frozenset()  # routes whose answers are certified as they are
    # family -> the local scorer (LOCAL_GATES) its threshold is on, by signal name; a family not
    # here is on the answer confidence's signal
    signals: dict[str, str] = Field(default_factory=dict[str, str])
    # Levels (decision 0011). medium: family -> lowest score that is Medium, on the threshold's
    # signal; a family not here has no Medium. route_levels: route -> the level of its answers;
    # route_counts: its reference answers. counts: the val cross-fit answers at each level;
    # None: the file carries no levels, so no answer gets one.
    medium: dict[str, float] = Field(default_factory=dict[str, float])
    route_levels: dict[str, LevelName] = Field(default_factory=dict[str, LevelName])
    route_counts: dict[str, Counts] = Field(default_factory=dict[str, Counts])
    counts: dict[LevelName, Counts] | None = None


class Level(Frozen):
    """How far to trust an answer: one of three levels, what it rests on, and one plain sentence
    with the measured counts behind it."""

    level: LevelName
    basis: Basis
    text: str


# (the drawing, the family, the answered count) -> the signal's P(the count is exact); None: it
# can't score this answer
Scorer = Callable[[Drawing, str, int], float | None]
NO_SCORERS: Mapping[str, Scorer] = MappingProxyType({})
# What a local gate model may read from the count arbiter's reading kept with the drawing (L1's
# probabilities, the arbiter's P): only an arbiter-t1 ingest stores it
ARBITER_BLOCKS = frozenset({"l1", "arbiter_p"})


def gate_scorer(model: LocalGateModel) -> Scorer:
    """The local gate `model` as a scorer: None for a family it was not fit on, and on a
    drawing that lacks what it reads, where its features would not be the ones it was fit on: the
    count arbiter's reading of the family (`ARBITER_BLOCKS`; a missing arbiter P would read as 0)
    or a double-check reader it reads (every one would read as "did not look"). Its families
    then ask."""

    def scored(drawing: Drawing, family: str, answer: int) -> float | None:
        if model.blocks & ARBITER_BLOCKS and count_arbiter_reading(drawing, family) is None:
            return None  # the count arbiter did not run on this drawing
        reads = model.readers if "readers" in model.blocks and family in READER_FAMILIES else ()
        if any(name not in (drawing.double_check or {}) for name in reads):
            return None  # a reader the model reads did not run (DOUBLE_CHECK_READERS)
        return score(model, family, reading_of(drawing, family, answer))

    return scored


def score_of(
    policy: CheckPolicy,
    family: str,
    *,
    confidence: float | None,
    drawing: Drawing,
    value: object,
    scorers: Mapping[str, Scorer],
) -> float | None:
    """The score `policy` reads for an answer of `family`: the answer `confidence`, or, for a
    family whose threshold is on a local scorer, that scorer's score of the answered count
    (None: the scorer is not configured, or the value is not a count)."""
    signal = policy.signals.get(family)
    if signal is None:
        return confidence
    scorer = scorers.get(signal)
    if scorer is None or isinstance(value, bool) or not isinstance(value, int):
        return None
    return scorer(drawing, family, value)


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


def found_nothing(drawing: Drawing) -> bool:
    """True when the detector found no plan and no located element on the drawing (an element a
    second reader counted with no position of its own does not count: its box is its plan's,
    app/core/review/review.py unlocated_boxes). Its counts are every reader's 0 on a sheet none
    of them read, so none is certified (on the raster route)."""
    located = any(element.attrs.get("located") is not False for element in drawing.elements)
    return bool(drawing.pages) and not drawing.plans and not located


class RoomWord(NamedTuple):
    """What a room's printed label names: a room type, and whether the word belongs to a kind of
    sheet the policy was not measured on (`unmeasured`: a Swiss floor's room names; CubiCasa val
    prints none)."""

    kind: RoomType
    unmeasured: bool


# a room's printed label -> what it names; None: no room word we know (composition gives the
# adapters' tables: app/adapters/raster/room_words.py)
RoomWords = Callable[[str], RoomWord | None]


def no_room_words(label: str) -> RoomWord | None:
    """No label table: no room count is doubted by its labels."""
    return None


def room_word_doubt(row: Row, drawing: Drawing, words: RoomWords) -> Found | None:
    """Why a count on an image is not certified, whatever its score, from the labels read in its
    rooms (think-acc's certified-wrong Swiss bathroom, .agents/exp/certified-bathroom.md,
    orchestrator 2026-11-14): for a count of a room type, a room whose label names that type is
    typed otherwise (each such room is a place, not counted); for any count, a label is a word
    of a sheet the policy was not measured on, where the readers and the signals carry
    CubiCasa's conventions (orchestrator gen 29, 21:59, post hoc and conservative: think-acc's
    paid read of 19 lone Swiss PNGs found its two High-and-wrong answers in toilet counts,
    certified by a local gate). None: neither. It holds the certificate only: the level stays
    what the score gives (on CubiCasa val 0 High answers and 2 Medium ones have such a room; the
    Medium ones keep their level)."""
    if row.measure != "count":
        return None
    kind = row.subject.removeprefix("room:") if row.subject.startswith("room:") else ""
    what = row.noun or row.label
    named = [(room, word) for room in drawing.rooms if room.label and (word := words(room.label))]
    off = [room for room, word in named if kind and word.kind == kind and room.type != kind]
    if off:
        places = tuple(
            Place(
                item_id=None,
                page=room.page,
                box=room.box,
                why=(
                    f'Labelled "{_label_line(room)}", which names a {kind}, but read as type '
                    f'"{room.type}", so it is not counted.'
                ),
                readers={"reader": room.type, "label": kind},
            )
            for room in off
        )
        some = "a room is" if len(off) == 1 else f"{len(off)} rooms are"
        return Found(
            places=places,
            reason=(
                f"Please double-check the {what}: {some} labelled as the type asked about but "
                "read as another type."
            ),
        )
    printed = unmeasured_room(drawing, words)
    if printed is not None:
        return Found(
            reason=(
                f"Please double-check the {what}: this image prints room names such as "
                f'"{_label_line(printed)}", and counts on plans of this kind are not in our '
                "validation, so none is certified."
            )
        )
    return None


def unmeasured_room(drawing: Drawing, words: RoomWords) -> Room | None:
    """The first room whose label is a word of a sheet the policy was not measured on (a Swiss
    room name); None: no such room. A count on such an image is Low (`level_of` `unmeasured`)."""
    return next(
        (
            room
            for room in drawing.rooms
            if room.label and (w := words(room.label)) and w.unmeasured
        ),
        None,
    )


def only_room_word(kind: str, drawing: Drawing) -> tuple[Room, ...]:
    """The rooms that leave a count of `kind` rooms unsaid: no room is typed `kind`, and these
    were typed `kind` by the reader from a label that says only "room" ("Rum", "HUONE", "H":
    room_policy.generic_word_rooms). The drawing then does not say which rooms are of the kind, so
    0 would be a number it does not give (jf06: ten rooms labelled "Rum", .agents/exp/
    judge-fresh-fixes.md). Empty: a room is typed `kind` (the count stands, with these as
    places to look at), or no room was retyped."""
    if any(room.type == kind for room in drawing.rooms):
        return ()
    return tuple(
        room
        for room in drawing.rooms
        if room.attrs.get("retyped_from") == kind and says_only_room(room.label)
    )


def room_word_refusal(kind: str, rooms: Sequence[Room]) -> str:
    """Why a count `only_room_word` leaves unsaid gets no number."""
    some = "1 room is" if len(rooms) == 1 else f"{len(rooms)} rooms are"
    return (
        f"This drawing doesn't say which rooms are {kind}s: {some} labelled only "
        f'"{_label_line(rooms[0])}", a word for any room.'
    )


def _label_line(room: Room) -> str:
    return (room.label or "").strip().split("\n")[0].strip()


def certified(
    policy: CheckPolicy,
    *,
    route: str | None,
    family: str | None,
    score: float | None,
    flags: Sequence[str],
    agrees: bool | None = None,
    blank: bool = False,
) -> bool:
    """`agrees`: whether the answer confidence's own most likely count is the answered one (None:
    it gives none); a family in `AGREEING_FAMILIES` needs True on the raster route. `blank`:
    `found_nothing` of the drawing; nothing on it is certified on the raster route."""
    if flags:
        return False  # the policy was chosen on scans of plans, not on photos
    if route != "raster":
        return route in policy.routes
    if blank:
        return False  # the readers agree because none of them saw anything
    if family in AGREEING_FAMILIES and agrees is not True:
        return False  # a second reader counts otherwise, or there is none to agree
    threshold = None if family is None else policy.thresholds.get(family)
    return threshold is not None and score is not None and score >= threshold


ASK = {"high": "", "medium": " Please double-check it.", "low": " Check it before you use it."}
PAGE_TEXT = (
    "Low confidence: this page was flagged when it was uploaded, and answers on such pages are "
    "not measured." + ASK["low"]
)
SUMMED_REASON = (
    "Please double-check this value against the schedule printed on the sheet: it is added up "
    "from several rows, or a room's area taken from the schedule, which is not measured."
)
SUMMED_TEXT = (
    "Low confidence: this value is added up from schedule rows or taken from the room schedule, "
    "and such values are not measured." + ASK["low"]
)
HELD_TEXT = (
    "Low confidence: this value is held for a check whatever its score; the double-check "
    "request says why." + ASK["low"]
)
UNRATED_TEXT = "Low confidence: we have no measurement behind this answer." + ASK["low"]
UNMEASURED_TEXT = (
    "Low confidence: plans of this kind are not in our validation, so no measurement stands "
    "behind this answer." + ASK["low"]
)
BLANK_TEXT = (
    "Low confidence: nothing was found on this page (no plan, no element), so the readers "
    "agreeing is not evidence." + ASK["low"]
)

# integ's pre-registered test of CARBON_LEVELS=demote on 256 unseen val pages (.agents/exp/integ.md
# AW pre-registration 2, 2026-11-14): of the 109 Medium answers Carbon counted otherwise, 80 exact
CARBON_DEMOTED = Counts(units=109, exact=80)
# CARBON_LEVELS=ladder on the same pages (.agents/exp/integ.md BQ): of the 563 Medium answers it
# counted the same, 536 exact
CARBON_AGREED = Counts(units=563, exact=536)


def carbon_checked(
    level: Level, check: CarbonCheck, carbon: object, said: object, *, ladder: bool = False
) -> Level:
    """CARBON_LEVELS=demote on an answer's level: a Medium answer whose question Carbon answers
    with another value (`carbon`) than the one shown (`said`) becomes Low; Carbon agreeing or
    refusing (None) changes nothing. With `ladder` (CARBON_LEVELS=ladder) a Medium answer Carbon
    answers with the same value becomes High: two readers agree (Carbon alone never makes one).
    When Carbon checked nothing (`check.failed`), the level stays and its sentence says so.
    Other levels are left as they are."""
    if level.level != "medium":
        return level
    if check.failed is not None:
        return level.model_copy(
            update={"text": f"{level.text} Gemini Carbon did not check it: {check.failed}."}
        )
    if carbon is None:
        return level
    if carbon == said:
        if not ladder:
            return level
        measured = round(100 * CARBON_AGREED.exact / CARBON_AGREED.units)
        text = (
            "High confidence: checked by Carbon: two readers agree. Gemini Carbon, read as a "
            f"second reader, counted the same here. On our validation plans, {measured}% of the "
            f"answers checked this way were exact ({CARBON_AGREED.exact} of "
            f"{CARBON_AGREED.units})." + ASK["high"]
        )
        return Level(level="high", basis="carbon", text=text)
    read = int(carbon) if isinstance(carbon, float) and carbon.is_integer() else carbon
    measured = round(100 * CARBON_DEMOTED.exact / CARBON_DEMOTED.units)
    text = (
        f"Low confidence: Gemini Carbon, read as a second reader, counted {read} here. On our "
        f"validation plans, {measured}% of the answers it counted differently were exact "
        f"({CARBON_DEMOTED.exact} of {CARBON_DEMOTED.units})." + ASK["low"]
    )
    return Level(level="low", basis="carbon", text=text)


def level_of(
    policy: CheckPolicy,
    *,
    sure: bool,
    route: str | None,
    family: str | None,
    score: float | None,
    flags: Sequence[str],
    held: bool = False,
    blank: bool = False,
    unmeasured: bool = False,
) -> Level | None:
    """The level of an answer `policy` rated `sure` or not (None: the policy file carries no
    levels). High exactly when sure. Else Low on a flagged page, on a raster drawing where
    nothing was found (`blank`, `found_nothing`), on a value `held` for a check (its score, if
    any, did not rate what is shown) and on a raster count on a plan of a kind the policy was not
    measured on (`unmeasured`: a Swiss image, `unmeasured_room`; its Medium would quote the
    validation's counts, orchestrator gen 29, 2026-11-14); off the raster route, the route's
    own level; on it, Medium at or above the family's `medium` score and Low below. A family with no
    threshold, an answer with no score and a route with no level are Low: nothing was measured."""
    if policy.counts is None:
        return None
    if sure:
        if route == "raster":
            return _measured("high", "certified", policy.counts["high"])
        return _on_route(policy, "high", route)
    if flags:
        return Level(level="low", basis="page", text=PAGE_TEXT)
    if blank and route == "raster":
        return Level(level="low", basis="page", text=BLANK_TEXT)
    if held:
        return Level(level="low", basis="held", text=HELD_TEXT)
    if unmeasured and route == "raster":
        return Level(level="low", basis="unrated", text=UNMEASURED_TEXT)
    if route != "raster":
        made = None if route is None else policy.route_levels.get(route)
        if made is None or made == "high":  # no level, or a certified route's answer that asks
            return Level(level="low", basis="unrated", text=UNRATED_TEXT)
        return _on_route(policy, made, route)
    if family is None or family not in policy.thresholds or score is None:
        return Level(level="low", basis="unrated", text=UNRATED_TEXT)
    medium = policy.medium.get(family)
    made = "medium" if medium is not None and score >= medium else "low"
    return _measured(made, "score", policy.counts[made])


def lowest(levels: Iterable[LevelName]) -> LevelName | None:
    """The lowest of `levels`, as a total over several answers is trusted; None for none."""
    return min(levels, key=LEVELS.index, default=None)


def _measured(level: LevelName, basis: Basis, counts: Counts) -> Level:
    said = f"{level.capitalize()} confidence: "
    if counts.units:
        said += (
            f"on our validation plans, {round(100 * counts.exact / counts.units)}% of the answers "
            f"rated this way were exact ({counts.exact} of {counts.units})."
        )
    else:
        said += "no validation answer was rated this way."
    return Level(level=level, basis=basis, text=said + ASK[level])


def _on_route(policy: CheckPolicy, level: LevelName, route: str | None) -> Level:
    counts = None if route is None else policy.route_counts.get(route)
    said = f"{level.capitalize()} confidence: on our reference drawings of this kind"
    if counts is None or not counts.units:
        said += ", answers read this way were checked."
    else:
        said += f", {counts.exact} of {counts.units} answers were exact."
    return Level(level=level, basis="route", text=said + ASK[level])


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
    (signed off or not: once signed, `double_check` asks nothing, but the answer is still not
    certified), or it counts bedrooms with no printed label. None: nothing holds it."""
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
    if row.status == "edited" or row.value != row.original_value:
        # the score rated the pipeline's value; a signed row hides its edit from `status`
        return f"Please double-check the {what}: edited by you: sign off to confirm."
    if unlabelled := unlabelled_bedrooms(row, drawing):
        some = "1 room is" if len(unlabelled) == 1 else f"{len(unlabelled)} rooms are"
        return (
            f"Please double-check the {what}: {some} drawn as a bedroom with no printed label; "
            "please confirm."
        )
    return None


def disagree(row: Row) -> str:
    """The request's sentence when the answer confidence counts otherwise (`AGREEING_FAMILIES`)."""
    return (
        f"Please double-check the {row.noun or row.label}: two readers count the plans differently."
    )


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


def summed_check(policy: CheckPolicy) -> tuple[Check, Level | None]:
    """The request and level on a value a schedule gives by adding up several rows, or a room's
    area read from the room schedule because the plan has no such room: never certified, since
    the schedule route was measured on single-cell lookups, not on these."""
    level = None if policy.counts is None else Level(level="low", basis="held", text=SUMMED_TEXT)
    return Check(reason=SUMMED_REASON, disputed=()), level


def _shown(row: Row, value: float) -> str:
    return str(round(value)) if row.unit == "count" else f"{value:.2f}"


def _reason(row: Row, places: int) -> str:
    what = row.noun or row.label  # "doors", "bedrooms"; "plan count" for no one class or type
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

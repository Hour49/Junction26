"""The engineer's question on one drawing: the answer_v1.1 line from the answering use case, with
the takeoff row it was looked up in (the surveyor's edits applied), or a refusal a person can read
with questions this drawing can answer.

Suggestions are built from the takeoff's rows that have a value, and a phrasing is offered only
when the parser maps it back to that row's key, so asking a suggestion is never refused.
"""

import re
from collections.abc import Callable, Iterable, Mapping, Sequence, Set
from typing import NamedTuple

from app.core.answering.answer import (
    AGREEING_FAMILIES,
    NO_DRAWING,
    NOT_IN_DRAWING,
    PRIOR_BY_POLICY,
    SCHEDULE,
    TAKEOFF,
    UNSUPPORTED_QUESTION,
    RoomByType,
    answer_question,
    counted_noun,
    noun_forms,
    partial_text,
    printed_rooms,
    rooms_of_type,
)
from app.core.answering.facts import FACTS
from app.core.answering.floors import (
    FLOOR,
    FLOOR_AT,
    floor_number,
    floor_of,
    glued,
    glued_floors,
)
from app.core.answering.model import (
    GLUED_FLOOR,
    IN_ONE_ROOM,
    NO_SUBJECT,
    NO_SUCH_FLOOR,
    NOT_COUNTED,
    SEVERAL_FLOORS,
    SEVERAL_PRINTED,
    SEVERAL_ROOMS,
    SEVERAL_THINGS,
    SHARED_FLOOR,
    Answer,
    Query,
    Question,
    TableQuery,
    Unsupported,
)
from app.core.answering.ports import AnswerConfidence, AnswerPrior, Clock, QuestionParser
from app.core.answering.tables import answer_table
from app.core.drawing.model import (
    ELEMENT_CLASSES,
    CarbonCheck,
    Drawing,
    Plan,
    Room,
    Table,
    words,
)
from app.core.ifc_facts import FactSheet
from app.core.ingest.judge import CARBON_FLAG
from app.core.model import Frozen
from app.core.pipeline import rules as rule_pack
from app.core.pipeline.model import CountingRule, Partial, Quantity
from app.core.pipeline.takeoff import (
    known_quantities,
    normalised,
    plan_counts,
    quantity_key,
    room_names,
    storeys,
)
from app.core.review.check import (
    ASK,
    LEVELS,
    NO_SCORERS,
    Check,
    CheckPolicy,
    Disputes,
    Found,
    Level,
    RoomWords,
    Scorer,
    carbon_checked,
    certified,
    disagree,
    double_check,
    found_nothing,
    held,
    level_of,
    no_disputes,
    no_room_words,
    only_room_word,
    room_word_doubt,
    room_word_refusal,
    schedule_check,
    score_of,
    summed_check,
    unmeasured_room,
)
from app.core.review.check import SCHEDULE as SCHEDULE_ROUTE
from app.core.review.model import (
    MarkView,
    Refusal,
    RefusalCode,
    ReviewState,
    Row,
    Scope,
    Suggestion,
)
from app.core.review.proof import NO_PROOF, Proof, schedule_proof, takeoff_proof
from app.core.review.review import (
    ROOM_NOUNS,
    label,
    parse_key,
    pluralise,
    row,
    storey_twins,
    with_twins,
)

# Every counting rule's text by id, as the answer shows it.
RULES: dict[str, str] = {
    found.id: found.text for found in vars(rule_pack).values() if isinstance(found, CountingRule)
}
SUGGESTIONS = 6
FACTS_LEVEL = "Low confidence: read from the file's fact sheet, not yet measured." + ASK["low"]
FACTS_REASON = (
    "Please double-check this answer against the file: it is read from its fact sheet, and such "
    "answers are not yet measured."
)
# Parser reason (question_templates.py) for a supported kind of question without that quantity
# ("no area is taken off for door"); NO_SUBJECT (answering/model.py): a subject it didn't recognise
NO_QUANTITY = re.compile(r"no (count|area|length|volume) is taken off for (\S+)")
# Plurals plain English rules don't give (a kind's id is not always the word a person uses)
PLURALS = {"living": "living rooms"}
SCHEDULE_KINDS = ("door", "window", "room")  # schedules a sheet may print, by what its rows are
NO_SCALE = ("no_scale", "not_to_scale")
ROOM_NUMBER = re.compile(r"-?U?\d+\.\d+")  # a room number the parser reads without quotes
TEXTS = {
    "unsupported-question": "This question isn't one I can turn into a count, area, length or "
    "volume. Try one of these instead.",
    # `read` is empty: the do-nothing stand-in, or a real reader that found nothing on this sheet
    "no-reader": "Nothing was read from this sheet: its reader found no elements or rooms on it.",
    # the route's extractor is the do-nothing stand-in: there is no reader to blame
    "no-reader-yet": "This sheet wasn't read, so nothing on it was counted or measured: this setup "
    "has no reader for this kind of sheet. You can still ask about the project's other drawings.",
    "no-scale": "The sheet has no scale, so lengths and areas can't be measured. Counts still "
    "work.",
    "no-drawing": "This file has no drawing model.",
    "policy": "On sheets like this one, our reader got this kind of question wrong too often when "
    "we measured it, so no number is given.",
}
PARTS = {  # an unsupported count that would drop part of the question: which part
    SEVERAL_THINGS: "This question names more than one kind of thing, and I count one kind across "
    "the whole drawing. Ask for each one on its own; try one of these.",
    IN_ONE_ROOM: "This question counts what is inside one room, and I count across the whole "
    "drawing. Try one of these instead.",
    SEVERAL_ROOMS: "This question names more than one room, and I answer for one room at a time. "
    "Ask for each room on its own.",
}


class Asked(Frozen):
    answer: Answer  # the answer_v1.1 line, as the scorer reads it
    query: str | None  # the takeoff key (or schedule query) the question became
    row: Row | None  # the takeoff row the value was read from, edits applied
    marks: tuple[MarkView, ...]  # the row's marks, or a schedule answer's cells
    refusal: Refusal | None
    proof: Proof  # what the screen draws as the answer's proof
    check: Check | None = None  # CHECK_POLICY's double-check request; None: certified or off
    # CHECK_POLICY's confidence level; None: a refusal, a value a person signed or settled, the
    # policy off, or a policy file without levels
    level: Level | None = None
    # A room total that may leave rooms out (Quantity.partial); None: not one, or a refusal
    partial: Partial | None = None


class _Once:
    """The parser, asked once per question text: the query is shown next to the answer."""

    def __init__(self, parser: QuestionParser) -> None:
        self._parser = parser
        self._seen: dict[str, Query | TableQuery | Unsupported] = {}

    def parse(self, text: str) -> Query | TableQuery | Unsupported:
        if text not in self._seen:
            self._seen[text] = self._parser.parse(text)
        return self._seen[text]


class Known(NamedTuple):
    """What `ask` looks a question up in: the drawing's takeoff after `_flagged` and `_unsaid`,
    and its rows' storey twins."""

    quantities: dict[str, Quantity]
    unread: set[str]
    unlocated: dict[str, Quantity]
    unsaid: dict[str, tuple[Room, ...]]
    twins: dict[str, str]


def known_of(drawing: Drawing, flags: Sequence[str], raster: bool) -> Known:
    """The drawing's takeoff (stages 9-10) as `ask` answers from it: the groups a flagged page's
    reader did not read and the 0 counts the drawing does not say are left out."""
    quantities, unread, unlocated = _flagged(known_quantities(drawing), drawing, flags, raster)
    unsaid = _unsaid(quantities, drawing)
    kept = {key: found for key, found in quantities.items() if key not in unsaid}
    return Known(kept, unread, unlocated, unsaid, storey_twins(kept))


def ask(
    text: str,
    drawing: Drawing,
    *,
    parser: QuestionParser,
    clock: Clock,
    prior: AnswerPrior,
    state: ReviewState,
    prior_families: Set[tuple[str, str]] = frozenset(),
    confidence: AnswerConfidence | None = None,
    sure_at: Mapping[str, float] | None = None,
    flags: Sequence[str] = (),
    raster: bool = False,
    check: CheckPolicy | None = None,
    route: str | None = None,
    disputes: Disputes = no_disputes,
    no_reader: bool = False,
    scorers: Mapping[str, Scorer] = NO_SCORERS,
    carbon_ladder: bool = False,
    room_words: RoomWords = no_room_words,
    facts: Callable[[], FactSheet | None] | None = None,
    known: Known | None = None,
) -> Asked:
    """`confidence` rates a takeoff answer as the pipeline does (DECISIONS_CONFIDENCE); its raw
    score is on the answer line only, never in the proof (it is not a calibrated probability).
    `flags`: how ingest read the page (judge.reading_flags: a phone photo, a scan). `raster`: the
    page was read on the raster route (an image, a photo, a scanned PDF). `no_reader`: the
    sheet's route has no reader (the stand-in), so a "no-reader" refusal says so, not that a
    reader found nothing. `check` (CHECK_POLICY): a takeoff answer it does not certify on `route`
    (ingest's) gets a double-check request with the places `disputes` finds; a family whose
    threshold is on a local gate's signal is scored by `scorers` (LOCAL_GATES), by signal name
    (app/core/review/check.py); a plan count also needs `confidence`'s own count to be the
    answered one (`agrees`), else it asks. With `check` on, it alone sets `sure`, in place of
    `sure_at`'s: true exactly when it certifies the answer, None on every answer it does not rate
    (a refusal, a question with no takeoff row), so an answer is never shown sure and asked
    about at once. The answer's `level` comes from the same verdict (check.level_of): High
    exactly when sure; none on a value a person signed or settled, which is theirs. With
    `carbon_ladder` (CARBON_LEVELS=ladder) a Medium answer Carbon read the same is High and asks
    nothing, yet stays not `sure`: Carbon never certifies an answer. On the raster route a count
    `room_words` doubts (check.room_word_doubt: its rooms' printed labels) is not certified
    and gets no High from Carbon either; its level is otherwise the score's, except Low on an image
    printing words of a plan kind the policy was not measured on (check.unmeasured_room). A 0
    count of a room type whose only candidates are labelled just "room" is refused
    (check.only_room_word). `facts` (IFC_FACTS; a services picture's sheet) gives the drawing's
    fact sheet, asked only when the takeoff, the schedules and the dev prior give nothing
    (answer_question): its answer is Low, never sure, marked by the facts' spots. `known`:
    `drawing`'s takeoff as `known_of` gives it for these `flags` and `raster`, when the caller has
    it already (which_room's per-room questions)."""
    if known is None:
        known = known_of(drawing, flags, raster)
    quantities, unread, unlocated, unsaid, twins = known

    def area_of(asked: str) -> Asked:  # one room's area, as this question would be answered
        return ask(
            asked, drawing, parser=parser, clock=clock, prior=prior, state=state,
            prior_families=prior_families, confidence=confidence, sure_at=sure_at, flags=flags,
            raster=raster, check=check, route=route, disputes=disputes, no_reader=no_reader,
            scorers=scorers, carbon_ladder=carbon_ladder, facts=facts, known=known,
        )  # fmt: skip

    if (compared := which_room(text, drawing, quantities, parser, area_of)) is not None:
        return compared
    once = _Once(RoomByType(parser, drawing, quantities))
    question = Question(id=1, file=drawing.file, text=text)
    tables = drawing.tables or ()
    answer = answer_question(
        question, quantities, once, clock, prior, tables, prior_families, confidence, sure_at,
        flags, facts,
    )  # fmt: skip
    parsed = once.parse(text)
    query: str | None = None
    if isinstance(parsed, Query):
        query = parsed.key()
    elif isinstance(parsed, TableQuery):
        query = parsed.family()
    found = quantities.get(query) if query is not None and answer.method == TAKEOFF else None
    shared = with_twins(state, twins)
    shown = None if found is None else row(found, drawing, shared, RULES)
    notes = [NOT_LOCATED] if found is not None and _unplaced(found, drawing) else []
    if found is not None and parse_key(found.key)[1] == "door" and CLOSET.search(text):
        notes.append(CLOSET_RULE)
    if found is not None and _in_room_opening(found.key):
        notes.append(SHARED_OPENING)
    if notes:
        said = "; ".join(note for note in (answer.explanation, *notes) if note)
        answer = answer.model_copy(update={"explanation": said})
    if shown is not None:
        marks = shown.marks
    elif answer.method in (SCHEDULE, FACTS):
        marks = tuple(
            MarkView(
                id=f"e{at}",
                n=at,
                page=item.page,
                box=item.box,
                polygon=None,
                state="counted",
                value=None,
                label=None,
                ref=None,
                reason=None,
            )
            for at, item in enumerate(answer.evidence, start=1)
        )
    else:
        marks = ()
    proof = NO_PROOF
    if shown is not None:
        proof = takeoff_proof(shown, drawing)
    elif answer.method == SCHEDULE:
        proof = schedule_proof(marks, tables, answer.answer)
    refusal = None
    if answer.method not in (TAKEOFF, SCHEDULE, FACTS):
        code, words = _refusal(answer.method, parsed, query, drawing)
        if isinstance(parsed, Query) and query is not None and _groups(query) <= unread:
            code, words = "no-reader", _unread_text(query, flags)
        elif query is not None and query in unlocated:
            code, words = "no-reader", _unlocated_text(unlocated[query], flags, drawing)
        elif query is not None and query in unsaid:
            kind = parse_key(query)[1].split(":", 1)[1]
            code, words = "not-in-drawing", room_word_refusal(kind, unsaid[query])
        if no_reader and code == "no-reader":
            words = TEXTS["no-reader-yet"]
        can_answer = suggestions(quantities, parser, SUGGESTIONS, tables)
        if code == "not-in-drawing" and isinstance(parsed, Query):
            rooms = rooms_of_type(parsed, drawing)
            if len(rooms) > 1 and (each := _room_areas(rooms, quantities, parser)):
                kind = parsed.subject.split(":", 1)[1]
                words = (
                    f"{len(rooms)} rooms on this drawing are of the type {kind}, so the question "
                    "doesn't say which one. Ask about one of them."
                )
                can_answer = each
        if (
            isinstance(parsed, Unsupported)
            and parsed.reason == SEVERAL_PRINTED
            and (named := printed_rooms(parser, drawing, text)) is not None
        ):
            # "How big is Bagno?", "How many doors does Bagno have?" with two rooms printed
            # Bagno: which one (Tudor's chat QA; fail-1, review-332 S1)
            again, rooms = named
            code = "not-in-drawing"
            words = (
                f"{len(rooms)} rooms on this drawing are printed {again.name}: "
                f"{', '.join(_room_lines(rooms, quantities))}. Which one? Ask with its number."
            )
            each = (
                _room_areas(rooms, quantities, parser)
                if again.measure == "area"
                else _room_counts(rooms, again.subject, quantities, parser)
            )
            can_answer = each or can_answer
        if isinstance(parsed, Unsupported) and parsed.reason in FLOOR_REASONS:
            # "How many toilets are on the second floor?" on a sheet that doesn't name it: which
            # floors it does name, or what each of its unnamed plans holds (fable-rooms r10 10)
            code = "not-in-drawing"
            words = _floor_text(parsed.reason, text, drawing, quantities, parser)
        if (
            isinstance(parsed, Unsupported)
            and parsed.reason in (NO_SUBJECT, NOT_COUNTED)
            and (noun := counted_noun(text)) is not None
        ):
            words = _noun_refusal(noun, drawing)  # vocab-nouns P2
        if code == "not-in-drawing" and isinstance(parsed, Query) and parsed.measure == "area":
            words += _not_measured(parsed, drawing)  # review-349 S3
        refusal = Refusal(code=code, text=words, can_answer=can_answer)
    request = None
    level = None
    sure: bool | None = None  # CHECK_POLICY's verdict
    if check is not None and shown is not None and isinstance(parsed, Query):
        reason = held(shown, drawing)
        if reason is None and found is not None and found.partial is not None:
            reason = f"Please double-check the {shown.noun or shown.label}: " + partial_text(
                found.partial
            )
        family = parsed.family()
        score = score_of(
            check, family, confidence=answer.confidence, drawing=drawing, value=answer.answer,
            scorers=scorers,
        )  # fmt: skip
        agrees = None
        if family in AGREEING_FAMILIES and confidence is not None and route == "raster":
            agrees = confidence.probability(drawing.file, family, answer.answer).agrees
        blank = found_nothing(drawing)
        doubt = room_word_doubt(shown, drawing, room_words) if route == "raster" else None
        unmeasured = shown.measure == "count" and unmeasured_room(drawing, room_words) is not None
        sure = reason is None and doubt is None and certified(
            check, route=route, family=family, score=score, flags=flags, agrees=agrees,
            blank=blank,
        )  # fmt: skip
        if shown.signed is None and shown.settled is None:
            level = level_of(
                check, sure=sure, route=route, family=family, score=score, flags=flags,
                held=reason is not None, blank=blank, unmeasured=unmeasured,
            )  # fmt: skip
            if level is not None and drawing.carbon_check is not None:
                carbon = carbon_answer(
                    question, drawing, drawing.carbon_check, parser, clock, prior, prior_families
                )
                # a disagreement the gate found (`agrees`) is not settled by Carbon agreeing
                ladder = carbon_ladder and agrees is not False and doubt is None
                level = carbon_checked(
                    level, drawing.carbon_check, carbon, answer.answer, ladder=ladder
                )
        if level is not None and found is not None and found.partial is not None:
            # a sum missing rooms is Low whatever its score, in its own words (partial totals)
            said = "Low confidence: " + partial_text(found.partial) + ASK["low"]
            level = Level(level="low", basis="held", text=said)
        if not sure and not (level is not None and level.level == "high"):
            disputed = disputes(drawing, shown)  # its own name: `found` keeps the row's partial
            if reason is None and doubt is not None:
                reason = doubt.reason
                disputed = Found(places=(*doubt.places, *disputed.places), reason=disputed.reason)
            if reason is None and agrees is False:
                reason = disagree(shown)
            request = double_check(shown, marks, disputed, reason)
    elif check is not None and answer.method == SCHEDULE and _summed(parsed, answer):
        request, level = summed_check(check)
        sure = False
    elif check is not None and answer.method == FACTS:  # not measured on any gold yet
        level = Level(level="low", basis="unrated", text=FACTS_LEVEL)
        request = Check(reason=FACTS_REASON, disputed=())  # as every Low answer: it asks
    elif check is not None and answer.method == SCHEDULE:
        request = schedule_check(check)
        sure = request is None
        level = level_of(
            check, sure=sure, route=SCHEDULE_ROUTE, family=None, score=None, flags=flags
        )
    if check is not None:
        answer = answer.model_copy(update={"sure": sure})
    return Asked(
        answer=answer,
        query=query,
        row=shown,
        marks=marks,
        refusal=refusal,
        proof=proof,
        check=request,
        level=level,
        partial=None if found is None else found.partial,
    )


def carbon_answer(
    question: Question,
    drawing: Drawing,
    check: CarbonCheck,
    parser: QuestionParser,
    clock: Clock,
    prior: AnswerPrior,
    prior_families: Set[tuple[str, str]],
) -> int | float | str | None:
    """Carbon's answer to the question (CARBON_LEVELS): its reading on the drawing's pages and
    scale, answered as the drawing's own reading is (the same parser, prior and answer policy,
    as integ's test answered both). None: it refuses (a class it did not count, a scope it has
    no plan for), which changes nothing."""
    seen = Drawing(
        file=drawing.file,
        pages=drawing.pages,
        scale=drawing.scale,
        plans=check.plans,
        elements=check.elements,
        rooms=check.rooms,
        read=check.read,
    )
    quantities = known_quantities(seen)
    once = _Once(RoomByType(parser, seen, quantities))
    found = answer_question(question, quantities, once, clock, prior, (), prior_families)
    return found.answer


def _summed(parsed: object, answer: Answer) -> bool:
    """A schedule answer outside the single-cell lookups the schedule route was measured on: a
    room's area the room schedule gives for a takeoff question (answering's fallback), or a sum
    over more than one row."""
    if isinstance(parsed, Query):
        return True
    summing = isinstance(parsed, TableQuery) and parsed.op in ("sum", "count_sum")
    return summing and len(answer.evidence) > 1


def _flagged(
    quantities: Mapping[str, Quantity], drawing: Drawing, flags: Sequence[str], raster: bool
) -> tuple[dict[str, Quantity], set[str], dict[str, Quantity]]:
    """On a page ingest flagged (a phone photo, a scan), a group its reader found nothing of
    (no element at all, no room at all) is unknown, not 0: its keys are left out and the group
    is returned as `unread`, so any question on it is refused, its key in the takeoff or not
    (F4-4b). Every other quantity carries the flag as its estimate, so the answer says what it
    rests on (R3-qa4-1). On any raster page, flagged or not, no room at all is unread too: a
    page can have 0 saunas, but not 0 rooms (F4-4). Except a class Carbon counted: Carbon names
    the classes it could not count (left out of `read`), so on a drawing whose elements are
    Carbon's (CARBON_FLAG, which ingest sets only then) a class it read with no element is a
    read 0, still flagged (brief r8 BD). A drawing Carbon read only a part of keeps F4-4b.
    On a flagged page a room count with no located mark ("0 bathrooms", "37 bedrooms" with
    nothing marked) is a guess too: it is left out and returned in `unlocated` by key, so the
    question is refused the same way (brief r8 BM); a class Carbon read keeps its 0. A 0 of a
    room type has nothing to mark, so it is a read 0 when the reader told room types apart (two
    or more types besides "other": a page can have 0 saunas, F4-4) and a guess when it put every
    room under one type (the hotel photo: 37 "bedrooms", then 0 bathrooms; #285 review)."""
    empty: set[str] = set()
    if flags and not drawing.elements:
        empty.update(ELEMENT_CLASSES)
        if CARBON_FLAG in flags and drawing.read is not None:
            empty.difference_update(drawing.read)
    if (flags or raster) and not drawing.rooms:
        empty.add("room")
    if not flags and not empty:
        return dict(quantities), set(), {}
    carbon: set[str] = set(drawing.read or ()) if CARBON_FLAG in flags else set()
    kept: dict[str, Quantity] = {}
    unlocated: dict[str, Quantity] = {}
    told = len(_types(drawing)) >= 2
    note = f"read from a page flagged at upload: {'; '.join(flags)}"
    for key, found in quantities.items():
        if _groups(key) <= empty:
            continue
        if not flags:
            kept[key] = found
            continue
        guess = found.value > 0 or not told
        if _room_count(found) and not found.marks and guess and not _groups(key) <= carbon:
            unlocated[key] = found
            continue
        said = note if found.estimate is None else f"{found.estimate}; {note}"
        kept[key] = found.model_copy(update={"estimate": said})
    return kept, empty, unlocated


def _unsaid(quantities: Mapping[str, Quantity], drawing: Drawing) -> dict[str, tuple[Room, ...]]:
    """The 0 counts of a room type the drawing does not say (check.only_room_word), by key, with
    the rooms that are why: the question is refused, not answered 0."""
    found: dict[str, tuple[Room, ...]] = {}
    for key, quantity in quantities.items():
        measure, subject = parse_key(key)[:2]
        if measure != "count" or not subject.startswith("room:") or quantity.value != 0:
            continue
        if rooms := only_room_word(subject.split(":", 1)[1], drawing):
            found[key] = rooms
    return found


def _groups(key: str) -> set[str]:
    """The groups a quantity key rests on: "area:room|indoor" -> {"room"}, "door+window" ->
    {"door", "window"}."""
    return {part.split(":", 1)[0] for part in parse_key(key)[1].split("+")}


def _unread_text(query: str, flags: Sequence[str]) -> str:
    if not flags:  # only rooms are unread on a page that wasn't flagged (_flagged)
        return "No rooms were read on this drawing, so 0 would be a guess, not a count."
    things = "rooms" if parse_key(query)[1].startswith("room") else "elements"
    return (
        f"This drawing was flagged at upload ({'; '.join(flags)}), and its reader found no "
        f"{things} on it, so 0 would be a guess, not a count."
    )


NOT_LOCATED = "not located on the drawing"
# Which room is the largest or smallest, or the larger of two rooms named: a room's name, from the
# rooms' areas (judge-fresh §10: 5 of 23 refusals)
# Anchored at both ends: "Which room has the largest window?" or "What is the largest room's
# area?" are other questions (review-368 M1)
WHICH_EXTREME = re.compile(
    r"^\s*(?:which|what)\s+(?:(?:room|space)\s+(?:is|has)\s+(?:the\s+)?(?P<a>largest|biggest|smallest)"
    r"(?:\s+(?:one|(?:floor\s+)?area|size))?|is\s+the\s+(?P<b>largest|biggest|smallest)\s+(?:room|space))"
    r"\s*[?.!]?\s*$",
    re.IGNORECASE,
)
WHICH_OF_TWO = re.compile(
    r"^\s*which\s+(?:room\s+|one\s+)?is\s+(?P<more>larger|bigger|smaller)\s*[,:]?\s*(?:the\s+)?"
    r"(?P<x>.+?)\s+or\s+(?:the\s+)?(?P<y>.+?)\s*\??\s*$",
    re.IGNORECASE,
)
SCHEDULE_WORD = re.compile(r"\bschedule\b", re.IGNORECASE)  # a schedule's rows: its own path


def which_room(
    text: str,
    drawing: Drawing,
    quantities: Mapping[str, Quantity],
    parser: QuestionParser,
    area_of: Callable[[str], Asked],
) -> Asked | None:
    """ "Which room is the largest?", "Which is the biggest room?" (the drawing's indoor rooms) and
    "Which is larger, the X or the Y?": the room's name, from each room's area as its own area
    question answers it (`area_of`: its value, refusal, level and marks). The level is the
    weakest of the areas compared, never higher than any of them. Refused when an area it needs
    is refused, when a room has no area question, when both rooms named are one room, or when
    the first two areas lie within each other's estimate band (`Room.area_uncertainty`). None:
    not such a question."""
    if SCHEDULE_WORD.search(text):
        return None
    rooms = [room for room in drawing.rooms if not room.outdoor]
    if (two := WHICH_OF_TWO.match(text)) is not None:
        word = two["more"].casefold()
        asks = [(two[side], f"What is the area of the {two[side]}?") for side in ("x", "y")]
    elif (extreme := WHICH_EXTREME.match(text)) is not None:
        word = (extreme["a"] or extreme["b"]).casefold()
        asks, left = _extreme_asks(rooms, quantities, parser, largest=word != "smallest")
        if left or len(asks) < 2:
            return _not_compared(f"I can't tell which room is the {word}: {_left_why(left, asks)}.")
    else:
        return None
    got: dict[str | None, tuple[str, Asked]] = {}  # by the row it reads: one room counted once
    for name, question in asks:
        found = area_of(question)
        if found.refusal is not None or not isinstance(found.answer.answer, int | float):
            why = found.refusal.text if found.refusal is not None else "it has no area"
            return _not_compared(
                f"I can't tell which is {word}: the area of {name} isn't known. {why}", found
            )
        got.setdefault(found.query, (_named(found, drawing) or name, found))
    if two is not None and len(got) == 1:
        ((name, found),) = got.values()
        return _not_compared(
            f"I can't tell which is {word}: the {two['x']} and the {two['y']} both read as "
            f"{name}, so I can't find them as two rooms.", found
        )  # fmt: skip
    ordered = sorted(
        got.values(), key=lambda pair: float(pair[1].answer.answer or 0),
        reverse=word != "smaller" and word != "smallest",
    )  # fmt: skip
    (first_name, first), (second_name, second) = ordered[0], ordered[1]
    a, b = float(first.answer.answer or 0), float(second.answer.answer or 0)
    ua, ub = _band(first, drawing), _band(second, drawing)
    big, small = (a, b) if a >= b else (b, a)
    u_big, u_small = (ua, ub) if a >= b else (ub, ua)
    if big * (1 - u_big) <= small * (1 + u_small):
        return _not_compared(
            f"I can't tell which is {word}: {first_name} ({_m2(first)}) and {second_name} "
            f"({_m2(second)}) are within each other's estimate band, so either could be.",
            first,
        )
    if two is not None:
        said = f"{first_name} ({_m2(first)}) is {word} than {second_name} ({_m2(second)})"
    else:
        said = (
            f"{first_name} ({_m2(first)}) is the {word} of the {len(rooms)} rooms; next is "
            f"{second_name} ({_m2(second)})"
        )
    compared = [found for _, found in ordered]
    levels = [found.level for found in compared]
    level = None if any(lv is None for lv in levels) else min(
        (lv for lv in levels if lv is not None), key=lambda lv: LEVELS.index(lv.level)
    )  # fmt: skip
    sures = [found.answer.sure for found in compared]
    sure = None if all(s is None for s in sures) else all(s is True for s in sures)
    estimate = any(found.answer.estimate for found in compared) or None
    why = "; ".join(e for e in (said, first.answer.explanation) if e)
    answer = first.answer.model_copy(
        update={"answer": first_name, "unit": None, "explanation": why, "sure": sure,
                "estimate": estimate, "confidence": None}
    )  # fmt: skip
    checks = [found.check for found in compared if found.check is not None]
    return Asked(
        answer=answer, query=None, row=None, marks=first.marks, refusal=None, proof=first.proof,
        check=checks[0] if checks else None, level=level,
    )  # fmt: skip


def _extreme_asks(
    rooms: Sequence[Room],
    quantities: Mapping[str, Quantity],
    parser: QuestionParser,
    largest: bool,
) -> tuple[list[tuple[str, str]], list[Room]]:
    """The area question of each room, by its own name; for the largest, a room no name gives
    alone is asked as the largest room of its printed label, else of its type (that row's room is
    a candidate too). The rooms no question reaches are returned as left."""
    asks: list[tuple[str, str]] = []
    left: list[Room] = []
    for room in rooms:
        if each := _room_areas([room], quantities, parser):
            asks.append((_shown(room), each[0].question))
            continue
        texts = (
            [f"What is the area of the largest room labelled '{' '.join(room.label.split())}'?"]
            if room.label
            else [f"What is the area of the largest {_noun(room)}?"]
        ) if largest else []  # fmt: skip
        found = next((t for t in texts if _key(parser, t) in quantities), None)
        if found is None:
            left.append(room)
        elif found not in (question for _, question in asks):
            asks.append((_shown(room), found))
    return asks, left


def _key(parser: QuestionParser, text: str) -> str | None:
    parsed = parser.parse(text)
    return parsed.key() if isinstance(parsed, Query) else None


def _left_why(left: Sequence[Room], asks: Sequence[tuple[str, str]]) -> str:
    if not left:
        return f"this drawing has {len(asks)} room{'' if len(asks) == 1 else 's'} to compare"
    named = ", ".join(_shown(room) for room in left[:4])
    if all(room.area_m2 is None for room in left):
        return f"{len(left)} of its rooms ({named}) have no area measured"
    return f"{len(left)} of its rooms ({named}) have no name or number to ask their area by"


def _named(found: Asked, drawing: Drawing) -> str | None:
    """The one room an area answer's marks point at, as the answer names it."""
    refs = {mark.ref for mark in found.marks}
    rooms = [room for room in drawing.rooms if room.id in refs]
    return _shown(rooms[0]) if len(rooms) == 1 else None


def _shown(room: Room) -> str:
    """A room as the answer names it: its printed label on one line, and its number."""
    number = room.attrs.get("number")
    parts = [" ".join(str(part).split()) for part in (room.label, number) if part]
    return " ".join(parts) or f"the unlabelled {_noun(room)}"


def _noun(room: Room) -> str:
    return ROOM_NOUNS.get(room.type, words(room.type))


def _m2(asked: Asked) -> str:
    value = float(asked.answer.answer or 0)
    return f"{round(value)} m²" if asked.answer.estimate else f"{value:.2f} m²"


def _band(asked: Asked, drawing: Drawing) -> float:
    """How far off the area of the room an area answer names may be (its relative estimate band;
    0 for a printed or measured area)."""
    refs = {mark.ref for mark in asked.marks}
    rooms = [room for room in drawing.rooms if room.id in refs]
    return max((room.area_uncertainty or 0.0 for room in rooms), default=0.0)


def _not_compared(why: str, asked: Asked | None = None) -> Asked:
    """A comparison refused, with why."""
    base = Answer(
        id=1, answer=None, unit=None, evidence=(), method=NOT_IN_DRAWING,
        cost_usd=0.0, latency_s=0.0, abstain=True, explanation=why,
    )  # fmt: skip
    line = base if asked is None else asked.answer.model_copy(
        update={"answer": None, "unit": None, "method": NOT_IN_DRAWING,
                "abstain": True, "explanation": why, "sure": None}
    )  # fmt: skip
    can = () if asked is None or asked.refusal is None else asked.refusal.can_answer
    return Asked(
        answer=line, query=None, row=None, marks=(), refusal=Refusal(
            code="not-in-drawing", text=why, can_answer=can
        ), proof=NO_PROOF,
    )  # fmt: skip


# "How many doors are there, including closet doors?": the door count's rule, said once (Stoa
# counts closet doors as doors; brief r8 BM)
CLOSET = re.compile(r"\bcloset", re.IGNORECASE)
CLOSET_RULE = "closet doors are counted as doors"
# fail-1, review-332 N1: rooms' door counts add up to more than the sheet's
SHARED_OPENING = "a door or window in a wall between two rooms counts for both rooms"


def _in_room_opening(key: str) -> bool:
    """A count of doors or windows in one room (`door|name=1.01`)."""
    _, subject, scope = parse_key(key)
    return scope.name is not None and bool({"door", "window"} & set(subject.split("+")))


def _room_count(found: Quantity) -> bool:
    """A count of rooms (of a type or all): element counts keep a read 0 (R3-qa4-1)."""
    return found.unit == "count" and _groups(found.key) == {"room"}


def _unplaced(found: Quantity, drawing: Drawing) -> bool:
    """A count of something on a drawing with pages that marks none of it: its value can't be
    checked on the drawing, so the answer says so next to it (brief r8 BM)."""
    return bool(drawing.pages) and found.unit == "count" and found.value > 0 and not found.marks


def _types(drawing: Drawing) -> set[str]:
    """The room types the reader told apart ("other" is no type)."""
    return {room.type for room in drawing.rooms if room.type != "other"}


def _unlocated_text(found: Quantity, flags: Sequence[str], drawing: Drawing) -> str:
    flagged = f"This drawing was flagged at upload ({'; '.join(flags)})"
    if found.value == 0:
        types = _types(drawing)
        why = (
            f"read every room as a {words(next(iter(types)))}"
            if types
            else "did not tell room types apart"
        )
        return f"{flagged}, and its reader {why}, so 0 would be a guess, not a count."
    return (
        f"{flagged}, and none of what its reader counted here is located on it, so "
        f"{found.value:g} would be a guess, not a count."
    )


def suggestions(
    quantities: Mapping[str, Quantity],
    parser: QuestionParser,
    limit: int,
    tables: Sequence[Table] = (),
) -> tuple[Suggestion, ...]:
    """Up to `limit` questions the parser maps to a row with a value (or to a schedule the sheet
    prints): schedules first, then areas, lengths and volumes, then counts, so a sheet offers
    more than counts."""
    found: list[Suggestion] = list(_schedule_suggestions(parser, tables))[:limit]
    order = sorted(quantities, key=lambda key: parse_key(key)[0] == "count")  # stable
    for key in order:
        if len(found) == limit:
            break
        if quantities[key].value == 0:
            continue
        for text in _phrasings(key):
            parsed = parser.parse(text)
            if isinstance(parsed, Query) and parsed.key() == key:
                found.append(Suggestion(quantity=key, label=label(key), question=text))
                break
    return tuple(found)


FLOOR_REASONS = (NO_SUCH_FLOOR, SEVERAL_FLOORS, SHARED_FLOOR, GLUED_FLOOR)


def _floor_text(
    reason: str,
    text: str,
    drawing: Drawing,
    quantities: Mapping[str, Quantity],
    parser: QuestionParser,
) -> str:
    """Why a floor named in words can't be answered on this drawing (RoomByType._floor), in
    words: the storeys that could be meant, the ones it has, or, on a sheet of several plans none
    of which names its floor or several of which carry the floor, how many of the counted thing
    each plan holds."""
    found = FLOOR.search(text)
    asked = "floor" if found is None else found.group().casefold()
    number = None if found is None else floor_number(found)
    named = storeys(drawing)
    if reason == GLUED_FLOOR and found is not None and number is not None:
        n = abs(number)
        if glued(found):
            word = found.group().split("-")[0]
            return (
                f'"{found.group()}" could be {word} {n} or {word} -{n} (below ground), so I can\'t '
                f'tell which is meant. Ask for "{word} {n}" or "{word} -{n}".'
            )
        same = [storey for storey in named if number in glued_floors(storey)]
        return (
            f"This drawing's storey {same[0]} could be floor {n} or floor -{n} (below ground), so "
            f"I can't tell if it is the {asked}. Ask with the storey's name in quotes, as in "
            f"\"How many doors are on '{same[0]}'?\""
        )
    if reason == SEVERAL_FLOORS:
        same = [storey for storey in named if floor_of(storey) == number]
        return (
            f"Several storeys of this drawing could be the {asked}: {', '.join(same)}. Ask with "
            f"the storey's name in quotes, as in \"How many doors are on '{same[0]}'?\""
        )
    if reason == SHARED_FLOOR:
        storey = next(storey for storey in named if floor_of(storey) == number)
        shared = [plan for plan in drawing.plans if str(plan.storey) == storey]
        words = (
            f"{len(shared)} plans on this drawing are labelled {storey}, so I can't tell which "
            "one is meant, and I don't add them up: they may be alternatives or parts of the floor."
        )
        each = _per_plan(text, drawing, quantities, parser, shared, total=False)
        return words if each is None else f"{words} {each}"
    if named and all(floor_of(storey) is not None for storey in named):
        return f"This drawing's storeys are {', '.join(named)}; none of them is the {asked}."
    if named:  # "Erdgeschoss", "1. Obergeschoss": names it can't read as floor numbers (S3)
        return (
            f"This drawing's storeys are {', '.join(named)}; I can't tell which of them is the "
            f"{asked}. Ask with the storey's name in quotes, as in \"How many doors are on "
            f"'{named[0]}'?\""
        )
    if len(drawing.plans) < 2:
        return (
            f"This drawing doesn't say which floor it shows, so I can't tell if it is the {asked}."
        )
    words = (
        f"This drawing has {len(drawing.plans)} plans and none is labelled with its floor, so I "
        f"can't tell which one is the {asked}."
    )
    each = _per_plan(text, drawing, quantities, parser, drawing.plans, total=True)
    return words if each is None else f"{words} {each}"


def _per_plan(
    text: str,
    drawing: Drawing,
    quantities: Mapping[str, Quantity],
    parser: QuestionParser,
    plans: Sequence[Plan],
    *,
    total: bool,
) -> str | None:
    """How many of the thing the question counts (its floor left out) each of `plans` holds,
    numbered as the drawing lists its plans; with `total`, the sheet's total and what lies
    outside every plan, so the parts add up. None when the question is not a count the sheet
    has."""
    rest = parser.parse(FLOOR_AT.sub(" ", text))
    if not isinstance(rest, Query) or rest.measure != "count" or rest.key() not in quantities:
        return None
    counted = {plan.id: n for plan, n in plan_counts(drawing, rest.key())}
    if not counted:
        return None
    pages = len(drawing.pages) > 1
    lines = [
        f"plan {at} ({_where(plan, pages)}) {counted[plan.id]}"
        for at, plan in enumerate(drawing.plans, 1)
        if plan in plans
    ]
    kind = parse_key(rest.key())[1].removeprefix("room:")
    said = f"{plural(kind).capitalize()} on each: {', '.join(lines)}"
    if not total:
        return f"{said}."
    whole = int(quantities[rest.key()].value)
    if (outside := whole - sum(counted.values())) > 0:
        said += f", {outside} outside every plan"
    return f"{said}; {whole} in all."


def _where(plan: Plan, pages: bool) -> str:
    """Where a plan is drawn, in words: top left, bottom, middle (and its page)."""
    x0, y0, x1, y1 = plan.box
    x, y = (x0 + x1) / 2, (y0 + y1) / 2
    across = "left" if x < 0.4 else "right" if x > 0.6 else ""
    down = "top" if y < 0.4 else "bottom" if y > 0.6 else ""
    place = " ".join(word for word in (down, across) if word) or "middle"
    return f"{place} of page {plan.page}" if pages else place


def _room_lines(rooms: Sequence[Room], quantities: Mapping[str, Quantity]) -> list[str]:
    """Each room as "Bagno 1.01 7.56 m²": its printed label, its number, and the area of its row
    (by the first of its names the takeoff has one for) when it has one."""
    lines: list[str] = []
    for room in rooms:
        keys = (quantity_key("area", "room", name=name) for name in room_names(room))
        found = next((quantities[key] for key in keys if key in quantities), None)
        number = room.attrs.get("number")
        name = " ".join(" ".join(str(part).split()) for part in (room.label, number) if part)
        lines.append(name if found is None else f"{name} {found.value:.2f} m²")
    return lines


def _room_counts(
    rooms: Sequence[Room], subject: str, quantities: Mapping[str, Quantity], parser: QuestionParser
) -> tuple[Suggestion, ...]:
    """The count question of `subject` in each room, by one of its names, that the parser maps
    back to a row."""
    found: list[Suggestion] = []
    for room in rooms:
        for name in sorted(room_names(room)):
            if not ROOM_NUMBER.fullmatch(name):
                continue
            text = f"How many {plural(subject)} are in room {name}?"
            parsed = parser.parse(text)
            if isinstance(parsed, Query) and parsed.key() in quantities:
                found.append(
                    Suggestion(quantity=parsed.key(), label=label(parsed.key()), question=text)
                )
                break
    return tuple(found)


def _room_areas(
    rooms: Sequence[Room], quantities: Mapping[str, Quantity], parser: QuestionParser
) -> tuple[Suggestion, ...]:
    """The area question of each room, by one of its names, that the parser maps back to a row
    with a value."""
    found: list[Suggestion] = []
    for room in rooms:
        for name in sorted(room_names(room)):
            noun = name if ROOM_NUMBER.fullmatch(name) else f"'{name}'"
            text = f"What is the net floor area of room {noun}?"
            parsed = parser.parse(text)
            if isinstance(parsed, Query) and parsed.key() in quantities:
                found.append(
                    Suggestion(quantity=parsed.key(), label=label(parsed.key()), question=text)
                )
                break
    return tuple(found)


def _schedule_suggestions(parser: QuestionParser, tables: Sequence[Table]) -> Iterable[Suggestion]:
    """A count of each kind of schedule the sheet prints, when it resolves on one table."""
    for kind in SCHEDULE_KINDS:
        text = f"How many {plural(kind)} are listed in the {kind} schedule?"
        parsed = parser.parse(text)
        if isinstance(parsed, TableQuery) and answer_table(parsed, tables) is not None:
            name = f"{plural(kind)} in the {kind} schedule"
            yield Suggestion(quantity=parsed.family(), label=name, question=text)


def plural(kind: str) -> str:
    """The English plural of a kind of element or room ("balcony" → "balconies")."""
    if kind in PLURALS:
        return PLURALS[kind]
    return pluralise(words(kind))


def _phrasings(key: str) -> Iterable[str]:
    measure, subject, scope = parse_key(key)
    if scope == Scope(model=True):  # the building model's own total
        if measure == "count" and subject in ELEMENT_CLASSES:
            yield f"How many {plural(subject)} are there in the building model?"
        elif measure == "count" and subject == "room":
            yield "How many rooms are there in the building model?"
        elif (measure, subject) == ("volume", "slab"):
            yield "What is the total volume of all floor slabs in the building model?"
        elif (measure, subject) == ("length", "wall"):
            yield "What is the total length of all walls in the building model?"
        return
    if scope != type(scope)():  # filtered rows (a storey, a room's name...) get no suggestion
        if measure == "area" and subject == "room" and scope.indoor and not scope.model:
            yield "What is the net floor area of all indoor rooms in m²?"
            yield "What is the total indoor floor area?"
            yield "What is the indoor area of this floor?"
        return
    if measure == "count":
        if subject in ELEMENT_CLASSES or subject in ("room", "apartment"):
            things = plural(subject)
        elif subject.startswith("room:"):
            things = plural(subject.split(":", 1)[1])
        else:
            return
        yield f"How many {things} are there?"
        yield f"How many {things} are on this plan?"
    elif measure == "area" and subject == "room":
        yield "What is the total floor area?"
        yield "What is the total area of all rooms?"


LABELS_LISTED = 12  # printed labels a refusal names, the rest counted


def _noun_refusal(noun: str, drawing: Drawing) -> str:
    """A count of a thing no reader counts (vocab-nouns P2): says the noun, and the labels the
    drawing does print, so the person can ask by one of them. A noun that is one room's whole
    printed label points at the count of that label instead: a plain noun is not taken as a
    label (vocab-nouns line 3 failed: 5 of 16 right on the held-out sheets)."""
    forms = noun_forms(noun)
    printed = dict.fromkeys(
        " ".join(r.label.split()) for r in drawing.rooms if r.label and normalised(r.label) in forms
    )
    if printed:
        label = next(iter(printed))
        return (
            f"I don't count {noun} by that word: they are not one of the things the readers count "
            "(doors, windows, toilets, sinks, showers, bathtubs, sauna stoves and rooms). Rooms "
            f"on this drawing are printed {label}: ask \"How many rooms labelled '{label}' are "
            'there?"'
        )
    words = (
        f"I don't count {noun}: they are not one of the things the readers count (doors, "
        "windows, toilets, sinks, showers, bathtubs, sauna stoves and rooms), and no room on this "
        f"drawing is printed {noun}."
    )
    labels = list(dict.fromkeys(" ".join(r.label.split()) for r in drawing.rooms if r.label))
    if not labels:
        return f"{words} No room on this drawing has a printed name."
    shown = ", ".join(labels[:LABELS_LISTED])
    more = f" and {len(labels) - LABELS_LISTED} more" if len(labels) > LABELS_LISTED else ""
    return f"{words} Rooms printed here: {shown}{more}."


def _not_measured(parsed: Query, drawing: Drawing) -> str:
    """Why the one room a question names has no area, from the drawing's note on it ("room
    area: r3 not measured, <why>"; raster_scale's REFUSED_NOTE), or nothing."""
    if parsed.name is None:
        return ""
    rooms = [room for room in drawing.rooms if normalised(parsed.name) in room_names(room)]
    if len(rooms) != 1:
        return ""
    start = f"room area: {rooms[0].id} not measured, "
    why = next((note[len(start) :] for note in drawing.notes if note.startswith(start)), None)
    return "" if why is None else f" Not measured: {why}."


def _unknown_subject(reason: str) -> str | None:
    """The words for a question of a kind the takeoff answers (a count, area, length or volume)
    whose room or element wasn't recognised, or that has no such quantity (R3-qa-1-1): saying the
    kind is unsupported would be false."""
    if reason == NO_SUBJECT:
        return (
            "I can see what this asks to measure, but not which room or element it is about. "
            "Name a room type (kitchen, sauna...), a room label printed on the drawing, a room "
            "number, or an element (doors, windows...). Try one of these instead."
        )
    if found := NO_QUANTITY.fullmatch(reason):
        measure, subject = found.groups()
        kind = subject.split(":", 1)[-1]
        things = plural(kind) if not kind.endswith("s") else words(kind)
        return f"The takeoff has no {measure} for {things}. Try one of these instead."
    return None


def _refusal(
    method: str,
    parsed: Query | TableQuery | Unsupported,
    query: str | None,
    drawing: Drawing,
) -> tuple[RefusalCode, str]:
    if method == NO_DRAWING:
        return "no-drawing", TEXTS["no-drawing"]
    if method == PRIOR_BY_POLICY:  # measured, but that reader loses to a guess on this family
        return "no-reader", TEXTS["policy"]
    if method == UNSUPPORTED_QUESTION or not isinstance(parsed, Query) or query is None:
        if isinstance(parsed, TableQuery):
            return "not-in-drawing", "No schedule on this sheet answers this question."
        if isinstance(parsed, Unsupported) and parsed.reason in PARTS:
            return "unsupported-question", PARTS[parsed.reason]
        if isinstance(parsed, Unsupported) and (words := _unknown_subject(parsed.reason)):
            return "unsupported-question", words
        return "unsupported-question", TEXTS["unsupported-question"]
    if drawing.read == () and not drawing.model_objects:
        return "no-reader", TEXTS["no-reader"]
    if parsed.measure in ("area", "length") and drawing.scale.status in NO_SCALE:
        return "no-scale", TEXTS["no-scale"]
    looked_for = drawing.read
    wanted = {part.split(":", 1)[0] for part in parsed.subject.split("+")}
    missing = sorted(
        name for name in wanted if name in (*ELEMENT_CLASSES, "room") and looked_for is not None
        and name not in looked_for
    )  # fmt: skip
    if missing:
        return (
            "not-read",
            f"The reader of this drawing doesn't look for {', '.join(missing)}, so it has no "
            f"{label(query, drawing)}.",
        )
    if parsed.measure == "count" and parsed.name is not None:  # what is inside one room
        rooms = [room for room in drawing.rooms if normalised(parsed.name) in room_names(room)]
        if not rooms:
            return "not-in-drawing", f"No room on this drawing is numbered or named {parsed.name}."
        if len(rooms) > 1:
            return (
                "not-in-drawing",
                f"{len(rooms)} rooms on this drawing are named {parsed.name}, so the question "
                "doesn't say which one.",
            )
        if rooms[0].polygon is None:
            return (
                "not-in-drawing",
                f"Room {parsed.name} has no outline on this drawing, only a box around it, so I "
                "can't tell what is inside it.",
            )
    return "not-in-drawing", f"This drawing doesn't give the {label(query, drawing)}."

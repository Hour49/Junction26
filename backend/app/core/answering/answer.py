"""The answering use cases: one question (the API) and a batch of them (the CLI)."""

import functools
import itertools
import logging
import math
import re
from collections import Counter
from collections.abc import Callable, Iterable, Mapping, Sequence, Set

from app.core.answering.facts import FactSource, answer_from_facts
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
    NO_SUBJECT,
    NO_SUCH_FLOOR,
    NO_SUCH_STOREY,
    SEVERAL_FLOORS,
    SEVERAL_PRINTED,
    SHARED_FLOOR,
    UNQUOTED_PLACE,
    Answer,
    ConflictValue,
    Evidence,
    Query,
    Question,
    TableFilter,
    TableQuery,
    Unsupported,
    source_of,
)
from app.core.answering.ports import (
    AnswerConfidence,
    AnswerPrior,
    AnswerSink,
    Clock,
    DrawingSource,
    QuestionParser,
)
from app.core.answering.tables import TableAnswer, answer_table, why_none
from app.core.drawing.model import Drawing, Room, Table
from app.core.ifc_facts import FactSheet
from app.core.pipeline.model import Partial, Quantity
from app.core.pipeline.second_count import METHODS
from app.core.pipeline.takeoff import known_quantities, normalised, room_names, storeys

logger = logging.getLogger(__name__)

# `method` of an answer: how it was answered, or "refused:<why>" (the reason in words goes in
# answer_v1.1 `explanation`).
TAKEOFF = "takeoff"
SCHEDULE = "schedule"  # read from a schedule printed on the sheet (Drawing.tables)
NO_DRAWING = "refused:no-drawing"
UNSUPPORTED_QUESTION = "refused:unsupported-question"
NOT_IN_DRAWING = "refused:not-in-drawing"
PRIOR_BY_POLICY = "prior:policy"  # the answer policy sends this family to the prior
POLICY_WHY = "raster reader below prior on val for this family"
# Families whose answer is sure only when the confidence signal's own most likely value is the
# answered one (two independent readers agree), whatever the score. Plans on page: the gate
# certified every val plan answer (threshold 0.014), and hand-drawn sketches got sure, wrong plan
# counts where Gemini's own count differed (.agents/exp/handdrawn.md; answer-next, 2026-11-14).
AGREEING_FAMILIES = frozenset({"plan"})


def answer_question(
    question: Question,
    quantities: Mapping[str, Quantity] | None,
    parser: QuestionParser,
    clock: Clock,
    prior: AnswerPrior,
    tables: Sequence[Table] = (),
    prior_families: Set[tuple[str, str]] = frozenset(),
    confidence: AnswerConfidence | None = None,
    sure_at: Mapping[str, float] | None = None,
    flags: Sequence[str] = (),
    facts: Callable[[], FactSheet | None] | None = None,
) -> Answer:
    """`quantities` is the takeoff of the question's drawing (`known_quantities`), or None when
    the file has no drawing model; `tables` the schedules it prints. `prior_families` holds the
    (source, family) pairs the answer policy (ANSWER_POLICY) answers from the prior although
    the drawing gives a value: abstaining, with the prior's value, when the prior has one. A
    refusal has the reason in `method`, `abstain` true and the reason in words in `explanation`
    (answer_v1.1). Its `answer` is the prior's value for the question's family when there is one
    (with the prior's `confidence`), else None. With `confidence` (DECISIONS_CONFIDENCE), a
    takeoff answer gets its probability as `confidence`; when there is none, the reason is
    logged, never added to the answer. `sure_at` (GATE_POLICY: family -> threshold on that
    confidence's signal) sets `sure`: true at or above the family's threshold, false below it,
    None without a probability or for a family it doesn't gate; for a family in
    `AGREEING_FAMILIES` also false when the signal's own value is another (`agrees`). `flags`:
    how ingest read the page (judge.reading_flags: a phone photo, a scan); on a flagged page
    `sure` is None, since the gate was certified on CubiCasa scans, not on photos
    (orchestrator, 2026-11-14 O1). `facts`: gets the fact sheet of the question's file
    (IFC_FACTS), called only when the takeoff, the schedules and the prior give nothing
    (answering/facts.py), so a sheet no question needs is never built."""
    start = clock()
    parsed = parser.parse(question.text)
    read = _read(parsed)
    found: Quantity | None = None
    if quantities is None:
        method, why = NO_DRAWING, "the file has no drawing model"
    elif isinstance(parsed, Unsupported):
        method, why = UNSUPPORTED_QUESTION, parsed.reason
    elif isinstance(parsed, TableQuery):
        if (row := answer_table(parsed, tables)) is not None:
            return read(_from_table(question, row, clock() - start))
        method = NOT_IN_DRAWING
        why = why_none(parsed, tables) or f"no schedule on the sheet resolves {parsed.family()}"
    else:
        found = quantities.get(parsed.key())
        scheduled = None if found is not None else _scheduled_room(parsed)
        if scheduled is not None and (row := answer_table(scheduled, tables)) is not None:
            return read(_from_table(question, row, clock() - start))
        method = NOT_IN_DRAWING if found is None else TAKEOFF
        why = f"the drawing model does not give {parsed.key()}"
        if scheduled is not None and (said := why_none(scheduled, tables)) is not None:
            why = f"{why}, and {said}"
        source, family = source_of(question.file), parsed.family()
        if (source, family) in prior_families and (
            estimate := prior.prior(source, family)
        ) is not None:
            return read(
                Answer(
                    id=question.id,
                    answer=estimate.value,
                    unit=estimate.unit,
                    evidence=(),
                    method=PRIOR_BY_POLICY,
                    cost_usd=0.0,
                    latency_s=clock() - start,
                    confidence=estimate.confidence,
                    abstain=True,
                    explanation=POLICY_WHY,
                )
            )
    if found is not None:
        answer = _from_takeoff(question, found, method, clock() - start)
        if confidence is None or isinstance(parsed, Unsupported | TableQuery):
            return read(answer)
        rated = confidence.probability(question.file, parsed.family(), answer.answer)
        sure = _sure(sure_at, parsed.family(), rated.value, flags, rated.agrees)
        if rated.value is None:  # why goes to the log: nothing a reader of the answer can act on
            logger.info("question %d: no confidence: %s", question.id, rated.note)
            return read(answer.model_copy(update={"sure": sure}))
        return read(answer.model_copy(update={"confidence": rated.value, "sure": sure}))
    estimate = None
    if not isinstance(parsed, Unsupported):
        source, family = source_of(question.file), parsed.family()
        if (estimate := prior.prior(source, family)) is not None:
            why = f"not read from the drawing; dev prior for {source} {family} ({why})"
    if estimate is None and facts is not None and (said := _from_facts(question, facts)):
        return read(said.model_copy(update={"latency_s": clock() - start}))
    return read(
        Answer(
            id=question.id,
            answer=None if estimate is None else estimate.value,
            unit=None if estimate is None else estimate.unit,
            evidence=(),
            method=method,
            cost_usd=0.0,
            latency_s=clock() - start,
            confidence=None if estimate is None else estimate.confidence,
            abstain=True,  # answer_v1.1: a refusal abstains, says why, keeps a best estimate
            explanation=why,
        )
    )


def _sure(
    sure_at: Mapping[str, float] | None,
    family: str,
    value: float | None,
    flags: Sequence[str],
    agrees: bool | None = None,
) -> bool | None:
    if sure_at is None or family not in sure_at or value is None:
        return None  # no score (a vector or IFC page, a failed read): the gate has no verdict
    if flags:
        return None  # a photo or a scanned PDF: the gate's certificate is on CubiCasa scans
    if family in AGREEING_FAMILIES and agrees is not True:
        return False  # the signal's own count differs: two readers disagree, nothing is sure
    return value >= sure_at[family]


def _from_table(question: Question, row: TableAnswer, latency_s: float) -> Answer:
    """The answer a schedule printed on the sheet gives."""
    return Answer(
        id=question.id,
        answer=row.value,
        unit=row.unit,
        evidence=tuple(Evidence(file=question.file, page=row.page, box=box) for box in row.boxes),
        method=SCHEDULE,
        cost_usd=0.0,
        latency_s=latency_s,
        abstain=True if row.abstain_why else None,
        explanation=row.abstain_why,
    )


def _scheduled_room(parsed: Query) -> TableQuery | None:
    """The area of a room named by its name or number (or of the rooms with a printed name) as
    a room schedule's lookup: the sum of its area column over the rows that print that name.
    Asked when the takeoff has no such room (a schedule sheet with no plan, or a room the plan
    reader missed); None for any other question."""
    named = parsed.name or parsed.label
    if parsed.measure != "area" or parsed.subject != "room" or named is None:
        return None
    if parsed.storey or parsed.apartment or parsed.model or parsed.largest or parsed.indoor:
        return None
    return TableQuery(
        op="sum",
        kind="room",
        column=(("area",),),
        filters=(TableFilter(values=(named,)),),
        one_row=parsed.name is not None,  # the one room; a label is every room printing it
    )


def _read(parsed: Query | TableQuery | Unsupported) -> Callable[[Answer], Answer]:
    """How a misspelt question was read ("read 'mnay' as 'many'"), put before the answer's own
    explanation, so the user sees what was answered."""
    if not isinstance(parsed, Query) or not parsed.read_as:
        return lambda answer: answer
    note = "read " + ", ".join(parsed.read_as)

    def said(answer: Answer) -> Answer:
        words = "; ".join(text for text in (note, answer.explanation) if text)
        return answer.model_copy(update={"explanation": words})

    return said


def _from_takeoff(question: Question, found: Quantity, method: str, latency: float) -> Answer:
    """The takeoff's value with its marks. An estimated reading says what it rests on. A value
    two methods measured differently shows both, with the rule that kept one; when no rule
    decides, it keeps the takeoff's own reading and abstains."""
    notes = [text for text in (found.source, found.estimate) if text]  # estimate: the card's too
    conflicts, resolution, abstain = None, None, None
    if (disputed := found.conflict) is not None:
        count = found.unit == "count"
        conflicts = tuple(
            ConflictValue(
                value=round(value.value) if count else value.value,
                unit=found.unit,
                method=value.method,
                file=question.file,
                page=value.page,
                box=value.box,
            )
            for value in disputed.values
        )
        shown = ", ".join(  # in words, not method ids (R3 qa-2)
            f"{METHODS.get(value.method, value.method)} {value.value:g}"
            for value in disputed.values
        )
        if (rule := disputed.resolution) is not None:
            resolution = f"kept {rule.value:g}: {rule.rule}"
            notes.append(f"two methods disagree ({shown}); {resolution}")
        else:
            abstain = True
            notes.append(f"two methods disagree ({shown}) and no rule decides between them")
        notes += [text for text in (disputed.derived, disputed.note) if text]
    return Answer(
        id=question.id,
        answer=found.value,
        unit=found.unit,
        evidence=tuple(
            Evidence(file=question.file, page=mark.page, box=mark.box) for mark in found.marks
        ),
        method=method,
        cost_usd=0.0,  # a lookup: no model is called on the drawing
        latency_s=latency,
        abstain=abstain,
        explanation=_with_partial("; ".join(notes), found.partial, found.unit == "count") or None,
        estimate=None if found.estimate is None else True,
        conflicts=conflicts,
        resolution=resolution,
    )


NAMED_MISSING = 3  # rooms named in a partial total's sentence; the rest are counted


def _with_partial(said: str, partial: Partial | None, count: bool = False) -> str:
    """The other notes, then a partial total's sentence as a sentence of its own."""
    if partial is None:
        return said
    sentence = partial_text(partial, count=count)
    return f"{said.rstrip('.')}. {sentence}" if said else sentence


def partial_text(partial: Partial, count: bool = False, gaps: Sequence[str] = ()) -> str:
    """One plain sentence: a room total is the sum of the rooms found, and which it misses.
    `count`: the total is the number of rooms found, not their sum (QA round 3 R3-G2/G3);
    `gaps`: room numbers between the ones found that were not found (`number_gaps`)."""
    rooms = f"{partial.counted} room{'' if partial.counted == 1 else 's'}"
    named = _named(partial.missing)
    table = f"the {partial.schedule}" if partial.schedule else "a schedule on the sheet"
    if count:  # a refused box area leaves a room in the count: only missed rooms make it partial
        if not partial.read:
            return f"These are the {rooms} drawn on the sheet; {table} lists more: {named}."
        said = f"These are the {rooms} the reader found; rooms it missed are not counted."
        if partial.missing:
            said += f" Not counted: {named}."
        if gaps:
            said += f" Room numbers it did not find between them: {_listed(gaps)}."
        return said
    if partial.refused:  # rooms found, their box areas refused (raster_scale.refused_boxes)
        why = (
            "its box cannot be the room"
            if len(partial.refused) == 1
            else ("their boxes cannot be the rooms")
        )
        said = (
            f"This is the sum of the {rooms} with a measured area; not measured: "
            f"{_named(partial.refused)} ({why})"
        )
        if partial.read:
            said += "; rooms the reader missed are not in it either"
        return said + (f"; {table} lists more: {named}." if partial.missing else ".")
    if not partial.read:  # a vector or IFC sheet has no reader: only a schedule makes it partial
        said = f"This is the sum of the {rooms} drawn on the sheet"
        return f"{said}; {table} lists more: {named}."
    said = f"This is the sum of the {rooms} the reader found; rooms it missed are not in it"
    return said + (f". Not in it: {named}." if partial.missing else ".")


# Room numbers listed in a partial count's sentence; past this many, the rest are counted
NAMED_GAPS = 6
WHOLE_ROOM_NUMBER = re.compile(r"\d{1,4}")


def number_gaps(numbers: Iterable[str]) -> list[str]:
    """The room numbers missing between the whole numbers found (2, 3, 5, ... -> 1, 4), within
    each hundred (101-130 is one storey's run; 1-40 a sheet's): between the lowest and the highest
    found, and x01 when the lowest is x02. Refusal beats a wrong list (review-600): a run with
    fewer than 3 numbers, one numbered in steps (even or odd numbers only: their differences share
    a factor), or one missing more than a quarter of its numbers names nothing."""
    runs: dict[int, set[int]] = {}
    for text in numbers:
        if WHOLE_ROOM_NUMBER.fullmatch(text.strip()):
            n = int(text)
            runs.setdefault(n // 100, set()).add(n)
    out: list[int] = []
    for hundred, found in sorted(runs.items()):
        ordered = sorted(found)
        if len(ordered) < 3 or math.gcd(*(b - a for a, b in itertools.pairwise(ordered))) > 1:
            continue
        low = ordered[0] - 1 if ordered[0] == hundred * 100 + 2 else ordered[0]
        missing = [n for n in range(low, ordered[-1]) if n not in found]
        if len(missing) * 4 <= ordered[-1] - low + 1:
            out += missing
    return [str(n) for n in out]


def _listed(numbers: Sequence[str]) -> str:
    """ "1, 4, 20 and 28"; past NAMED_GAPS, "and N more"."""
    shown = list(numbers[:NAMED_GAPS])
    if (more := len(numbers) - NAMED_GAPS) > 0:
        return f"{', '.join(shown)} and {more} more"
    return shown[0] if len(shown) == 1 else f"{', '.join(shown[:-1])} and {shown[-1]}"


def _named(rooms: Sequence[str]) -> str:
    """The first NAMED_MISSING of `rooms`, and how many more."""
    named = ", ".join(rooms[:NAMED_MISSING])
    if (more := len(rooms) - NAMED_MISSING) > 0:
        named += f" and {more} more"
    return named


HINT = re.compile(r"\([^()]*\)")  # a parenthesised hint, as question_templates' PARENTHESES
BARE_NUMBER = re.compile(r"-?U?\d+\.\d+", re.IGNORECASE)  # as question_templates' ROOM_NUMBER
SHORT_LABEL = re.compile(r"[^\W\d_a-zäöå]{2}")  # MH, OH, KT: two capitals
CODED_LABEL = re.compile(r"[^\W\d_]+\d+")  # MH1, KH2: letters, then digits
WHOLE_NUMBER = re.compile(r"\d{2,4}")  # a room number of whole digits ("104"; takeoff's)
LETTERS = re.compile(r"[^\W\d_]{3}")
DOTTED = re.compile(r"\d[.,]\d")
# A count asked as "how many <noun>" / "the number of <noun>", English (vocab-nouns P2)
COUNT_NOUN = re.compile(
    r"^\s*(?:how\s+many|(?:what\s+is\s+)?the\s+number\s+of|number\s+of)\s+"
    r"(?P<noun>[^\W\d_][\w'\u2019 .-]*?)\s*"
    r"(?:\b(?:are|is|do|does|can|there|on|in|at|shown|printed|have|has)\b|[?.!]|$)",
    re.IGNORECASE,
)
# What may stand before a room number in a question: "No 2", "no. 2", "Nr 2", "#2", "№ 2"
NUMBER_SIGN = r"(?:(?:№|no\.?|nr\.?|#)\s*)?"
NUMBER_SIGNS = frozenset({"№", "no", "no.", "nr", "nr.", "#"})


class RoomByType:
    """The parser, with the area of a room asked by its type ("the area of the kitchen") turned
    into that room's own area (the key "room 2.01" answers under) when the drawing has exactly one
    room of the type and the takeoff has its area: one row, with its conflict and review (a room
    with no name, read from its furniture, by the largest of its type: itself). Any other
    question, or a type several rooms (or none) have, stays as parsed.

    The same for a room asked by a printed label or name the parser has no word for ("the area
    of the Reduit"), when the parser refuses the question as typed: when one room on the drawing
    carries that name (3 letters or more, no digits; a 2-letter one or one of letters and digits
    only as printed, "the MH", "the MH1"), the question is read with it as the room's name, and
    answers when that is an area (R2-2-3, R3-qa-1-1, R3-qa-5-2)."""

    def __init__(
        self, parser: QuestionParser, drawing: Drawing, quantities: Mapping[str, Quantity]
    ) -> None:
        self._parser = parser
        self._drawing = drawing
        self._quantities = quantities

    def parse(self, text: str) -> Query | TableQuery | Unsupported:
        parsed = self._parser.parse(text)
        if isinstance(parsed, Query) and parsed.storey is not None:
            storey = self._storey(parsed.storey, sheet=not parsed.model)
            if storey is None:
                return Unsupported(reason=NO_SUCH_STOREY)
            parsed = parsed.model_copy(update={"storey": storey})
        if isinstance(parsed, Unsupported):
            return self._floor(text, parsed) or self._printed(text) or parsed
        if isinstance(parsed, Query) and (unnamed := self._not_a_room(text, parsed)):
            return unnamed
        if isinstance(parsed, Query) and _sheet_count(parsed) and (inside := self._printed(text)):
            return inside  # "How many doors does Bagno have?" is not the sheet's count
        if not isinstance(parsed, Query):
            return parsed
        rooms = rooms_of_type(parsed, self._drawing)
        if len(rooms) > 1:  # "the living room" of two typed living: the one printed so (r11)
            return self._printed_of(text, parsed, rooms) or parsed
        if len(rooms) != 1:
            return parsed
        return self._area_of(rooms[0], parsed) or self._only_one(parsed) or parsed

    def _printed_of(self, text: str, parsed: Query, rooms: Sequence[Room]) -> Query | None:
        """The area of the one room whose printed label the question holds, when no other room
        carries that label; None otherwise. A label of the type's own words ("Hall") names a
        room only among `rooms`, the rooms of the type `parsed` asks for: "the Sports Hall" holds
        "Hall" and is not that room (review-595). A label with more words names its room whatever
        type the reader gave it ("the Multi-Purpose Hall", typed other, among 11 rooms typed
        hall: R3-A5)."""
        named = printed_rooms(self._parser, self._drawing, text)
        if named is None or len(named[1]) != 1:
            return None
        if named[1][0] not in rooms and self._type_words(named[0].name or "", parsed):
            return None
        for _, pattern in _printed_names(named[1][0]):
            # "the living room 1" names a room the label doesn't: refused, as before (review-415)
            if (at := pattern.search(text)) is not None and AFTER_ID.match(text, at.end()):
                return None
        return self._area_of(named[1][0], named[0])

    def _type_words(self, name: str, parsed: Query) -> bool:
        """Every word of `name` is a word for the room type `parsed` asks about (or "room")."""
        for word in name.split():
            if word.casefold() in ("room", "rooms"):
                continue
            alone = self._parser.parse(f"What is the area of the {word}?")
            if not (isinstance(alone, Query) and alone.subject == parsed.subject):
                return False
        return True

    def _not_a_room(self, text: str, parsed: Query) -> Unsupported | None:
        """A bare number the parser took as the room ("Area 3.14?", "level 1.5") that no room of
        the drawing is numbered or named: the question names no room (review-313 S2). Only when
        the number was its one subject, so "room 1.05" keeps its own answer."""
        name = parsed.name
        if parsed.subject != "room" or name is None or not BARE_NUMBER.fullmatch(name):
            return None
        if any(normalised(name) in room_names(room) for room in self._drawing.rooms):
            return None
        at = re.compile(rf"(?<![\w.]){re.escape(name)}(?![\w.])", re.IGNORECASE)
        again = self._parser.parse(at.sub(" ", text, count=1))
        if isinstance(again, Unsupported) and again.reason == NO_SUBJECT:
            return again
        return None

    def _only_one(self, parsed: Query) -> Query | None:
        """The one room of the type has no name to key its area by (read from its furniture):
        the largest room of that type is that room."""
        query = parsed.model_copy(update={"largest": True})
        return query if query.key() in self._quantities else None

    def _area_of(self, room: Room, parsed: Query) -> Query | None:
        """The area query of `room` by the first of its names the takeoff has a row for."""
        for name in sorted(room_names(room)):
            query = Query(
                measure="area", subject="room", name=name, storey=parsed.storey,
                read_as=parsed.read_as,
            )  # fmt: skip
            if query.key() in self._quantities:
                return query
        return None

    def _storey(self, asked: str, sheet: bool) -> str | None:
        """The drawing's own storey a question's storey names (big QA R1): the one of that name,
        else the one whose name holds it as a word ("OG2" is "OK OG2", "E00" is "E00_OKRD");
        `asked` itself on a drawing that names no storey, which then has no row for it and refuses
        (a quoted storey did so before; "on P1" on a plain plan gave the whole sheet's count on
        main, review-702 S1); None when the drawing names storeys and none, or several, are it.
        With `sheet` (not a question about the model), a sheet whose plans name their storeys is
        only those: the P2 sheet, which carries the model's storeys too, is no answer for P1 (its
        0 would be read as P1's)."""
        named = storeys(self._drawing)
        drawn = sorted({str(plan.storey) for plan in self._drawing.plans if plan.storey})
        if sheet and self._drawing.pages and drawn:
            named = tuple(drawn)
        if not named:
            return asked
        want = normalised(asked)
        same = [storey for storey in named if normalised(storey) == want]
        if not same:
            same = [s for s in named if want in re.split(r"[\W_]+", s.casefold())]
        return same[0] if len(same) == 1 else None

    def _floor(self, text: str, parsed: Unsupported) -> Query | Unsupported | None:
        """A floor named in words ("on the first floor", "1st floor"), which the parser refuses
        as a place, read as the drawing's one storey of that floor number (FIRST FLOOR, "Level
        1"). None when the question names no floor, or names none the rest of it can be asked
        of; NO_SUCH_FLOOR when no storey of the drawing is that floor, SEVERAL_FLOORS when more
        than one could be, SHARED_FLOOR when several plans carry it (ask says which floors there
        are, or what is on each plan).
        "How many doors are on the first floor?" was refused on a sheet titled FIRST FLOOR PLAN;
        "... on the 1st floor?" counted the whole sheet (fable-rooms r10 items 10, 11)."""
        if parsed.reason != UNQUOTED_PLACE:
            return None
        matches = list(FLOOR.finditer(text))
        if any(glued(match) for match in matches):  # "level-1": 1 or -1 (review-352 N5)
            return Unsupported(reason=GLUED_FLOOR)
        asked = {floor_number(match) for match in matches}
        if len(asked) != 1:
            return None
        number = asked.pop()
        named = [storey for storey in storeys(self._drawing) if floor_of(storey) == number]
        if len(named) > 1:
            return Unsupported(reason=SEVERAL_FLOORS)
        if not named and any(number in glued_floors(s) for s in storeys(self._drawing)):
            return Unsupported(reason=GLUED_FLOOR)  # a storey printed "LEVEL-1"
        if not named:
            rest = self._parser.parse(FLOOR_AT.sub(" ", text))
            return Unsupported(reason=NO_SUCH_FLOOR) if isinstance(rest, Query) else None
        (storey,) = named
        if sum(str(plan.storey) == storey for plan in self._drawing.plans) > 1:
            return Unsupported(reason=SHARED_FLOOR)  # alternatives or parts: never summed
        quote = "'{}'" if "'" not in storey else "„{}“"
        again = self._parser.parse(FLOOR.sub(lambda _: quote.format(storey), text))
        if isinstance(again, Query) and again.storey == storey:
            return again
        return None

    def _printed(self, text: str) -> Query | Unsupported | None:
        """The question read with the one room name of the drawing it holds as that room's name
        ("the Reduit" → "the room 'Reduit'"): that room's area, or the count of what is in it
        ("How many doors does the Cucina have?"); SEVERAL_PRINTED when several rooms carry the
        name (ask lists them)."""
        named = printed_rooms(self._parser, self._drawing, text)
        if named is None:
            return None
        again, rooms = named
        if len(rooms) != 1:
            return Unsupported(reason=SEVERAL_PRINTED)
        if again.measure != "area":
            return again
        # a room with no area keeps the question about it: the drawing doesn't give its area
        # (review-349 S3), never "not which room"
        return self._area_of(rooms[0], again) or again.model_copy(
            update={"name": normalised(rooms[0].label or again.name or "")}
        )


# A number or a one-letter identifier right after a room's label ("living room 1", "living room
# B", "living room no. 2"): it names a room the label alone doesn't
AFTER_ID = re.compile(r"\s*(?:(?:no|nr|num(?:ber)?)\.?\s*|#\s*)?(?:\d|[a-z]\b(?!'))", re.IGNORECASE)


def _printed_names(room: Room) -> list[tuple[str, re.Pattern[str]]]:
    """The names of a room a question may hold without quotes, each with how it is found (its
    group "name" is what the question is read with). A name of 3 letters or more in any case,
    with a whole number in it or not ("lobby", "open office 102"); a dotted room number stays
    the parser's ("1.07"). A 2-letter label (MH, OH) or one of letters and digits (MH1) only as
    printed, case-sensitive: never a word ("of", "is"). A whole room number alone ("104") only
    after "room" ("room 104"): never any number in the question."""
    found: list[tuple[str, re.Pattern[str]]] = []
    for name in room_names(room):
        if WHOLE_NUMBER.fullmatch(name):
            words = rf"(?<!\w)(?:room|rm\.?)\s+(?P<name>{re.escape(name)})(?![\w.])"
            found.append((name, re.compile(words, re.IGNORECASE)))
        elif len(name) > 2 and LETTERS.search(name) and not DOTTED.search(name):
            words = rf"(?<!\w)(?P<name>{_name_pattern(name)})(?!\w)"
            found.append((name, re.compile(words, re.IGNORECASE)))
    if room.label and (SHORT_LABEL.fullmatch(room.label) or CODED_LABEL.fullmatch(room.label)):
        words = rf"(?<!\w)(?P<name>{re.escape(room.label)})(?!\w)"
        found.append((normalised(room.label), re.compile(words)))
    return found


def _name_pattern(name: str) -> str:
    """How a printed name is found in a question: its words as printed, and a room number in it
    with "№", "No", "No.", "Nr" or "#" before it or nothing ("BED ROOM № 2" is "Bed Room No 2",
    "Bed Room #2" and "Bed Room 2"; vocab-nouns P3)."""
    tokens = name.split()
    parts: list[str] = []
    for at, token in enumerate(tokens):
        if token in NUMBER_SIGNS and at + 1 < len(tokens) and tokens[at + 1].isdigit():
            continue  # the number after it says it
        parts.append(NUMBER_SIGN + token if token.isdigit() else re.escape(token))
    return r"\s+".join(parts)


def counted_noun(text: str) -> str | None:
    """The noun of an English count question ("How many porches are there?" → "porches"), as
    written; None when the question is not one."""
    found = COUNT_NOUN.match(text)
    return None if found is None else " ".join(found.group("noun").split()) or None


def noun_forms(noun: str) -> set[str]:
    """The printed labels a counted noun can mean: as written and in the singular, with or
    without a trailing "room" ("guard rooms" → "guard room"; "music rooms" → "music")."""
    words = normalised(noun).split()
    forms = {" ".join(words), " ".join([*words[:-1], _singular(words[-1])])}
    for form in list(forms):
        for tail in (" rooms", " room"):
            if form.endswith(tail) and len(form) > len(tail):
                forms.add(form[: -len(tail)])
    return forms


def _singular(word: str) -> str:
    if word.endswith("ies") and len(word) > 4:
        return word[:-3] + "y"
    if word.endswith(("ches", "shes", "sses", "xes", "zes")):
        return word[:-2]
    if word.endswith("s") and not word.endswith("ss"):
        return word[:-1]
    return word


def printed_rooms(
    parser: QuestionParser, drawing: Drawing, text: str
) -> tuple[Query, list[Room]] | None:
    """The rooms carrying the one room name of the drawing the question holds, and the question
    read with it as a room's name ("the Reduit" → "the room 'Reduit'"), when that asks for a
    room's area or for a count of things in it; None when it holds no such name, or several.
    Two rooms printed "Bagno" give both: the question doesn't say which (ask lists them)."""
    found: dict[str, list[Room]] = {}
    at: dict[str, re.Match[str]] = {}
    for room in drawing.rooms:
        for name, pattern in _printed_names(room):
            match = pattern.search(text)
            if match is not None:
                found.setdefault(name, []).append(room)
                at[name] = match
    # "open office 102" holds "open office" too (three rooms print it): the longer name is meant
    inside = {
        name
        for name, match in at.items()
        for other in at.values()
        if other is not match
        and other.start() <= match.start()
        and match.end() <= other.end()
        and other.end() - other.start() > match.end() - match.start()
    }
    found = {name: rooms for name, rooms in found.items() if name not in inside}
    if len(found) != 1:
        return None
    ((name, rooms),) = found.items()
    match = at[name]
    named = match.group("name")
    if normalised(named) != name:  # asked as "Bed Room No 2": the room's own name keys it
        named = name
    again = parser.parse(f"{text[: match.start()]}room '{named}'{text[match.end() :]}")
    if not (isinstance(again, Query) and again.name is not None):
        return None
    if again.measure == "area":
        return again, rooms
    if again.measure != "count" or again.subject.startswith("room"):
        return None
    # a name in parentheses is a gloss on what is counted, not where: golden's "Kuinka monta pesu-
    # ja tiskiallasta (keittiö ja kylpytilat yhteensä ...)" counts the sheet's sinks
    if any(at.start() <= match.start() < at.end() for at in HINT.finditer(text)):
        return None
    # "toilets (WC)" on a sheet with a room printed WC: the label is the counted thing's own word,
    # so the question counts the sheet's toilets (fail-1, review-332 S1)
    word = parser.parse(f"How many {match.group()} are there?")
    if isinstance(word, Query) and word.subject == again.subject:
        return None
    return again, rooms


def _sheet_count(parsed: Query) -> bool:
    """A count of a kind of element over the whole sheet, no room, label or storey named."""
    return (
        parsed.measure == "count"
        and not parsed.subject.startswith("room")
        and parsed.name is None
        and parsed.label is None
        and parsed.storey is None
        and not parsed.model
    )


def rooms_of_type(parsed: Query, drawing: Drawing) -> list[Room]:
    """The drawing's rooms a question about a room's area by its type alone ("the kitchen") is
    about; none for any other question."""
    if not (
        parsed.measure == "area"
        and parsed.subject.startswith("room:")
        and parsed.name is None
        and parsed.label is None
        and not (parsed.largest or parsed.model or parsed.indoor)
    ):
        return []
    kind = parsed.subject.split(":", 1)[1]
    return [room for room in drawing.rooms if room.type == kind]


def _from_facts(question: Question, facts: Callable[[], FactSheet | None]) -> Answer | None:
    """The fact sheet's answer, or None; a fact the rules can't read refuses this question only."""
    try:
        sheet = facts()
        return None if sheet is None else answer_from_facts(question, sheet, 0.0)
    except Exception:  # a source's malformed fact must not stop the run
        logger.exception("question %d: no fact answer", question.id)
        return None


def answer_questions(
    questions: Iterable[Question],
    *,
    drawings: DrawingSource,
    parser: QuestionParser,
    clock: Clock,
    sink: AnswerSink,
    prior: AnswerPrior,
    prior_families: Set[tuple[str, str]] = frozenset(),
    confidence: AnswerConfidence | None = None,
    sure_at: Mapping[str, float] | None = None,
    flags: Callable[[str], Sequence[str]] | None = None,
    facts: FactSource | None = None,
) -> dict[str, int]:
    """Answers every question, file by file so each drawing model is loaded once, and writes the
    answers to the sink. Returns how many answers each method gave. `flags`: how ingest read a
    file's page, by its path (answer_question's `flags`); None: no page is flagged. `facts`
    (IFC_FACTS) gives each file's fact sheet, the last fallback, built on the file's first question
    that needs it."""
    by_file: dict[str, list[Question]] = {}
    for question in questions:
        by_file.setdefault(question.file, []).append(question)
    methods: Counter[str] = Counter()
    for file, asked in by_file.items():
        drawing = drawings.drawing(file)
        quantities = None if drawing is None else known_quantities(drawing)
        tables = () if drawing is None else drawing.tables or ()
        read_as = () if flags is None else flags(file)
        sheet = None if facts is None else functools.cache(functools.partial(facts.facts, file))
        reads = (
            parser
            if drawing is None or quantities is None
            else RoomByType(parser, drawing, quantities)
        )
        for question in asked:
            answer = answer_question(
                question,
                quantities,
                reads,
                clock,
                prior,
                tables,
                prior_families,
                confidence,
                sure_at,
                read_as,
                facts=sheet,
            )
            sink.write(answer)
            methods[answer.method] += 1
    return dict(methods)

"""The answering use cases: one question (the API) and a batch of them (the CLI)."""

import logging
import re
from collections import Counter
from collections.abc import Callable, Iterable, Mapping, Sequence, Set

from app.core.answering.model import (
    NO_SUBJECT,
    SEVERAL_PRINTED,
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
from app.core.pipeline.model import Partial, Quantity
from app.core.pipeline.second_count import METHODS
from app.core.pipeline.takeoff import known_quantities, normalised, room_names

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
    (orchestrator, 2026-11-14 O1)."""
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
    notes = [] if found.estimate is None else [found.estimate]  # the card's Estimate line too
    if found.partial is not None:
        notes.append(partial_text(found.partial))
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
        explanation="; ".join(notes) or None,
        estimate=None if found.estimate is None else True,
        conflicts=conflicts,
        resolution=resolution,
    )


NAMED_MISSING = 3  # rooms named in a partial total's sentence; the rest are counted


def partial_text(partial: Partial) -> str:
    """One plain sentence: a room total is the sum of the rooms found, and which it misses."""
    n = partial.counted
    said = (
        f"This is the sum of the {n} room{'' if n == 1 else 's'} the reader found; rooms it "
        "missed are not in it"
    )
    if partial.missing:
        named = ", ".join(partial.missing[:NAMED_MISSING])
        more = len(partial.missing) - NAMED_MISSING
        said += f". Not in it: {named}" + (f" and {more} more" if more > 0 else "")
    return said + "."


HINT = re.compile(r"\([^()]*\)")  # a parenthesised hint, as question_templates' PARENTHESES
BARE_NUMBER = re.compile(r"U?\d+\.\d+", re.IGNORECASE)  # as question_templates' ROOM_NUMBER
SHORT_LABEL = re.compile(r"[^\W\d_a-zäöå]{2}")  # MH, OH, KT: two capitals
CODED_LABEL = re.compile(r"[^\W\d_]+\d+")  # MH1, KH2: letters, then digits


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
        if isinstance(parsed, Unsupported):
            return self._printed(text) or parsed
        if isinstance(parsed, Query) and (unnamed := self._not_a_room(text, parsed)):
            return unnamed
        if isinstance(parsed, Query) and _sheet_count(parsed) and (inside := self._printed(text)):
            return inside  # "How many doors does Bagno have?" is not the sheet's count
        if not isinstance(parsed, Query) or len(rooms := rooms_of_type(parsed, self._drawing)) != 1:
            return parsed
        return self._area_of(rooms[0], parsed) or self._only_one(parsed) or parsed

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
        return self._area_of(rooms[0], again) if again.measure == "area" else again


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
        names = [(name, name, re.IGNORECASE) for name in room_names(room) if len(name) > 2]
        # a 2-letter label (MH, OH) or one of letters and digits (MH1) only as printed,
        # case-sensitive: never a word ("of", "is"); a room number stays the parser's
        if room.label and (SHORT_LABEL.fullmatch(room.label) or CODED_LABEL.fullmatch(room.label)):
            names.append((normalised(room.label), room.label, re.NOFLAG))
        for name, printed, flags in names:
            if flags and any(char.isdigit() for char in name):
                continue
            match = re.search(rf"(?<!\w){re.escape(printed)}(?!\w)", text, flags)
            if match is not None:
                found.setdefault(name, []).append(room)
                at[name] = match
    if len(found) != 1:
        return None
    ((name, rooms),) = found.items()
    match = at[name]
    again = parser.parse(f"{text[: match.start()]}room '{match.group()}'{text[match.end() :]}")
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
) -> dict[str, int]:
    """Answers every question, file by file so each drawing model is loaded once, and writes the
    answers to the sink. Returns how many answers each method gave. `flags`: how ingest read a
    file's page, by its path (answer_question's `flags`); None: no page is flagged."""
    by_file: dict[str, list[Question]] = {}
    for question in questions:
        by_file.setdefault(question.file, []).append(question)
    methods: Counter[str] = Counter()
    for file, asked in by_file.items():
        drawing = drawings.drawing(file)
        quantities = None if drawing is None else known_quantities(drawing)
        tables = () if drawing is None else drawing.tables or ()
        read_as = () if flags is None else flags(file)
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
            )
            sink.write(answer)
            methods[answer.method] += 1
    return dict(methods)

"""The answering use cases: one question (the API) and a batch of them (the CLI)."""

import logging
import re
from collections import Counter
from collections.abc import Callable, Iterable, Mapping, Sequence, Set

from app.core.answering.model import (
    Answer,
    ConflictValue,
    Evidence,
    Query,
    Question,
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
from app.core.answering.tables import answer_table
from app.core.drawing.model import Drawing, Room, Table
from app.core.pipeline.model import Quantity
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


def answer_question(
    question: Question,
    quantities: Mapping[str, Quantity] | None,
    parser: QuestionParser,
    clock: Clock,
    prior: AnswerPrior,
    tables: Sequence[Table] = (),
    prior_families: Set[tuple[str, str]] = frozenset(),
    confidence: AnswerConfidence | None = None,
) -> Answer:
    """`quantities` is the takeoff of the question's drawing (`known_quantities`), or None when
    the file has no drawing model; `tables` the schedules it prints. `prior_families` holds the
    (source, family) pairs the answer policy (ANSWER_POLICY) answers from the prior although
    the drawing gives a value: abstaining, with the prior's value, when the prior has one. A
    refusal has the reason in `method`, `abstain` true and the reason in words in `explanation`
    (answer_v1.1). Its `answer` is the prior's value for the question's family when there is one
    (with the prior's `confidence`), else None. With `confidence` (DECISIONS_CONFIDENCE), a
    takeoff answer gets its probability as `confidence`; when there is none, the reason is
    logged, never added to the answer."""
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
            return read(
                Answer(
                    id=question.id,
                    answer=row.value,
                    unit=row.unit,
                    evidence=tuple(
                        Evidence(file=question.file, page=row.page, box=box) for box in row.boxes
                    ),
                    method=SCHEDULE,
                    cost_usd=0.0,
                    latency_s=clock() - start,
                    abstain=True if row.abstain_why else None,
                    explanation=row.abstain_why,
                )
            )
        method = NOT_IN_DRAWING
        why = f"no schedule on the sheet resolves {parsed.family()}"
    else:
        found = quantities.get(parsed.key())
        method = NOT_IN_DRAWING if found is None else TAKEOFF
        why = f"the drawing model does not give {parsed.key()}"
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
        if rated.value is None:  # why goes to the log: nothing a reader of the answer can act on
            logger.info("question %d: no confidence: %s", question.id, rated.note)
            return read(answer)
        return read(answer.model_copy(update={"confidence": rated.value}))
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
        if not isinstance(parsed, Query) or len(rooms := rooms_of_type(parsed, self._drawing)) != 1:
            return parsed
        return self._area_of(rooms[0], parsed) or self._only_one(parsed) or parsed

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

    def _printed(self, text: str) -> Query | None:
        """The question read with the one room name of the drawing it holds as that room's name
        ("the Reduit" → "the room 'Reduit'"), when that asks for the room's area."""
        found: dict[str, list[Room]] = {}
        at: dict[str, re.Match[str]] = {}
        for room in self._drawing.rooms:
            names = [(name, name, re.IGNORECASE) for name in room_names(room) if len(name) > 2]
            # a 2-letter label (MH, OH) or one of letters and digits (MH1) only as printed,
            # case-sensitive: never a word ("of", "is"); a room number stays the parser's
            if room.label and (
                SHORT_LABEL.fullmatch(room.label) or CODED_LABEL.fullmatch(room.label)
            ):
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
        if len(rooms) != 1:
            return None
        match = at[name]
        again = self._parser.parse(
            f"{text[: match.start()]}room '{match.group()}'{text[match.end() :]}"
        )
        if not (isinstance(again, Query) and again.measure == "area" and again.name is not None):
            return None
        return self._area_of(rooms[0], again)


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
) -> dict[str, int]:
    """Answers every question, file by file so each drawing model is loaded once, and writes the
    answers to the sink. Returns how many answers each method gave."""
    by_file: dict[str, list[Question]] = {}
    for question in questions:
        by_file.setdefault(question.file, []).append(question)
    methods: Counter[str] = Counter()
    for file, asked in by_file.items():
        drawing = drawings.drawing(file)
        quantities = None if drawing is None else known_quantities(drawing)
        tables = () if drawing is None else drawing.tables or ()
        reads = (
            parser
            if drawing is None or quantities is None
            else RoomByType(parser, drawing, quantities)
        )
        for question in asked:
            answer = answer_question(
                question, quantities, reads, clock, prior, tables, prior_families, confidence
            )
            sink.write(answer)
            methods[answer.method] += 1
    return dict(methods)

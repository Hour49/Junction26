"""The engineer's question on one drawing: the answer_v1.1 line from the answering use case, with
the takeoff row it was looked up in (the surveyor's edits applied), or a refusal a person can read
with questions this drawing can answer.

Suggestions are built from the takeoff's rows that have a value, and a phrasing is offered only
when the parser maps it back to that row's key, so asking a suggestion is never refused.
"""

import re
from collections.abc import Iterable, Mapping, Sequence, Set

from app.core.answering.answer import (
    NO_DRAWING,
    PRIOR_BY_POLICY,
    SCHEDULE,
    TAKEOFF,
    UNSUPPORTED_QUESTION,
    RoomByType,
    answer_question,
    rooms_of_type,
)
from app.core.answering.model import (
    IN_ONE_ROOM,
    SEVERAL_THINGS,
    Answer,
    Query,
    Question,
    TableQuery,
    Unsupported,
)
from app.core.answering.ports import AnswerConfidence, AnswerPrior, Clock, QuestionParser
from app.core.answering.tables import answer_table
from app.core.drawing.model import ELEMENT_CLASSES, Drawing, Room, Table
from app.core.model import Frozen
from app.core.pipeline import rules as rule_pack
from app.core.pipeline.model import CountingRule, Quantity
from app.core.pipeline.takeoff import known_quantities, room_names
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
from app.core.review.review import label, parse_key, row

# Every counting rule's text by id, as the answer shows it.
RULES: dict[str, str] = {
    found.id: found.text for found in vars(rule_pack).values() if isinstance(found, CountingRule)
}
SUGGESTIONS = 6
PLURALS = {"bathtub": "bathtubs", "stair": "stairs", "sauna_stove": "sauna stoves"}
SCHEDULE_KINDS = ("door", "window", "room")  # schedules a sheet may print, by what its rows are
NO_SCALE = ("no_scale", "not_to_scale")
ROOM_NUMBER = re.compile(r"U?\d+\.\d+")  # a room number the parser reads without quotes
TEXTS = {
    "unsupported-question": "This question isn't one I can turn into a count, area, length or "
    "volume. Try one of these instead.",
    # `read` is empty: the do-nothing stand-in, or a real reader that found nothing on this sheet
    "no-reader": "Nothing was read from this sheet: its reader found no elements or rooms on it.",
    "no-scale": "The sheet has no scale, so lengths and areas can't be measured. Counts still "
    "work.",
    "no-drawing": "This file has no drawing model.",
    "policy": "The reader for this kind of sheet is not reliable enough for this question yet, so "
    "no number is given.",
}
PARTS = {  # an unsupported count that would drop part of the question: which part
    SEVERAL_THINGS: "This question names more than one kind of thing, and I count one kind across "
    "the whole drawing. Ask for each one on its own; try one of these.",
    IN_ONE_ROOM: "This question counts what is inside one room, and I count across the whole "
    "drawing. Try one of these instead.",
}


class Asked(Frozen):
    answer: Answer  # the answer_v1.1 line, as the scorer reads it
    query: str | None  # the takeoff key (or schedule query) the question became
    row: Row | None  # the takeoff row the value was read from, edits applied
    marks: tuple[MarkView, ...]  # the row's marks, or a schedule answer's cells
    refusal: Refusal | None
    proof: Proof  # what the screen draws as the answer's proof


class _Once:
    """The parser, asked once per question text: the query is shown next to the answer."""

    def __init__(self, parser: QuestionParser) -> None:
        self._parser = parser
        self._seen: dict[str, Query | TableQuery | Unsupported] = {}

    def parse(self, text: str) -> Query | TableQuery | Unsupported:
        if text not in self._seen:
            self._seen[text] = self._parser.parse(text)
        return self._seen[text]


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
) -> Asked:
    """`confidence` rates a takeoff answer as the pipeline does (DECISIONS_CONFIDENCE); its raw
    score is on the answer line only, never in the proof (it is not a calibrated probability)."""
    quantities = known_quantities(drawing)
    once = _Once(RoomByType(parser, drawing, quantities))
    question = Question(id=1, file=drawing.file, text=text)
    tables = drawing.tables or ()
    answer = answer_question(
        question, quantities, once, clock, prior, tables, prior_families, confidence
    )
    parsed = once.parse(text)
    query: str | None = None
    if isinstance(parsed, Query):
        query = parsed.key()
    elif isinstance(parsed, TableQuery):
        query = parsed.family()
    found = quantities.get(query) if query is not None and answer.method == TAKEOFF else None
    shown = None if found is None else row(found, drawing, state, RULES)
    if shown is not None:
        marks = shown.marks
    elif answer.method == SCHEDULE:
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
    if answer.method not in (TAKEOFF, SCHEDULE):
        code, words = _refusal(answer.method, parsed, query, drawing)
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
        refusal = Refusal(code=code, text=words, can_answer=can_answer)
    return Asked(answer=answer, query=query, row=shown, marks=marks, refusal=refusal, proof=proof)


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
        text = f"How many {kind}s are listed in the {kind} schedule?"
        parsed = parser.parse(text)
        if isinstance(parsed, TableQuery) and answer_table(parsed, tables) is not None:
            name = f"{kind}s in the {kind} schedule"
            yield Suggestion(quantity=parsed.family(), label=name, question=text)


def _phrasings(key: str) -> Iterable[str]:
    measure, subject, scope = parse_key(key)
    if scope == Scope(model=True):  # the building model's own total
        if measure == "count" and subject in ELEMENT_CLASSES:
            yield f"How many {PLURALS.get(subject, f'{subject}s')} are there in the building model?"
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
        if subject in ELEMENT_CLASSES:
            things = PLURALS.get(subject, f"{subject}s")
        elif subject.startswith("room:"):
            things = f"{subject.split(':', 1)[1]}s"
        elif subject in ("room", "apartment"):
            things = f"{subject}s"
        else:
            return
        yield f"How many {things} are there?"
        yield f"How many {things} are on this plan?"
    elif measure == "area" and subject == "room":
        yield "What is the total floor area?"
        yield "What is the total area of all rooms?"


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
            f"{label(query)}.",
        )
    return "not-in-drawing", f"This drawing doesn't give the {label(query)}."

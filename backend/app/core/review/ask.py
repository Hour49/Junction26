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
from app.core.drawing.model import ELEMENT_CLASSES, Drawing, Room, Table, words
from app.core.model import Frozen
from app.core.pipeline import rules as rule_pack
from app.core.pipeline.model import CountingRule, Quantity
from app.core.pipeline.takeoff import known_quantities, room_names
from app.core.review.check import (
    NO_SCORERS,
    Check,
    CheckPolicy,
    Disputes,
    Scorer,
    certified,
    double_check,
    held,
    no_disputes,
    schedule_check,
    score_of,
)
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
from app.core.review.review import label, parse_key, row, storey_twins, with_twins

# Every counting rule's text by id, as the answer shows it.
RULES: dict[str, str] = {
    found.id: found.text for found in vars(rule_pack).values() if isinstance(found, CountingRule)
}
SUGGESTIONS = 6
# Parser reasons (question_templates.py) for a supported kind of question about a subject it
# didn't recognise, or one without that quantity ("no area is taken off for door")
NO_SUBJECT = "no element, room or apartment named"
NO_QUANTITY = re.compile(r"no (count|area|length|volume) is taken off for (\S+)")
# Plurals plain English rules don't give (a kind's id is not always the word a person uses)
PLURALS = {"living": "living rooms"}
SCHEDULE_KINDS = ("door", "window", "room")  # schedules a sheet may print, by what its rows are
NO_SCALE = ("no_scale", "not_to_scale")
ROOM_NUMBER = re.compile(r"U?\d+\.\d+")  # a room number the parser reads without quotes
TEXTS = {
    "unsupported-question": "This question isn't one I can turn into a count, area, length or "
    "volume. Try one of these instead.",
    # `read` is empty: the do-nothing stand-in, or a real reader that found nothing on this sheet
    "no-reader": "Nothing was read from this sheet: its reader found no elements or rooms on it.",
    # the route's extractor is the do-nothing stand-in: there is no reader to blame
    "no-reader-yet": "Nothing was read from this sheet: there is no reader for this kind of sheet "
    "yet.",
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
    check: Check | None = None  # CHECK_POLICY's double-check request; None: certified or off


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
    sure_at: Mapping[str, float] | None = None,
    flags: Sequence[str] = (),
    raster: bool = False,
    check: CheckPolicy | None = None,
    route: str | None = None,
    disputes: Disputes = no_disputes,
    no_reader: bool = False,
    scorers: Mapping[str, Scorer] = NO_SCORERS,
) -> Asked:
    """`confidence` rates a takeoff answer as the pipeline does (DECISIONS_CONFIDENCE); its raw
    score is on the answer line only, never in the proof (it is not a calibrated probability).
    `flags`: how ingest read the page (judge.reading_flags: a phone photo, a scan). `raster`: the
    page was read on the raster route (an image, a photo, a scanned PDF). `no_reader`: the
    sheet's route has no reader (the stand-in), so a "no-reader" refusal says so, not that a
    reader found nothing. `check` (CHECK_POLICY): a takeoff answer it does not certify on `route`
    (ingest's) gets a double-check request with the places `disputes` finds; a family whose
    threshold is on a local gate's signal is scored by `scorers` (LOCAL_GATES), by signal name
    (app/core/review/check.py)."""
    quantities, unread = _flagged(known_quantities(drawing), drawing, flags, raster)
    once = _Once(RoomByType(parser, drawing, quantities))
    question = Question(id=1, file=drawing.file, text=text)
    tables = drawing.tables or ()
    answer = answer_question(
        question, quantities, once, clock, prior, tables, prior_families, confidence, sure_at, flags
    )
    parsed = once.parse(text)
    query: str | None = None
    if isinstance(parsed, Query):
        query = parsed.key()
    elif isinstance(parsed, TableQuery):
        query = parsed.family()
    found = quantities.get(query) if query is not None and answer.method == TAKEOFF else None
    shared = with_twins(state, storey_twins(quantities))
    shown = None if found is None else row(found, drawing, shared, RULES)
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
        if isinstance(parsed, Query) and query is not None and _groups(query) <= unread:
            code, words = "no-reader", _unread_text(query, flags)
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
        refusal = Refusal(code=code, text=words, can_answer=can_answer)
    request = None
    if check is not None and shown is not None and isinstance(parsed, Query):
        reason = held(shown, drawing)
        family = parsed.family()
        score = score_of(
            check, family, confidence=answer.confidence, drawing=drawing, value=answer.answer,
            scorers=scorers,
        )  # fmt: skip
        sure = reason is None and certified(
            check, route=route, family=family, score=score, flags=flags
        )
        if not sure:
            request = double_check(shown, marks, disputes(drawing, shown), reason)
    elif check is not None and answer.method == SCHEDULE:
        request = schedule_check(check)
    return Asked(
        answer=answer,
        query=query,
        row=shown,
        marks=marks,
        refusal=refusal,
        proof=proof,
        check=request,
    )


def _flagged(
    quantities: Mapping[str, Quantity], drawing: Drawing, flags: Sequence[str], raster: bool
) -> tuple[dict[str, Quantity], set[str]]:
    """On a page ingest flagged (a phone photo, a scan), a group its reader found nothing of
    (no element at all, no room at all) is unknown, not 0: its keys are left out and the group
    is returned as `unread`, so any question on it is refused, its key in the takeoff or not
    (F4-4b). Every other quantity carries the flag as its estimate, so the answer says what it
    rests on (R3-qa4-1). On any raster page, flagged or not, no room at all is unread too: a
    page can have 0 saunas, but not 0 rooms (F4-4)."""
    empty: set[str] = set()
    if flags and not drawing.elements:
        empty.update(ELEMENT_CLASSES)
    if (flags or raster) and not drawing.rooms:
        empty.add("room")
    if not flags and not empty:
        return dict(quantities), set()
    kept: dict[str, Quantity] = {}
    note = f"read from a page flagged at upload: {'; '.join(flags)}"
    for key, found in quantities.items():
        if _groups(key) <= empty:
            continue
        if not flags:
            kept[key] = found
            continue
        said = note if found.estimate is None else f"{found.estimate}; {note}"
        kept[key] = found.model_copy(update={"estimate": said})
    return kept, empty


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
        text = f"How many {plural(kind)} are listed in the {kind} schedule?"
        parsed = parser.parse(text)
        if isinstance(parsed, TableQuery) and answer_table(parsed, tables) is not None:
            name = f"{plural(kind)} in the {kind} schedule"
            yield Suggestion(quantity=parsed.family(), label=name, question=text)


def plural(kind: str) -> str:
    """The English plural of a kind of element or room ("balcony" → "balconies")."""
    if kind in PLURALS:
        return PLURALS[kind]
    kind = words(kind)
    if kind.endswith("y") and kind[-2:-1] not in ("a", "e", "i", "o", "u"):
        return f"{kind[:-1]}ies"
    if kind.endswith(("s", "x", "z", "ch", "sh")):
        return f"{kind}es"
    return f"{kind}s"


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
    return "not-in-drawing", f"This drawing doesn't give the {label(query, drawing)}."

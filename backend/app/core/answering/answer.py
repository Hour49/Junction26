"""The answering use cases: one question (the API) and a batch of them (the CLI)."""

from collections import Counter
from collections.abc import Iterable, Mapping, Sequence

from app.core.answering.model import (
    Answer,
    ConflictValue,
    Evidence,
    Question,
    TableQuery,
    Unsupported,
    source_of,
)
from app.core.answering.ports import (
    AnswerPrior,
    AnswerSink,
    Clock,
    DrawingSource,
    QuestionParser,
)
from app.core.answering.tables import answer_table
from app.core.drawing.model import Table
from app.core.pipeline.model import Quantity
from app.core.pipeline.takeoff import known_quantities

# `method` of an answer: how it was answered, or "refused:<why>" (the reason in words goes in
# answer_v1.1 `explanation`).
TAKEOFF = "takeoff"
SCHEDULE = "schedule"  # read from a schedule printed on the sheet (Drawing.tables)
NO_DRAWING = "refused:no-drawing"
UNSUPPORTED_QUESTION = "refused:unsupported-question"
NOT_IN_DRAWING = "refused:not-in-drawing"


def answer_question(
    question: Question,
    quantities: Mapping[str, Quantity] | None,
    parser: QuestionParser,
    clock: Clock,
    prior: AnswerPrior,
    tables: Sequence[Table] = (),
) -> Answer:
    """`quantities` is the takeoff of the question's drawing (`known_quantities`), or None when
    the file has no drawing model; `tables` the schedules it prints. A refusal has the reason in
    `method`, `abstain` true and the reason in words in `explanation` (answer_v1.1). Its `answer`
    is the prior's value for the question's family when there is one (with the prior's
    `confidence`), else None."""
    start = clock()
    parsed = parser.parse(question.text)
    found: Quantity | None = None
    if quantities is None:
        method, why = NO_DRAWING, "the file has no drawing model"
    elif isinstance(parsed, Unsupported):
        method, why = UNSUPPORTED_QUESTION, parsed.reason
    elif isinstance(parsed, TableQuery):
        if (row := answer_table(parsed, tables)) is not None:
            return Answer(
                id=question.id,
                answer=row.value,
                unit=row.unit,
                evidence=tuple(
                    Evidence(file=question.file, page=row.page, box=box) for box in row.boxes
                ),
                method=SCHEDULE,
                cost_usd=0.0,
                latency_s=clock() - start,
            )
        method = NOT_IN_DRAWING
        why = f"no schedule on the sheet resolves {parsed.family()}"
    else:
        found = quantities.get(parsed.key())
        method = NOT_IN_DRAWING if found is None else TAKEOFF
        why = f"the drawing model does not give {parsed.key()}"
    if found is not None:
        return _from_takeoff(question, found, method, clock() - start)
    estimate = None
    if not isinstance(parsed, Unsupported):
        source, family = source_of(question.file), parsed.family()
        if (estimate := prior.prior(source, family)) is not None:
            why = f"not read from the drawing; dev prior for {source} {family} ({why})"
    return Answer(
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


def _from_takeoff(question: Question, found: Quantity, method: str, latency: float) -> Answer:
    """The takeoff's value with its marks. An estimated reading says what it rests on. A value
    two methods measured differently shows both, with the rule that kept one; when no rule
    decides, it keeps the takeoff's own reading and abstains."""
    notes = [] if found.estimate is None else [f"rests on {found.estimate}"]
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
        shown = ", ".join(f"{value.method} {value.value:g}" for value in disputed.values)
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


def answer_questions(
    questions: Iterable[Question],
    *,
    drawings: DrawingSource,
    parser: QuestionParser,
    clock: Clock,
    sink: AnswerSink,
    prior: AnswerPrior,
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
        for question in asked:
            answer = answer_question(question, quantities, parser, clock, prior, tables)
            sink.write(answer)
            methods[answer.method] += 1
    return dict(methods)

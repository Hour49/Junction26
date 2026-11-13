"""The answering use cases: one question (the API) and a batch of them (the CLI)."""

from collections import Counter
from collections.abc import Iterable, Mapping

from app.core.answering.model import Answer, Evidence, Question, Unsupported
from app.core.answering.ports import AnswerSink, Clock, DrawingSource, QuestionParser
from app.core.pipeline.model import Quantity
from app.core.pipeline.takeoff import known_quantities

# `method` of an answer. answer_v1 has no field for why a question was refused, so the reason
# goes after "refused:".
TAKEOFF = "takeoff"
NO_DRAWING = "refused:no-drawing"
UNSUPPORTED_QUESTION = "refused:unsupported-question"
NOT_IN_DRAWING = "refused:not-in-drawing"


def answer_question(
    question: Question,
    quantities: Mapping[str, Quantity] | None,
    parser: QuestionParser,
    clock: Clock,
) -> Answer:
    """`quantities` is the takeoff of the question's drawing (`known_quantities`), or None when
    the file has no drawing model. A refusal is an answer of None with the reason in `method`."""
    start = clock()
    found: Quantity | None = None
    if quantities is None:
        method = NO_DRAWING
    else:
        parsed = parser.parse(question.text)
        if isinstance(parsed, Unsupported):
            method = UNSUPPORTED_QUESTION
        else:
            found = quantities.get(parsed.quantity)
            method = NOT_IN_DRAWING if found is None else TAKEOFF
    return Answer(
        id=question.id,
        answer=None if found is None else found.value,
        unit=None if found is None else found.unit,
        evidence=tuple(
            Evidence(file=question.file, page=mark.page, box=mark.box)
            for mark in (found.marks if found else ())
        ),
        method=method,
        cost_usd=0.0,  # a lookup: no model is called on the drawing
        latency_s=clock() - start,
    )


def answer_questions(
    questions: Iterable[Question],
    *,
    drawings: DrawingSource,
    parser: QuestionParser,
    clock: Clock,
    sink: AnswerSink,
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
        for question in asked:
            answer = answer_question(question, quantities, parser, clock)
            sink.write(answer)
            methods[answer.method] += 1
    return dict(methods)

"""RESOLVER: a model looks at what is in dispute and picks a value, or says it can't tell.
Two things are asked about: a conflict no rule decides and no person settled, and an answer
CHECK_POLICY does not certify. Its reply is checked by a model, never a person's word: a
conflict's pick becomes the value in use until a person settles or signs it, and an answer keeps
its value, `sure`, `check` and `level`, with the reply beside it."""

from collections.abc import Mapping, Sequence

from app.core.pipeline.model import ValueMark
from app.core.review.check import Check
from app.core.review.conflict_card import method, number, title
from app.core.review.model import (
    Candidate,
    MarkView,
    Resolved,
    ResolveRequest,
    ResolverUnavailable,
    ReviewState,
    Row,
    Spot,
)
from app.core.review.ports import Resolver
from app.core.review.review import disputes

SPOTS = 8  # crops per request at most: the strongest places first


def conflict_request(drawing_id: str, row: Row) -> ResolveRequest:
    """The request for the row's conflict: each method's value with where its items are, and
    those places as spots (each method's items in turn, so both sides are seen)."""
    disputed = row.conflict
    assert disputed is not None
    marks = disputed.value_marks or tuple(() for _ in disputed.values)
    candidates = tuple(
        Candidate(value=found.value, source=method(found.method), marks=placed)
        for found, placed in zip(disputed.values, marks, strict=True)
    )
    spots: list[Spot] = []
    for depth in range(max((len(placed) for placed in marks), default=0)):
        for candidate in candidates:
            if depth < len(candidate.marks) and len(spots) < SPOTS:
                mark = candidate.marks[depth]
                why = f"{candidate.source} counts {mark.label} here"
                spots.append(Spot(page=mark.page, box=mark.box, why=why))
    return ResolveRequest(
        drawing_id=drawing_id,
        quantity=row.key,
        question=title(row),
        unit=row.unit,
        kind="conflict",
        candidates=candidates,
        spots=tuple(spots),
    )


def answer_request(
    drawing_id: str, question: str, row: Row, marks: Sequence[MarkView], check: Check
) -> ResolveRequest:
    """The request for an answer CHECK_POLICY asks a person to double-check: the answer's value
    with its counted marks, and the places the readers disagree on as spots."""
    counted = tuple(
        ValueMark(page=mark.page, box=mark.box, label=mark.label or f"item {mark.n}")
        for mark in marks
        if mark.state in ("counted", "added")
    )
    spots = tuple(
        Spot(page=place.page, box=place.box, why=place.why) for place in check.disputed[:SPOTS]
    )
    return ResolveRequest(
        drawing_id=drawing_id,
        quantity=row.key,
        question=question,
        unit=row.unit,
        kind="answer",
        candidates=(Candidate(value=row.value, source="the answer", marks=counted),),
        spots=spots,
    )


def resolve_conflicts(
    drawing_id: str, rows: Sequence[Row], state: ReviewState, resolver: Resolver
) -> tuple[dict[str, Resolved], list[str]]:
    """The resolver's reply to each conflict of the drawing that needs a person and has no reply
    yet, by quantity key, and the notes of the ones that got none. A pick must be one of the
    methods' values: anything else is no reply (a conflict is between what the methods read)."""
    found: dict[str, Resolved] = {}
    notes: list[str] = []
    for row in disputes(rows):
        disputed = row.conflict
        if disputed is None or not row.needs_person or _asked(state.resolved, row):
            continue
        values = tuple(found_value.value for found_value in disputed.values)
        reply = resolver.resolve(conflict_request(drawing_id, row))
        if isinstance(reply, ResolverUnavailable):
            notes.append(f"{row.label}: {reply.note}")
            continue
        if reply.value is not None:
            # a pick is one of the methods' values as the card writes it ("22.40 m²"): kept as
            # that method's exact value, so the row shows what the method read
            same = [value for value in values if number(row, value) == number(row, reply.value)]
            if not same:
                notes.append(
                    f"{row.label}: the resolver picked {reply.value}, which no method read"
                )
                continue
            reply = reply.model_copy(update={"value": same[0]})
        found[row.key] = reply.model_copy(update={"of": values})
    return found, notes


def _asked(resolved: Mapping[str, Resolved], row: Row) -> bool:
    """The resolver already replied about the conflict as it is now."""
    reply = resolved.get(row.key)
    assert row.conflict is not None
    return reply is not None and reply.of == tuple(found.value for found in row.conflict.values)

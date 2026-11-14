"""A conflict as the conflict card says it (board #14, Tudor's asks 9 and 10): a plain-words title,
why it is a conflict and how it is decided, and short answers a person can tap. Rule-based on the
takeoff row, no model and no paid call."""

from app.core.drawing.model import words
from app.core.pipeline.second_count import METHODS
from app.core.review.model import Row
from app.core.review.review import noun

UNITS = {"m2": "m²", "m3": "m³", "m": "m"}


def number(row: Row, value: float) -> str:
    """A value as the card writes it: "13" in a count, "22.40 m²" in an area."""
    if row.unit == "count":
        return str(round(value))
    return f"{value:.2f} {UNITS.get(row.unit, row.unit)}"


def answer(row: Row, value: float) -> str:
    """A value as an answer a person could type: "13 doors", "1 kitchen", "22.40 m²"."""
    said = number(row, value)
    if row.unit != "count":
        return said
    name = noun(row.measure, row.subject, round(value))
    return f"{said} {name}" if name is not None else said


def _values(row: Row) -> list[float]:
    """The conflict's values, each once, in the order the methods measured them."""
    assert row.conflict is not None
    seen: list[float] = []
    for found in row.conflict.values:
        if all(number(row, found.value) != number(row, other) for other in seen):
            seen.append(found.value)
    return seen


def _or(parts: list[str]) -> str:
    return parts[0] if len(parts) == 1 else f"{', '.join(parts[:-1])} or {parts[-1]}"


def title(row: Row) -> str:
    """ "Door count: 13 or 11?" """
    said = row.label[:1].upper() + row.label[1:]
    return f"{said}: {_or([number(row, value) for value in _values(row)])}?"


def method(name: str) -> str:
    return METHODS.get(name, f"the {words(name)}")


def why(row: Row) -> str:
    """What each method read and how the conflict is decided, in plain words."""
    disputed = row.conflict
    assert disputed is not None
    read = [f"{number(row, found.value)} by {method(found.method)}" for found in disputed.values]
    text = f"The methods disagree: {', '.join(read)}."
    if disputed.note:
        text += f" {disputed.note.rstrip('.')}."
    if disputed.resolution is None:
        return text + " No rule decides between them, so a person has to choose."
    picked = number(row, disputed.resolution.value)
    return text + f" Settled by a rule ({disputed.resolution.rule}): {picked} is used."


def suggestions(row: Row) -> list[str]:
    """Short answers to tap: each value the methods read, as a person would type it."""
    return [answer(row, value) for value in _values(row)]

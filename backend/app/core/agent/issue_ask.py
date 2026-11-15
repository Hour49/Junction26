"""The chat asks about an open issue before it answers (decision 0018): which of the project's
issues an ask_drawings answer rests on, matched by drawing, quantity and question (never a
model's guess), and the ask turn's text and choices. Issues are plain JSON, as GET /api/projects/
{id}/issues gives them."""

import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

from app.core.agent.model import Json, Option

ASKS = 2  # at most this many asks before one question is answered
SKIP = "Skip for now"
METHODS = {  # second_count.METHODS, in the words a chip has room for
    "plan_drawing": "the sheet",
    "parser": "the sheet",
    "detector": "the detector",
    "ifc_model": "the IFC model",
    "schedule": "the schedule",
    "printed_label": "printed areas",
    "polygon_x_scale": "room outlines",
    "printed_total": "printed total",
}
UNITS = {"m2": "m²", "m": "m", "count": ""}


@dataclass(frozen=True)
class Asker:
    """What a turn needs to ask: the project's issues (loaded when ask_drawings has answered),
    the issue ids a person skipped (kept with the project), and how many asks are left."""

    load: Callable[[], list[Json]]
    skipped: frozenset[str] = field(default_factory=frozenset[str])
    left: int = ASKS


def _base(key: str) -> str:
    return re.sub(r"\|storey=[^|]*", "", key)  # a storey's row is its sheet row's (K4)


def _parts(given: Json) -> list[Json]:
    parts: list[Json] = given.get("parts") or []
    return parts


def _quantity(part: Json) -> Json:
    answer: Json = part.get("answer") or {}
    quantity: Json = answer.get("quantity") or {}
    return quantity


def _answered(part: Json) -> bool:
    answer: Json = part.get("answer") or {}
    return answer.get("answer") is not None and answer.get("refusal") is None


def _matches(issue: Json, given: Json) -> bool:
    """Whether the answer `given` (a ProjectAnswer) rests on `issue` (D1: blocking ones, and a
    reading flag on a drawing that answered). A refusal is a note: the drawings that answered
    stand, so it is not asked."""
    parts = _parts(given)
    drawing = issue.get("drawing_id")
    on = [part for part in parts if part.get("drawing_id") == drawing]
    kind = issue.get("kind")
    if kind == "conflict":
        key = issue.get("quantity")
        return (
            issue.get("severity") == "needs_person"
            and key is not None
            and any(_base(str(_quantity(part).get("key", ""))) == _base(key) for part in on)
        )
    if kind == "reading_flag":
        return any(_answered(part) for part in on)
    if kind == "unrelated_file":  # a file triage was unsure about may hold what no drawing has
        return issue.get("severity") == "needs_person" and not any(map(_answered, parts))
    return False


def related(issues: Sequence[Json], given: Json, skipped: frozenset[str]) -> list[Json]:
    """The open issues the answer rests on that nobody answered or skipped, in the list's order."""
    return [
        issue
        for issue in issues
        if issue.get("state") == "open"
        and issue.get("answer") is None
        and issue.get("id") not in skipped
        and _matches(issue, given)
    ]


def noted(issues: Sequence[Json], given: Json) -> list[Json]:
    """The issues the answer rests on that a person already answered with a note (D5)."""
    return [
        issue
        for issue in issues
        if issue.get("state") == "open" and issue.get("answer") and _matches(issue, given)
    ]


def _number(value: float) -> str:
    return f"{value:.2f}".rstrip("0").rstrip(".") if value != int(value) else str(int(value))


def options_of(issue: Json, given: Json) -> tuple[Option, ...]:
    """The ask's choices: a conflict's values (picking one settles it), the issue's own
    suggestions, then Skip."""
    out: list[Option] = []
    if issue.get("kind") == "conflict":
        for part in _parts(given):
            quantity = _quantity(part)
            if part.get("drawing_id") != issue.get("drawing_id"):
                continue
            if _base(str(quantity.get("key", ""))) != _base(str(issue.get("quantity"))):
                continue
            conflict: Json = quantity.get("conflict") or {}
            values: list[Json] = conflict.get("values") or []
            unit = UNITS.get(str(quantity.get("unit")), "")
            for value in values:
                shown = f"{_number(float(value['value']))} {unit}".strip()
                method = METHODS.get(str(value.get("method")), "")
                label = f"Use {shown}" + (f" ({method})" if method else "")
                if all(option.value != float(value["value"]) for option in out):
                    out.append(Option(label=label[:60], message=label, value=value["value"]))
            break
    suggestions: list[str] = issue.get("suggestions") or []
    out += [Option(label=said[:60], message=said) for said in suggestions]
    out.append(Option(label=SKIP, message=SKIP, skip=True))
    return tuple(out)


def ask_text(issue: Json) -> str:
    where = issue.get("drawing_name") or issue.get("file") or "A file"
    question = (
        "Which value should I use?"
        if issue.get("kind") == "conflict"
        else "What should I note before I answer?"
    )
    return f"Before I answer: {where} has an open issue on this. {issue['why']} {question}"


def answered_line(issue: Json, text: str, value: float | None) -> str:
    """What the next turn's model is told about the person's answer."""
    where = issue.get("drawing_name") or issue.get("file")
    settled = f" The conflict is settled to {_number(value)}." if value is not None else ""
    return (
        f'(The person answered the open issue "{issue.get("label")}" on {where}: '
        f'"{text}".{settled} Answer the question above with that.)'
    )


def skipped_ending(issue: Json) -> str:
    """The end of the answer after a skip (D2): said by the server, so it is always there."""
    where = issue.get("drawing_name") or issue.get("file")
    return (
        f"This rests on an open issue on {where}: {issue.get('label')}. "
        "Do you have other questions?"
    )

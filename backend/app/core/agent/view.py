"""The plan a turn shows (.agents/chat/contract.md A-B): the `show_on_plan` tool's arguments and
schema, and a View built from places in the evidence ledger. Places come only from tool results
(ev ids); the model never writes a box."""

from collections.abc import Mapping, Sequence
from typing import Any, Literal

from pydantic import Field

from app.core.agent.model import Box, View, ViewMark
from app.core.model import Frozen

SHOW_ON_PLAN = "show_on_plan"
MARKS = 60  # at most this many places in one view
CAPTION_CHARS = 120
MARGIN = 0.03  # page fractions around the marks


class ShowArgs(Frozen):
    evidence_ids: tuple[str, ...] = Field(default=(), max_length=MARKS)
    answer: Literal["latest"] | None = None
    marks: Literal["all", "disputed"] = "all"
    caption: str = Field(default="", max_length=CAPTION_CHARS)


SHOW_ON_PLAN_TOOL: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": SHOW_ON_PLAN,
        "description": (
            "Show places on the plan beside the chat (the user asks where something is, or to "
            "see it). Give evidence_ids (any ev id of this chat, all on one drawing page), or "
            "answer: latest for the marks of the latest ask_drawings answer of this chat (marks: "
            "disputed for only the ones the readers disagree on) without asking again. caption: "
            "a few plain words on what is shown. An answer that cites places is shown anyway: "
            "call this only to show other places than the ones the answer cites."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "evidence_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "maxItems": MARKS,
                },
                "answer": {"type": "string", "enum": ["latest"]},
                "marks": {"type": "string", "enum": ["all", "disputed"]},
                "caption": {"type": "string", "maxLength": CAPTION_CHARS},
            },
            "required": ["caption"],
        },
    },
}


def pages(
    ids: Sequence[str], ledger: Mapping[str, Mapping[str, Any]]
) -> dict[tuple[str, int], list[str]]:
    """`ids` grouped by (drawing id, page), in first-seen order."""
    out: dict[tuple[str, int], list[str]] = {}
    for ev in ids:
        found = ledger[ev]
        out.setdefault((str(found["drawing_id"]), int(found["page"])), []).append(ev)
    return out


def view_of(
    place: tuple[str, int],
    ids: Sequence[str],
    ledger: Mapping[str, Mapping[str, Any]],
    numbers: Mapping[str, int],
    name: str | None,
    caption: str | None,
    source: Literal["show_on_plan", "evidence"],
    around: Sequence[Box] = (),
) -> View:
    """The view of drawing page `place` (drawing id, page) with places `ids` on it, each mark
    numbered as in the turn's evidence (`numbers`: ev id → n). `around`: more boxes the focus
    box takes in (an edit's geometry); `ids` or `around` is not empty."""
    marks = tuple(
        ViewMark(
            n=numbers[ev],
            label=ledger[ev]["label"],
            box=tuple(ledger[ev]["box"]),  # pyright: ignore[reportArgumentType]
            polygon=_points(ledger[ev].get("polygon")),
        )
        for ev in ids
    )
    return View(
        drawing_id=place[0],
        name=name,
        page=place[1],
        box=frame([m.box for m in marks] + list(around)),
        marks=marks,
        caption=caption,
        source=source,
    )


def frame(boxes: Sequence[Box]) -> Box:
    """The union of `boxes` with MARGIN around it, inside the page."""
    x0 = min(b[0] for b in boxes) - MARGIN
    y0 = min(b[1] for b in boxes) - MARGIN
    x1 = max(b[2] for b in boxes) + MARGIN
    y1 = max(b[3] for b in boxes) + MARGIN
    return (round(max(0.0, x0), 4), round(max(0.0, y0), 4),
            round(min(1.0, x1), 4), round(min(1.0, y1), 4))  # fmt: skip


def bounds(polygon: Sequence[Sequence[float]]) -> Box:
    xs = [p[0] for p in polygon]
    ys = [p[1] for p in polygon]
    return (min(xs), min(ys), max(xs), max(ys))


def _points(value: Any) -> tuple[tuple[float, float], ...] | None:
    if not value:
        return None
    return tuple((float(x), float(y)) for x, y in value)

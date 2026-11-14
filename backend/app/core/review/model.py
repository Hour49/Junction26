"""The surveyor's review of a drawing's takeoff: the edits kept per drawing, and the takeoff rows
the API shows (docs/API.md, "Takeoff and review")."""

from typing import Literal

from pydantic import Field

from app.core.drawing.model import Box, Polygon, RoomType
from app.core.model import Frozen
from app.core.pipeline.model import Measure, QuantityConflict, QuantityUnit

# excluded: left out by the counting rule, with the reason (Quantity.excluded); `restore` counts
# it in, and it shows as counted with its reason kept.
MarkState = Literal["counted", "rejected", "added", "excluded"]
# Ranked as the review screen sorts rows: what needs a look comes first.
RowStatus = Literal["signed", "conflict", "estimate", "edited", "agree", "single"]
Action = Literal["reject", "restore", "add", "settle", "reset"]
RefusalCode = Literal[
    "unsupported-question", "not-in-drawing", "not-read", "no-reader", "no-scale", "no-drawing"
]


class Added(Frozen):
    """A mark the surveyor added: an item the drawing model missed (counts only)."""

    id: str  # a1, a2...
    page: int = Field(ge=1)
    box: Box


class SignOff(Frozen):
    by: str = Field(min_length=1)
    at: str  # ISO 8601, UTC
    value: int | float


class Settled(Frozen):
    """The value a surveyor chose to keep for a quantity (the `settle` action)."""

    value: int | float
    at: str  # ISO 8601, UTC


class ReviewState(Frozen):
    """Every edit made to one drawing's takeoff, by quantity key."""

    rejected: dict[str, tuple[str, ...]] = Field(default_factory=dict[str, tuple[str, ...]])
    added: dict[str, tuple[Added, ...]] = Field(default_factory=dict[str, tuple[Added, ...]])
    settled: dict[str, Settled] = Field(default_factory=dict[str, Settled])
    signed: dict[str, SignOff] = Field(default_factory=dict[str, SignOff])
    # Excluded marks (x1, x2...) the surveyor counted in after all
    included: dict[str, tuple[str, ...]] = Field(default_factory=dict[str, tuple[str, ...]])


class Edit(Frozen):
    """One review edit (POST /drawings/{id}/review). `reset` without a quantity resets them all."""

    quantity: str | None = Field(default=None, min_length=1)
    action: Action
    mark: str | None = None  # reject, restore
    page: int | None = Field(default=None, ge=1)  # add
    box: Box | None = None  # add
    value: float | None = None  # settle


class MarkView(Frozen):
    """One mark as the screen draws it. `n`: its number on the drawing, None when not counted.
    `value`: its share of the quantity (1 in a count, the room's m2 in an area), None: unknown.
    `label`: the room's printed label, else the element class; `ref`: the element or room id in
    the drawing model; both None when the mark is no item of the model (an added mark)."""

    id: str
    n: int | None
    page: int = Field(ge=1)
    box: Box
    polygon: Polygon | None
    state: MarkState
    value: float | None
    label: str | None
    ref: str | None
    reason: str | None  # why it is left out (state excluded)
    room_type: RoomType | None = None  # a room's type; None: no room (an element, an added mark)


class RuleText(Frozen):
    id: str
    text: str


class MethodValue(Frozen):
    method: str
    value: int | float


class Scope(Frozen):
    """The filters of a takeoff key, parsed, so the screen can group rows without parsing keys."""

    storey: str | None = None
    label: str | None = None
    name: str | None = None
    apartment: str | None = None
    indoor: bool = False
    model: bool = False
    largest: bool = False


class Row(Frozen):
    """One quantity of the takeoff with its review state."""

    key: str
    label: str
    measure: Measure
    subject: str
    scope: Scope
    value: int | float
    unit: QuantityUnit
    original_value: int | float
    status: RowStatus
    needs_person: bool  # methods disagree, no rule decides and nobody settled it: no sign-off
    rule: RuleText
    estimate: str | None
    first: MethodValue | None  # the drawing's own reading, when a second method measured it
    second: MethodValue | None  # the independent method's value; None: measured once
    conflict: QuantityConflict | None
    settled: Settled | None
    marks: tuple[MarkView, ...]
    signed: SignOff | None
    # Counted by a second reader with no position of its own (decide's count swap adds elements
    # with `attrs.located` false), per class: in `value`, never drawn as a mark
    unlocated: dict[str, int] = Field(default_factory=dict[str, int])
    # What a count is a count of, as the screen writes it after the number ("doors", "door" at 1);
    # None: not a count of one kind of thing (an area, a room type, a combined count)
    noun: str | None = None


class Refusal(Frozen):
    """Why a question gets no number, for a person, with questions this drawing can answer."""

    code: RefusalCode
    text: str
    can_answer: tuple["Suggestion", ...]


class Suggestion(Frozen):
    """A question the parser is checked to map to `quantity`, so asking it is never refused."""

    quantity: str
    label: str
    question: str

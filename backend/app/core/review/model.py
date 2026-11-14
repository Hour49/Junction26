"""The surveyor's review of a drawing's takeoff: the edits kept per drawing, and the takeoff rows
the API shows (docs/API.md, "Takeoff and review")."""

from typing import Literal

from pydantic import Field, model_validator

from app.core.drawing.model import Box, Polygon, RoomType
from app.core.model import Frozen
from app.core.pipeline.model import Measure, QuantityConflict, QuantityUnit, ValueMark

# excluded: left out by the counting rule, with the reason (Quantity.excluded); `restore` counts
# it in, and it shows as counted with its reason kept.
MarkState = Literal["counted", "rejected", "added", "excluded"]
# Ranked as the review screen sorts rows: what needs a look comes first.
RowStatus = Literal["signed", "conflict", "estimate", "edited", "agree", "single"]
Action = Literal["reject", "restore", "add", "settle", "unsettle", "reset"]
NOTE_MAX = 280  # a settle's note: a typed answer, not a document
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
    note: str | None = None  # the person's answer in words, when they typed one


def is_none(value: object) -> bool:
    """A field left out of the JSON while it is None: added for RESOLVER, so with it off every
    response and stored state stays as it was."""
    return value is None


def _empty(value: object) -> bool:
    return not value


class Resolved(Frozen):
    """What the resolver (RESOLVER, app/core/review/resolve.py) said about a conflict or an answer
    that is not certified: a value it picked, or that it can't tell, why, and where it looked.
    Checked by a model: never a person's settle or sign-off, never certified."""

    verdict: Literal["picked", "cannot_tell"]
    value: int | float | None  # None exactly when it can't tell
    reason: str = Field(min_length=1)  # one plain sentence for the person
    marks: tuple[ValueMark, ...] = ()  # where it looked or what it counted
    by: str = Field(min_length=1)  # "carbon:<model>", the fake's name in tests
    at: str  # ISO 8601, UTC: when it was first resolved
    # The conflict's values it was asked about, in order: a stored pick applies only while the
    # takeoff still disagrees between exactly these values (empty on an answer)
    of: tuple[int | float, ...] = ()

    @model_validator(mode="after")
    def _value_with_pick(self) -> "Resolved":
        if (self.value is None) != (self.verdict == "cannot_tell"):
            raise ValueError("a pick has a value, cannot_tell has none")
        return self


class ReviewState(Frozen):
    """Every edit made to one drawing's takeoff, by quantity key."""

    rejected: dict[str, tuple[str, ...]] = Field(default_factory=dict[str, tuple[str, ...]])
    added: dict[str, tuple[Added, ...]] = Field(default_factory=dict[str, tuple[Added, ...]])
    settled: dict[str, Settled] = Field(default_factory=dict[str, Settled])
    signed: dict[str, SignOff] = Field(default_factory=dict[str, SignOff])
    # Excluded marks (x1, x2...) the surveyor counted in after all
    included: dict[str, tuple[str, ...]] = Field(default_factory=dict[str, tuple[str, ...]])
    # What the resolver said about a conflict, by quantity key (POST .../resolve): not an edit, a
    # reset keeps it; a person's settle or sign-off wins over it
    resolved: dict[str, Resolved] = Field(default_factory=dict[str, Resolved], exclude_if=_empty)


class Edit(Frozen):
    """One review edit (POST /drawings/{id}/review). `reset` without a quantity resets them all."""

    quantity: str | None = Field(default=None, min_length=1)
    action: Action
    mark: str | None = None  # reject, restore
    page: int | None = Field(default=None, ge=1)  # add
    box: Box | None = None  # add
    value: float | None = None  # settle
    # settle: the person's answer in words; without `value` the value in use is kept with it
    note: str | None = Field(default=None, min_length=1, max_length=NOTE_MAX)

    @model_validator(mode="after")
    def _note_with_settle(self) -> "Edit":
        if self.note is not None and self.action != "settle":
            raise ValueError(f"a note goes with settle, not {self.action}")
        if self.note is not None and not self.note.strip():
            raise ValueError("a settle's note has no words")
        return self


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
    # RESOLVER: what the resolver said about this row's conflict; left out of the JSON when None
    resolved: Resolved | None = Field(default=None, exclude_if=is_none)


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


class Candidate(Frozen):
    """One value in dispute and who reads it, with where its items are."""

    value: int | float
    source: str  # in words: "the drawn plan", "the building model", "the answer"
    marks: tuple[ValueMark, ...] = ()


class Spot(Frozen):
    """One disputed place the resolver should look at (a crop of the page around `box`)."""

    page: int = Field(ge=1)
    box: Box
    why: str


class ResolveRequest(Frozen):
    """What the resolver is asked about one conflict or one answer that is not certified. Its
    JSON is the cache key, so it holds only what decides the reply."""

    drawing_id: str
    quantity: str  # the takeoff key
    question: str  # in words: the person's question, or the conflict's title
    unit: QuantityUnit
    kind: Literal["conflict", "answer"]
    candidates: tuple[Candidate, ...] = Field(min_length=1)
    spots: tuple[Spot, ...] = ()


class ResolverUnavailable(Frozen):
    """No reply: the budget is used up, a timeout, a reply that doesn't parse. The thing stays
    as it was; `note` says why."""

    note: str

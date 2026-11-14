"""A rule pack and the results of checking a drawing against it (decision 0009).

A pack is data (backend/app/rules/<id>.json). Validating it here is what refuses a rule nobody
can trace to a clause: no clause ref, no https URL or no quoted sentence and the pack does not load.
"""

from typing import Literal

from pydantic import Field, model_validator

from app.core.drawing.model import Box, ElementClass, Polygon, RoomType
from app.core.model import Frozen

NOTE = "A pre-check of a few rules, not a compliance certificate."

# room_area: each room of the types, its area; room_windows: each room of the types, the windows
# on its outline; door_width: each door, its width from the symbol at the scale (or the model's);
# takeoff: one quantity of the takeoff, for the whole sheet.
Op = Literal["room_area", "room_windows", "door_width", "takeoff"]
Comparison = Literal[">=", ">", "<=", "<"]
CheckUnit = Literal["m2", "m", "count"]
CheckStatus = Literal["pass", "fail", "cannot_tell"]
# A rule, a drawing or a project: also not_applicable, when the drawing as read has nothing the
# rule applies to (rooms were read and none is a bedroom; doors were read and there is none)
RuleStatus = Literal["pass", "fail", "cannot_tell", "not_applicable"]
# The comparison as the screen writes it before the limit ("at least 7 m2")
COMPARISON_TEXT: dict[str, str] = {
    ">=": "at least",
    ">": "more than",
    "<=": "at most",
    "<": "less than",
}
UNIT_OF_OP: dict[str, CheckUnit] = {"room_area": "m2", "room_windows": "count", "door_width": "m"}
ROOM_OPS = ("room_area", "room_windows")


class Clause(Frozen):
    """Where a limit comes from: the clause someone read, the page it is on, and its sentence."""

    ref: str = Field(min_length=1)  # act or decree, section, subsection
    url: str = Field(pattern=r"^https://\S+$")
    quote: str = Field(min_length=1)  # as printed, in the source's language
    quote_en: str | None = Field(default=None, min_length=1)  # our English, when not English


class AppliesTo(Frozen):
    """What a rule checks, in the drawing model's words (room types as MarkView.room_type,
    element classes as the drawing model's). Room ops: the rooms of `room_types`, but not one
    whose printed label is one of `skip_labels` (a dining nook typed living). door_width:
    `element_classes` ["door"], only the doors that meet a room of `room_types` (every door when
    empty) and none of `not_room_types`. A takeoff rule may name types or classes (for the
    screen)."""

    room_types: tuple[RoomType, ...] = ()
    element_classes: tuple[ElementClass, ...] = ()
    not_room_types: tuple[RoomType, ...] = ()
    skip_labels: tuple[str, ...] = ()  # compared as the takeoff compares names: case, spaces
    note: str | None = None  # which buildings or rooms, exceptions, as a person reads it


class CodeRule(Frozen):
    id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]*$")
    title: str = Field(min_length=1)
    op: Op
    applies_to: AppliesTo = AppliesTo()
    comparison: Comparison
    limit: float = Field(ge=0)
    unit: CheckUnit
    key: str | None = Field(default=None, min_length=1)  # takeoff: the takeoff key it reads
    clause: Clause

    @model_validator(mode="after")
    def _fits_its_op(self) -> "CodeRule":
        applies = self.applies_to
        if self.op in ROOM_OPS and (
            not applies.room_types or applies.element_classes or applies.not_room_types
        ):
            raise ValueError(f"rule {self.id}: {self.op} applies to room_types only")
        if self.op == "door_width" and applies.element_classes != ("door",):
            raise ValueError(f"rule {self.id}: door_width applies to element_classes [door]")
        if self.op not in ROOM_OPS and applies.skip_labels:
            raise ValueError(f"rule {self.id}: skip_labels is for the room ops")
        if self.op != "door_width" and applies.not_room_types:
            raise ValueError(f"rule {self.id}: not_room_types is for door_width")
        if (self.op == "takeoff") != (self.key is not None):
            raise ValueError(f"rule {self.id}: a key is for the takeoff op, and it needs one")
        unit = UNIT_OF_OP.get(self.op) or _unit_of_key(self.key or "")
        if self.unit != unit:
            raise ValueError(f"rule {self.id}: {self.op} {self.key or ''} is in {unit}")
        # The symbol bounds a door's clear opening from above only (check.DOOR_FRAME_M)
        if self.op == "door_width" and self.comparison not in (">=", ">"):
            raise ValueError(f"rule {self.id}: door_width checks a minimum (>= or >)")
        return self


def _unit_of_key(key: str) -> CheckUnit | None:
    """The unit of a takeoff key (app/core/pipeline/takeoff.py quantity_key); None: a measure
    no check compares (a volume, a text)."""
    measure = key.split("|")[0].split(":")[0]
    units: dict[str, CheckUnit] = {"area": "m2", "length": "m"}
    if measure in units:
        return units[measure]
    return None if measure in ("volume", "text") else "count"


class RulePack(Frozen):
    id: str = Field(pattern=r"^[a-z][a-z0-9-]*$")
    country: str = Field(pattern=r"^[A-Z]{2}$")  # ISO 3166-1 alpha-2, for the flag
    country_name: str = Field(min_length=1)  # "Finland"
    name: str = Field(min_length=1)  # the pack's display name
    law: str = Field(min_length=1)
    version: str = Field(min_length=1)
    # What a fail means under this law, one sentence put after each fail's why and shown next to
    # NOTE: "It would not meet today's rule for a new building." None: nothing to add
    fail_means: str | None = Field(default=None, min_length=1)
    rules: tuple[CodeRule, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _unique_ids(self) -> "RulePack":
        ids = [rule.id for rule in self.rules]
        if len(set(ids)) != len(ids):
            raise ValueError(f"pack {self.id}: rule ids repeat")
        return self


class CheckMark(Frozen):
    """An item a result is about, drawn on its page. subject: the room or door checked; counted:
    what was counted for it (a room's windows)."""

    page: int = Field(ge=1)
    box: Box
    polygon: Polygon | None = None
    ref: str | None = None  # the element or room id in the drawing model
    label: str | None = None
    role: Literal["subject", "counted"]
    # The takeoff row this item is a mark of (Row.key) and its MarkView.id there; None when the
    # takeoff has no row with it
    quantity: str | None = None
    mark_id: str | None = None


class CheckSubject(Frozen):
    kind: Literal["room", "element", "sheet"]
    ref: str | None  # the room or element id; None for the sheet
    label: str


class CheckResult(Frozen):
    """One rule on one room, door or sheet. `value`: what was measured, in the takeoff's units;
    None when nothing was (cannot tell); a value too uncertain to judge is kept, with cannot tell.
    `quantity`: the takeoff row of the subject (Row.key), for the surveyor's view; None: none."""

    id: str  # <rule id>:<subject ref>, the same on every call for the same drawing
    rule_id: str
    status: CheckStatus
    subject: CheckSubject
    value: float | None
    limit: float
    unit: CheckUnit
    comparison: Comparison
    comparison_text: str  # COMPARISON_TEXT
    why: str  # one plain sentence
    quantity: str | None
    marks: tuple[CheckMark, ...]


class RuleCheck(Frozen):
    """One rule on one drawing: fail when a result fails, else cannot tell when one is, else
    pass. With no results: cannot tell when the drawing could not be checked (what the rule needs
    was not read), not_applicable when it has nothing the rule applies to."""

    rule_id: str
    title: str
    status: RuleStatus
    why: str
    clause: Clause
    results: tuple[CheckResult, ...]

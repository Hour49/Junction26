"""The drawing model: one drawing file with its pages, scale, plans, elements and rooms.

It serialises as extraction_v1 (docs/decisions/0004-extraction-format.md, with the optional
`tables` and `conflicts` of its 2026-11-13 amendment): the field names and the value lists are that
format's, so app/adapters/extraction_v1.py only adds the envelope (`schema`, `split`, `truth`).
Positions are fractions of the page as rendered, origin top left.

Field ranges are checked here. The format's cross-field rules (a `scaled` scale has a value, ids
are unique, a plan an element names is listed) are checked by `stoa_eval validate-extraction`.
"""

from typing import Annotated, Literal, get_args

from pydantic import AfterValidator, ConfigDict, Field

from app.core.model import Frozen

ElementClass = Literal[
    "door", "window", "toilet", "sink", "shower", "bathtub", "sauna_stove", "stair", "wall",
    "column", "beam", "slab", "railing", "furniture",
]  # fmt: skip
RoomType = Literal[
    "bedroom", "kitchen", "bathroom", "wc", "sauna", "balcony", "living", "hall", "storage",
    "outdoor", "shaft", "other",
]  # fmt: skip
ScaleStatus = Literal["scaled", "no_scale", "not_to_scale", "estimated"]
ScaleEvidence = Literal[
    "scale_text", "scale_bar", "printed_areas", "dimension_lines", "not_to_scale_note"
]
ConflictQuantity = Literal[
    "room_area", "apartment_area", "floor_area", "room_count", "element_count", "scale",
    "storey_count", "other",
]  # fmt: skip
MeasureMethod = Literal[
    "printed_label", "printed_total", "polygon_x_scale", "summed_rooms", "scale_text", "scale_bar",
    "dimension_lines", "ifc_model", "plan_drawing", "schedule", "detector", "parser", "annotation",
    "other",
]  # fmt: skip
ELEMENT_CLASSES: tuple[ElementClass, ...] = get_args(ElementClass)
ROOM_TYPES: tuple[RoomType, ...] = get_args(RoomType)
PLAN = "plan"
# Every count a drawing can give, keyed as extraction_v1 `counts`: a class, room:<type>, or plan.
COUNT_KEYS: tuple[str, ...] = (*ELEMENT_CLASSES, *(f"room:{kind}" for kind in ROOM_TYPES), PLAN)

Fraction = Annotated[float, Field(ge=0.0, le=1.0)]
Attr = str | int | float | bool | None


def _ordered(box: tuple[float, float, float, float]) -> tuple[float, float, float, float]:
    x0, y0, x1, y1 = box
    if x0 > x1 or y0 > y1:
        raise ValueError(f"box {list(box)} needs x0 <= x1 and y0 <= y1")
    return box


Box = Annotated[tuple[Fraction, Fraction, Fraction, Fraction], AfterValidator(_ordered)]
Polygon = Annotated[tuple[tuple[Fraction, Fraction], ...], Field(min_length=3)]


class Page(Frozen):
    page: int = Field(ge=1)
    width: float = Field(gt=0)
    height: float = Field(gt=0)
    unit: Literal["px", "pt"]


class Scale(Frozen):
    """The sheet's scale. `no_scale`: no scale evidence on the sheet; `not_to_scale`: the sheet
    says so; `estimated`: a best-effort value with its `uncertainty` and the method in `source`."""

    status: ScaleStatus
    m_per_unit: float | None = Field(default=None, gt=0)  # metres per page unit (px or pt)
    evidence: tuple[ScaleEvidence, ...] = ()
    text: str | None = None  # the printed scale, e.g. 1:100
    source: str | None = None  # how the value was derived, in words
    uncertainty: float | None = Field(default=None, gt=0)
    reference_m_per_unit: float | None = Field(default=None, gt=0)  # gold only


class Plan(Frozen):
    id: str = Field(min_length=1)
    page: int = Field(ge=1)
    box: Box
    storey: int | str | None = None


class Element(Frozen):
    model_config = ConfigDict(validate_by_name=True)

    id: str = Field(min_length=1)
    class_: ElementClass = Field(validation_alias="class", serialization_alias="class")
    page: int = Field(ge=1)
    plan: str | None = None
    box: Box
    polygon: Polygon | None = None
    attrs: dict[str, Attr] = Field(default_factory=dict[str, Attr])


class Room(Frozen):
    id: str = Field(min_length=1)
    type: RoomType
    label: str | None = None  # the text written in the room, raw
    page: int = Field(ge=1)
    plan: str | None = None
    polygon: Polygon | None = None
    box: Box
    area_m2: float | None = Field(default=None, ge=0)
    apartment: str | None = None
    outdoor: bool = False
    attrs: dict[str, Attr] = Field(default_factory=dict[str, Attr])


class Apartment(Frozen):
    id: str = Field(min_length=1)
    label: str | None = None
    area_m2: float | None = Field(default=None, ge=0)


class TableRow(Frozen):
    cells: tuple[str | None, ...]  # one per column, as printed; None when empty
    box: Box | None = None


class Table(Frozen):
    """A schedule printed on the sheet (door, window, hardware, finish, room schedules)."""

    id: str = Field(min_length=1)
    page: int = Field(ge=1)
    box: Box
    title: str | None = None
    columns: tuple[str, ...] = Field(min_length=1)  # header text, left to right
    rows: tuple[TableRow, ...]


class Subject(Frozen):
    """What a measured quantity is about: a room or apartment id of this drawing, an element
    class, or the whole sheet (`ref` None)."""

    kind: Literal["room", "apartment", "class", "sheet"]
    ref: str | None


class MeasuredValue(Frozen):
    value: float
    unit: str | None = None
    method: MeasureMethod
    page: int | None = Field(default=None, ge=1)
    box: Box | None = None


class Resolution(Frozen):
    rule: str = Field(min_length=1)
    value: float


class Conflict(Frozen):
    """One quantity that two independent methods measured (ingest stage 8), agreeing or not.
    Both values are kept; `resolution` is the value to report when a rule decides, else None."""

    id: str = Field(min_length=1)
    quantity: ConflictQuantity
    subject: Subject
    status: Literal["conflict", "agree"]
    tolerance: float = Field(ge=0)  # relative; 0 for counts
    values: tuple[MeasuredValue, ...] = Field(min_length=2)
    resolution: Resolution | None = None
    note: str | None = None


class Mark(Frozen):
    """Where one counted item is on the drawing: the proof shown with an answer."""

    page: int = Field(ge=1)
    box: Box


class Drawing(Frozen):
    file: str  # the path as the dataset's questions.jsonl gives it
    pages: tuple[Page, ...] = Field(min_length=1)
    scale: Scale
    plans: tuple[Plan, ...] = ()
    elements: tuple[Element, ...] = ()
    rooms: tuple[Room, ...] = ()
    apartments: tuple[Apartment, ...] = ()
    # Totals from a source that gives no items behind them (extraction_v1 `truth: counts`). A key
    # that is missing is unknown, not zero.
    counts: dict[str, Annotated[int, Field(ge=0)]] | None = None
    tables: tuple[Table, ...] | None = None  # None: no schedule was looked for
    conflicts: tuple[Conflict, ...] | None = None  # None: nothing was measured a second way
    notes: tuple[str, ...] = ()

    def marks_by_quantity(self) -> dict[str, tuple[Mark, ...]]:
        """Per count key, where each listed item is. Every key of COUNT_KEYS is present, so a
        class the drawing lists nothing of counts 0."""
        marks: dict[str, list[Mark]] = {key: [] for key in COUNT_KEYS}
        for plan in self.plans:
            marks[PLAN].append(Mark(page=plan.page, box=plan.box))
        for element in self.elements:
            marks[element.class_].append(Mark(page=element.page, box=element.box))
        for room in self.rooms:
            marks[f"room:{room.type}"].append(Mark(page=room.page, box=room.box))
        return {key: tuple(found) for key, found in marks.items()}

"""The drawing model: one drawing file with its pages, scale, plans, elements and rooms.

It serialises as extraction_v1 (docs/decisions/0004-extraction-format.md, with the optional
`tables`, `conflicts` and `read` of its 2026-11-13 amendments and `model_objects` of 2026-11-14):
the field names and the value lists are that format's (eval/stoa_eval/extraction.py), so
app/adapters/extraction_v1.py only adds the envelope (`schema`, `split`, `truth`). Positions are
fractions of the page as rendered, origin top left.

Field ranges are checked here. The format's cross-field rules (a `scaled` scale has a value, ids
are unique, a plan an element names is listed) are checked by `stoa_eval validate-extraction`.
"""

from typing import Annotated, Literal, get_args

from pydantic import AfterValidator, ConfigDict, Field, model_validator

from app.core.model import Frozen

ElementClass = Literal[
    "door", "window", "toilet", "sink", "shower", "bathtub", "sauna_stove", "stair", "wall",
    "column", "beam", "slab", "railing", "furniture",
]  # fmt: skip
RoomType = Literal[
    "bedroom", "kitchen", "bathroom", "wc", "sauna", "balcony", "living", "hall", "storage",
    "outdoor", "shaft", "other",
]  # fmt: skip


def words(kind: str) -> str:
    """An element class, room type or combined count as a person reads it: "sauna_stove" is
    "sauna stove", "shower+bathtub" is "shower and bathtub"."""
    return kind.replace("_", " ").replace("+", " and ")


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
ReadClass = ElementClass | Literal["room"]  # what an extraction can say it looked for
ModelClass = ElementClass | Literal["space"]  # what a building model's object can be
# A model object's own quantities. area_m2: a space's net floor area; side_area_m2: one wall face.
QuantityKey = Literal["length_m", "height_m", "width_m", "area_m2", "side_area_m2", "volume_m3"]
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
    # How the area was got. exact: the sheet prints it (unset counts as exact); estimated: the
    # outline at a measured or an estimated scale, with its relative uncertainty.
    area_status: Literal["exact", "estimated"] | None = None
    area_source: Literal["printed", "geometry_x_scale", "geometry_x_estimate"] | None = None
    area_uncertainty: float | None = Field(default=None, gt=0)
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
    key_column: int = Field(default=0, ge=0)  # the 0-based column that identifies a row
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


class ModelObject(Frozen):
    """One object a building model lists, whether this sheet draws it or not (`model_objects`).
    `element`: the id of the Element this sheet draws it as, or of the Room for a space; None:
    not drawn here. `quantities` are the model's own, in metres."""

    model_config = ConfigDict(validate_by_name=True)

    id: str = Field(min_length=1)  # unique in the drawing, and no element's or room's id
    class_: ModelClass = Field(validation_alias="class", serialization_alias="class")
    storey: str | None = None  # as the model names it
    global_id: str | None = None
    name: str | None = None
    long_name: str | None = None
    quantities: dict[QuantityKey, Annotated[float, Field(ge=0)]] = Field(
        default_factory=dict[QuantityKey, float]
    )
    element: str | None = None
    attrs: dict[str, Attr] = Field(default_factory=dict[str, Attr])


class Mark(Frozen):
    """Where one counted item is on the drawing: the proof shown with an answer."""

    page: int = Field(ge=1)
    box: Box


class ReaderView(Frozen):
    """What one double-check reader saw on the sheet (DOUBLE_CHECK_READERS). None of it is
    counted: it is set against the counted marks to find the places a person should look at
    again (app/core/pipeline/disputed_marks.py)."""

    read: tuple[ElementClass, ...]  # the classes it looked for; of another it says nothing
    elements: tuple[Element, ...] = ()


def _absent(value: object) -> bool:
    return value is None


class Drawing(Frozen):
    file: str  # the path as the dataset's questions.jsonl gives it
    pages: tuple[Page, ...]  # none only for a model file, which has objects and no page
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
    # The element classes, and "room", that were looked for. None: all of them (every gold file).
    # A class left out was not read, so its count is unknown, not 0.
    read: tuple[ReadClass, ...] | None = None
    # Every object of the building model behind the drawing, all storeys, drawn here or not.
    # None: the drawing has no model. Sums over a storey and counts "in the model" read this;
    # what the sheet shows is `elements` and `rooms`.
    model_objects: tuple[ModelObject, ...] | None = None
    # What each double-check reader saw, by the reader's name. None: none ran, and then no dump
    # has the field, so a drawing without readers is written exactly as before there were any.
    double_check: dict[str, ReaderView] | None = Field(default=None, exclude_if=_absent)
    notes: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _a_page_or_a_model(self) -> "Drawing":
        if not self.pages and not self.model_objects:
            raise ValueError("pages: a drawing has a page, unless it is a model file's objects")
        return self

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

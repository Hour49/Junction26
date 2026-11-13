"""extraction_v1: what the pipeline writes for each drawing file, and the shape of the extraction
gold (`data/stoa/extraction_gold/<source>/<file stem>.json`). Decision record:
docs/decisions/0004-extraction-format.md (amended 2026-11-13: optional `tables` for schedule sheets,
`truth: "tables"`, and optional `conflicts` from ingestion stage 8; formats-v1-1 brief; estimated
scales and room areas; optional `read`, golden-7f brief; optional `model_objects`, formats v1.2).

Coordinates are fractions of the page as rendered (after any PDF /Rotate), origin top left, the same
frame as answer_v1 evidence. Extra keys are refused everywhere, so a typo fails loudly.
"""

from typing import Annotated, Literal, Self

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, StrictFloat, model_validator

ElementClass = Literal[
    "door", "window", "toilet", "sink", "shower", "bathtub", "sauna_stove", "stair", "wall",
    "column", "beam", "slab", "railing", "furniture",
]  # fmt: skip
RoomType = Literal[
    "bedroom", "kitchen", "bathroom", "wc", "sauna", "balcony", "living", "hall", "storage",
    "outdoor", "shaft", "other",
]  # fmt: skip
ELEMENT_CLASSES: frozenset[str] = frozenset(ElementClass.__args__)
ROOM_TYPES: frozenset[str] = frozenset(RoomType.__args__)
Fraction = Annotated[float, Field(ge=0.0, le=1.0)]
Attr = str | int | float | bool | None


def _ordered(box: tuple[float, float, float, float]) -> tuple[float, float, float, float]:
    x0, y0, x1, y1 = box
    if x0 > x1 or y0 > y1:
        raise ValueError(f"box {list(box)} needs x0 <= x1 and y0 <= y1")
    return box


Box = Annotated[
    tuple[Fraction, Fraction, Fraction, Fraction],
    AfterValidator(_ordered),
    Field(description="[x0, y0, x1, y1] as page fractions, origin top left"),
]
Polygon = Annotated[list[tuple[Fraction, Fraction]], Field(min_length=3)]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Page(_Strict):
    page: int = Field(ge=1)
    width: float = Field(gt=0)
    height: float = Field(gt=0)
    unit: Literal["px", "pt"]


ScaleStatus = Literal["scaled", "no_scale", "not_to_scale", "estimated"]
ScaleEvidence = Literal[
    "scale_text", "scale_bar", "printed_areas", "dimension_lines", "not_to_scale_note"
]  # fmt: skip


class Scale(_Strict):
    """The sheet's scale and every kind of scale evidence it shows (Bogdan, 2026-11-13 22:31), and
    on every image a value to get areas from, approximated where nothing is printed (Bogdan, 23:33:
    "We should have ON ALL IMAGES THE SCALE TO GET THE AREA, BY APROXIMATING IT IN DIFFERENT WAYS
    IF NOT GOOD SCALE ETC.")."""

    status: ScaleStatus = Field(
        description="scaled (measured, two checks); estimated (approximated without usable printed "
        "evidence); not_to_scale (the sheet says so; may still carry an approximate value); "
        "no_scale (no method applies)"
    )
    m_per_unit: float | None = Field(
        default=None,
        gt=0,
        description="metres per page unit (px or pt): scaled and estimated; optional on "
        "not_to_scale",
    )
    evidence: list[ScaleEvidence] = Field(
        default_factory=list[ScaleEvidence], description="every kind visible on the sheet"
    )
    text: str | None = Field(default=None, description="the printed scale, e.g. 1:100")
    source: str | None = Field(default=None, description="how the value was derived, in words")
    uncertainty: float | None = Field(
        default=None, gt=0, description="relative, e.g. 0.08: estimated and a valued not_to_scale"
    )
    reference_m_per_unit: float | None = Field(
        default=None, gt=0, description="a reference unit (e.g. the annotation's), not truth"
    )

    @model_validator(mode="after")
    def _status_fits(self) -> Self:
        problems: list[str] = []
        needs_value = self.status in ("scaled", "estimated")
        if needs_value and self.m_per_unit is None:
            problems.append(f"m_per_unit is required when {self.status}")
        if self.status == "no_scale" and self.m_per_unit is not None:
            problems.append("m_per_unit is null when no_scale")
        approximate = self.status == "estimated" or (
            self.status == "not_to_scale" and self.m_per_unit is not None
        )
        if len(set(self.evidence)) != len(self.evidence):
            problems.append("evidence lists a kind twice")
        if self.status == "scaled" and not self.evidence:
            problems.append("scaled needs the evidence it was read from")
        if self.status == "no_scale" and self.evidence:
            problems.append("no_scale has no evidence")
        if self.status == "not_to_scale" and "not_to_scale_note" not in self.evidence:
            problems.append("not_to_scale lists not_to_scale_note in evidence")
        if approximate and (self.uncertainty is None or not self.source):
            problems.append(f"an approximate {self.status} value needs uncertainty and source")
        if not approximate and self.uncertainty is not None:
            problems.append("uncertainty is for an approximate value (estimated, not_to_scale)")
        if self.status == "scaled" and self.reference_m_per_unit is not None:
            problems.append("reference_m_per_unit is not for scaled")
        if problems:
            raise ValueError("scale: " + "; ".join(problems))
        return self


class Plan(_Strict):
    id: str = Field(min_length=1)
    page: int = Field(ge=1)
    box: Box
    storey: int | str | None = Field(default=None, description="storey number or name, when known")


class Element(_Strict):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    id: str = Field(min_length=1)
    class_: ElementClass = Field(alias="class")
    page: int = Field(ge=1)
    plan: str | None = None
    box: Box
    polygon: Polygon | None = None
    attrs: dict[str, Attr] = Field(
        default_factory=dict[str, Attr],
        description="source_class; IFC also global_id, storey; multiplicity (int >= 1) when the "
        "source draws this element several times at identical geometry",
    )

    @model_validator(mode="after")
    def _multiplicity(self) -> Self:
        value = self.attrs.get("multiplicity", 1)
        if isinstance(value, bool) or not isinstance(value, int) or value < 1:
            raise ValueError(f"element {self.id}: attrs.multiplicity must be an int >= 1")
        return self

    @property
    def multiplicity(self) -> int:
        value = self.attrs.get("multiplicity", 1)
        return value if isinstance(value, int) else 1


class Room(_Strict):
    id: str = Field(min_length=1)
    type: RoomType
    label: str | None = Field(default=None, description="the text written in the room, raw")
    page: int = Field(ge=1)
    plan: str | None = None
    polygon: Polygon | None = None
    box: Box
    area_m2: float | None = Field(default=None, ge=0)
    area_status: Literal["exact", "estimated"] | None = Field(
        default=None, description="exact: the sheet prints it; unset counts as exact (swiss, ifc)"
    )
    area_source: Literal["printed", "geometry_x_scale", "geometry_x_estimate"] | None = None
    area_uncertainty: float | None = Field(default=None, gt=0, description="estimated: relative")
    apartment: str | None = None
    outdoor: bool = False
    attrs: dict[str, Attr] = Field(default_factory=dict[str, Attr])

    @model_validator(mode="after")
    def _area_fits(self) -> Self:
        problems: list[str] = []
        if (self.area_status or self.area_source) and self.area_m2 is None:
            problems.append("area_status and area_source describe an area_m2")
        if self.area_source is not None and self.area_status is None:
            problems.append("area_source needs area_status")
        if (self.area_status == "estimated") != (self.area_uncertainty is not None):
            problems.append("area_uncertainty is set exactly on estimated areas")
        if self.area_source and (self.area_source == "printed") != (self.area_status == "exact"):
            problems.append("a printed area is exact, and an exact area is printed")
        if problems:
            raise ValueError(f"room {self.id}: " + "; ".join(problems))
        return self


class Apartment(_Strict):
    id: str = Field(min_length=1)
    label: str | None = None
    area_m2: float | None = Field(default=None, ge=0)


class TableRow(_Strict):
    cells: list[str | None] = Field(description="one per column, as printed; null when empty")
    box: Box | None = None


class Table(_Strict):
    """A schedule printed on the sheet (door, window, hardware, finish, room schedules)."""

    id: str = Field(min_length=1)
    page: int = Field(ge=1)
    box: Box
    title: str | None = None
    columns: list[str] = Field(min_length=1, description="header text, left to right")
    key_column: int = Field(default=0, ge=0, description="0-based column that identifies a row")
    rows: list[TableRow]

    @model_validator(mode="after")
    def _rows_fit(self) -> Self:
        bad = [n for n, row in enumerate(self.rows, 1) if len(row.cells) != len(self.columns)]
        if bad:
            raise ValueError(
                f"table {self.id}: rows {bad[:5]} do not have {len(self.columns)} cells"
            )
        if self.key_column >= len(self.columns):
            raise ValueError(f"table {self.id}: key_column {self.key_column} is not a column")
        return self


ConflictQuantity = Literal[
    "room_area", "apartment_area", "floor_area", "room_count", "element_count", "scale",
    "storey_count", "other",
]  # fmt: skip
ConflictMethod = Literal[
    "printed_label", "printed_total", "polygon_x_scale", "summed_rooms", "scale_text", "scale_bar",
    "dimension_lines", "ifc_model", "plan_drawing", "schedule", "detector", "parser", "annotation",
    "other",
]  # fmt: skip


class Subject(_Strict):
    kind: Literal["room", "apartment", "class", "sheet"]
    ref: str | None = Field(
        description="a room or apartment id in this file, an element class, or null for sheet"
    )


class MeasuredValue(_Strict):
    value: float
    unit: str | None = None
    method: ConflictMethod
    page: int | None = Field(default=None, ge=1)
    box: Box | None = None


class Resolution(_Strict):
    rule: str = Field(min_length=1)
    value: float


class Conflict(_Strict):
    """One quantity two independent methods measured on this file (ingestion stage 8)."""

    id: str = Field(min_length=1)
    quantity: ConflictQuantity
    subject: Subject
    status: Literal["conflict", "agree"]
    tolerance: float = Field(ge=0, description="relative; 0 for counts")
    values: list[MeasuredValue] = Field(min_length=2)
    resolution: Resolution | None = Field(
        default=None, description="the value to report and the rule; null when no rule decides"
    )
    note: str | None = None

    @model_validator(mode="after")
    def _well_formed(self) -> Self:
        methods = [value.method for value in self.values]
        if len(set(methods)) != len(methods):
            raise ValueError(f"conflict {self.id}: each value needs a different method")
        if (self.subject.kind == "sheet") != (self.subject.ref is None):
            raise ValueError(f"conflict {self.id}: subject ref is null for a sheet, else set")
        if self.subject.kind == "class" and self.subject.ref not in ELEMENT_CLASSES:
            raise ValueError(f"conflict {self.id}: {self.subject.ref!r} is not an element class")
        return self


QuantityKey = Literal["length_m", "height_m", "width_m", "area_m2", "side_area_m2", "volume_m3"]
Quantity = Annotated[StrictFloat, Field(ge=0, allow_inf_nan=False)]


class ModelObject(_Strict):
    """One object of the BIM model the sheet comes from, drawn on this sheet or not (formats v1.2,
    2026-11-14): storey sums and counts "in the model" need every object."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    id: str = Field(min_length=1, description="unique in the file, not an element or room id")
    class_: ElementClass | Literal["space"] = Field(alias="class")
    storey: str | None = Field(
        default=None, description="IfcBuildingStorey.Name, as the model has it"
    )
    global_id: str | None = None
    name: str | None = Field(default=None, description="the object's Name, raw")
    long_name: str | None = Field(default=None, description="an IfcSpace LongName, raw")
    quantities: dict[QuantityKey, Quantity] = Field(
        default_factory=dict[QuantityKey, Quantity],
        description="area_m2 on a space: net floor area as the dataset defines it; side_area_m2: "
        "one face of a wall",
    )
    element: str | None = Field(
        default=None,
        description="the drawn element on this sheet (a room, for a space); null: not drawn here",
    )
    attrs: dict[str, Attr] = Field(default_factory=dict[str, Attr])


def _count_key_ok(key: str) -> bool:
    kind, _, room_type = key.partition(":")
    return key == "plan" or key in ELEMENT_CLASSES or (kind == "room" and room_type in ROOM_TYPES)


class Extraction(_Strict):
    """One drawing file: its pages, plans, elements, rooms, apartments and, optionally, its
    schedules, stage-8 conflicts and the objects of its BIM model (extraction_v1)."""

    model_config = ConfigDict(extra="forbid", title="Extraction_v1")

    schema_: Literal["extraction_v1"] = Field(alias="schema")
    file: str = Field(pattern=r"^data/[^/]+/.+", description="the path as in questions.jsonl")
    split: Literal["dev", "eval"]
    truth: Literal["elements", "counts", "tables"] = Field(
        description="elements: full element and room lists; counts: only `counts` is scored; "
        "tables: a schedule sheet, only `tables` is scored"
    )
    pages: list[Page] = Field(
        description="at least one, except on an .ifc file read as a model: there [] with "
        "model_objects, and empty plans, elements and rooms"
    )
    scale: Scale
    plans: list[Plan]
    elements: list[Element]
    rooms: list[Room]
    apartments: list[Apartment] = Field(default_factory=list[Apartment])
    counts: dict[str, Annotated[int, Field(ge=0)]] | None = Field(
        default=None, description="keys: an element class, room:<type>, or plan"
    )
    tables: list[Table] | None = Field(default=None, description="schedules a question can ask")
    conflicts: list[Conflict] | None = Field(
        default=None, description="quantities measured by two methods, agreeing or not"
    )
    read: list[ElementClass | Literal["room"]] | None = Field(
        default=None,
        description="the element classes, and room, this extraction looked for; null: everything "
        "its truth covers. A class left out was not read: its count is unknown, not 0",
    )
    model_objects: list[ModelObject] | None = Field(
        default=None,
        description="every object of the BIM model the file comes from, all storeys, drawn here "
        "or not; null: the source has no model",
    )
    notes: list[str] = Field(default_factory=list[str])

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        problems: list[str] = []
        for name, ids in (
            ("page", [str(page.page) for page in self.pages]),
            ("plan", [plan.id for plan in self.plans]),
            ("element", [element.id for element in self.elements]),
            ("room", [room.id for room in self.rooms]),
            ("apartment", [apartment.id for apartment in self.apartments]),
            ("table", [table.id for table in self.tables or []]),
            ("conflict", [conflict.id for conflict in self.conflicts or []]),
            ("model object", [item.id for item in self.model_objects or []]),
        ):
            repeated = sorted({i for i in ids if ids.count(i) > 1})
            if repeated:
                problems.append(f"repeated {name} ids {repeated[:5]}")
        pages = {page.page for page in self.pages}
        plans = {plan.id for plan in self.plans}
        apartments = {apartment.id for apartment in self.apartments}
        located = (("plan", self.plans), ("element", self.elements), ("room", self.rooms),
                   ("table", self.tables or []))  # fmt: skip
        for kind, items in located:
            for item in items:
                if item.page not in pages:
                    problems.append(f"{kind} {item.id} is on page {item.page}, not in pages")
        for kind, items in (("element", self.elements), ("room", self.rooms)):
            for item in items:
                if item.plan is not None and item.plan not in plans:
                    problems.append(f"{kind} {item.id} names plan {item.plan!r}, not in plans")
        for room in self.rooms:
            if room.apartment is not None and room.apartment not in apartments:
                problems.append(f"room {room.id} names apartment {room.apartment!r}, not listed")
        if self.truth == "counts" and self.counts is None:
            problems.append("truth: counts needs a counts object")
        if self.truth == "tables" and (not self.tables or self.elements or self.rooms):
            problems.append("truth: tables needs tables, with empty elements and rooms")
        rooms = {room.id for room in self.rooms}
        for conflict in self.conflicts or []:
            ref, kind = conflict.subject.ref, conflict.subject.kind
            listed = rooms if kind == "room" else apartments
            if kind in ("room", "apartment") and ref not in listed:
                problems.append(f"conflict {conflict.id} names {kind} {ref!r}, not listed")
            for value in conflict.values:
                if value.page is not None and value.page not in pages:
                    problems.append(f"conflict {conflict.id} has a value on page {value.page}")
        twice = sorted({name for name in self.read or [] if (self.read or []).count(name) > 1})
        if twice:
            problems.append(f"read lists {twice} twice")
        bad_keys = sorted(key for key in self.counts or {} if not _count_key_ok(key))
        if bad_keys:
            problems.append(f"counts keys {bad_keys} are not a class, room:<type> or plan")
        problems += self._model_problems()
        if problems:
            raise ValueError("; ".join(problems[:10]))
        return self

    def _model_problems(self) -> list[str]:
        problems: list[str] = []
        objects = self.model_objects or []
        if not self.pages:
            if not (objects and self.file.endswith(".ifc")):
                problems.append(
                    "pages needs at least 1 page, unless an .ifc file has model_objects"
                )
            if self.plans or self.elements or self.rooms:
                problems.append("a file without pages has empty plans, elements and rooms")
        elements = {element.id: element.class_ for element in self.elements}
        rooms = {room.id for room in self.rooms}
        clash = sorted({item.id for item in objects} & (elements.keys() | rooms))
        if clash:
            problems.append(f"model object ids {clash[:5]} are also element or room ids")
        seen: set[tuple[bool, str]] = set()
        for item in objects:
            if item.element is None:
                continue
            space = item.class_ == "space"
            if space and item.element not in rooms:
                problems.append(f"model object {item.id} names room {item.element!r}, not listed")
            elif not space and item.element not in elements:
                problems.append(
                    f"model object {item.id} names element {item.element!r}, not listed"
                )
            elif not space and elements[item.element] != item.class_:
                problems.append(
                    f"model object {item.id} is a {item.class_}, element {item.element} a "
                    f"{elements[item.element]}"
                )
            if (space, item.element) in seen:
                problems.append(f"{'room' if space else 'element'} {item.element} is named twice")
            seen.add((space, item.element))
        return problems

    def strict_v2_problems(self) -> list[str]:
        """Why this file falls short of golden v2's rule that every image has a scale and every
        room an area (Bogdan, 2026-11-13 23:33); empty when it doesn't. A schedule sheet
        (truth tables) has no plan to measure, and an .ifc file without pages has no image."""
        if self.truth == "tables" or not self.pages:
            return []
        problems: list[str] = []
        if self.scale.m_per_unit is None:
            problems.append(f"scale {self.scale.status} has no m_per_unit")
        if any(note.lower().startswith("scale not reviewed") for note in self.notes):
            problems.append('a note still says "scale not reviewed"')
        bare = [room.id for room in self.rooms if room.polygon and room.area_m2 is None]
        if bare:
            problems.append(f"{len(bare)} rooms with a polygon have no area_m2 (first {bare[0]})")
        return problems

    def derived_counts(self, multiplicity: bool = False) -> dict[str, int]:
        """Counts from the lists, keyed like `counts`: element classes, room:<type>, plan. With
        `multiplicity`, an element counts attrs.multiplicity times."""
        counts: dict[str, int] = {"plan": len(self.plans)}
        for element in self.elements:
            weight = element.multiplicity if multiplicity else 1
            counts[element.class_] = counts.get(element.class_, 0) + weight
        for room in self.rooms:
            key = f"room:{room.type}"
            counts[key] = counts.get(key, 0) + 1
        return counts

"""extraction_v1: what the pipeline writes for each drawing file, and the shape of the extraction
gold (`data/stoa/extraction_gold/<source>/<file stem>.json`). Decision record:
docs/decisions/0004-extraction-format.md.

Coordinates are fractions of the page as rendered (after any PDF /Rotate), origin top left, the same
frame as answer_v1 evidence. Extra keys are refused everywhere, so a typo fails loudly.
"""

from typing import Annotated, Literal, Self

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, model_validator

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
    """The sheet's scale and every kind of scale evidence it shows (Bogdan, 2026-11-13 22:31)."""

    status: ScaleStatus = Field(
        description="scaled; no_scale (no scale evidence at all); not_to_scale (the sheet says "
        "so); estimated (predictions only: a best-effort scale without printed evidence)"
    )
    m_per_unit: float | None = Field(
        default=None, gt=0, description="metres per page unit (px or pt); scaled and estimated"
    )
    evidence: list[ScaleEvidence] = Field(
        default_factory=list[ScaleEvidence], description="every kind visible on the sheet"
    )
    text: str | None = Field(default=None, description="the printed scale, e.g. 1:100")
    source: str | None = Field(default=None, description="how the value was derived, in words")
    uncertainty: float | None = Field(
        default=None, gt=0, description="estimated only: relative, e.g. 0.10"
    )
    reference_m_per_unit: float | None = Field(
        default=None, gt=0, description="gold without a scale: a reference for estimates, not truth"
    )

    @model_validator(mode="after")
    def _status_fits(self) -> Self:
        problems: list[str] = []
        has_value = self.status in ("scaled", "estimated")
        if has_value != (self.m_per_unit is not None):
            problems.append(
                f"m_per_unit is {'required' if has_value else 'null'} when {self.status}"
            )
        if len(set(self.evidence)) != len(self.evidence):
            problems.append("evidence lists a kind twice")
        if self.status == "scaled" and not self.evidence:
            problems.append("scaled needs the evidence it was read from")
        if self.status == "no_scale" and self.evidence:
            problems.append("no_scale has no evidence")
        if self.status == "not_to_scale" and "not_to_scale_note" not in self.evidence:
            problems.append("not_to_scale lists not_to_scale_note in evidence")
        if self.status == "estimated" and (self.uncertainty is None or not self.source):
            problems.append("estimated needs uncertainty and source (the method)")
        if self.status != "estimated" and self.uncertainty is not None:
            problems.append("uncertainty is for estimated only")
        if has_value and self.reference_m_per_unit is not None:
            problems.append("reference_m_per_unit is for no_scale and not_to_scale only")
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
    apartment: str | None = None
    outdoor: bool = False
    attrs: dict[str, Attr] = Field(default_factory=dict[str, Attr])


class Apartment(_Strict):
    id: str = Field(min_length=1)
    label: str | None = None
    area_m2: float | None = Field(default=None, ge=0)


def _count_key_ok(key: str) -> bool:
    kind, _, room_type = key.partition(":")
    return key == "plan" or key in ELEMENT_CLASSES or (kind == "room" and room_type in ROOM_TYPES)


class Extraction(_Strict):
    """One drawing file: its pages, plans, elements, rooms and apartments (extraction_v1)."""

    model_config = ConfigDict(extra="forbid", title="Extraction_v1")

    schema_: Literal["extraction_v1"] = Field(alias="schema")
    file: str = Field(pattern=r"^data/[^/]+/.+", description="the path as in questions.jsonl")
    split: Literal["dev", "eval"]
    truth: Literal["elements", "counts"] = Field(
        description="elements: full element and room lists; counts: only `counts` is scored"
    )
    pages: list[Page] = Field(min_length=1)
    scale: Scale
    plans: list[Plan]
    elements: list[Element]
    rooms: list[Room]
    apartments: list[Apartment] = Field(default_factory=list[Apartment])
    counts: dict[str, Annotated[int, Field(ge=0)]] | None = Field(
        default=None, description="keys: an element class, room:<type>, or plan"
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
        ):
            repeated = sorted({i for i in ids if ids.count(i) > 1})
            if repeated:
                problems.append(f"repeated {name} ids {repeated[:5]}")
        pages = {page.page for page in self.pages}
        plans = {plan.id for plan in self.plans}
        apartments = {apartment.id for apartment in self.apartments}
        for kind, items in (("plan", self.plans), ("element", self.elements), ("room", self.rooms)):
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
        bad_keys = sorted(key for key in self.counts or {} if not _count_key_ok(key))
        if bad_keys:
            problems.append(f"counts keys {bad_keys} are not a class, room:<type> or plan")
        if problems:
            raise ValueError("; ".join(problems[:10]))
        return self

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

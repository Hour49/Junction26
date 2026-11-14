"""What an answer's proof shows, per kind of answer (docs/GOLDEN.md "What an answer should show"),
so the screen and `evidence.png` draw the same thing:

- a count: its marks outlined and numbered, one colour per class (`legend`);
- a sum: the parts filled with their values, and the sum written out (`arithmetic`);
- an item the counting rule left out: greyed with its reason (the marks' `excluded` state);
- a fact of the building model: the objects with their GlobalIds (`objects`) and the storey table;
- a schedule: the rows it rests on, with their cells, and how they make the answer (`schedule`).

The colour of a class is fixed (`colour`), so a door is the same colour in every answer.
"""

import zlib
from collections import Counter
from collections.abc import Mapping, Sequence
from typing import Literal

from pydantic import ConfigDict, Field

from app.core.drawing.model import ELEMENT_CLASSES, Box, Drawing, ModelObject, Table
from app.core.model import Frozen
from app.core.pipeline.rules import MODEL_COUNT, MODEL_QUANTITY, MODEL_SPACES
from app.core.pipeline.takeoff import SPACE, normalised
from app.core.review.model import MarkView, Row

# Colour-blind-safe, distinct on a white sheet; the common classes keep theirs, the rest by name
PALETTE = ("#d62728", "#1f77b4", "#2ca02c", "#9467bd", "#ff7f0e", "#17becf", "#8c564b", "#e377c2")
FIXED = {"door": 0, "window": 1, "toilet": 2, "sink": 3, "shower": 4, "bathtub": 5, "stair": 6}
GREY = "#9e9e9e"  # rejected and excluded marks
MODEL_RULES = {MODEL_COUNT.id, MODEL_QUANTITY.id, MODEL_SPACES.id}
ProofKind = Literal["count", "sum", "model", "schedule", "none"]


def colour(name: str) -> str:
    """The fixed colour of a class or room label."""
    at = FIXED.get(name.casefold())
    return PALETTE[at if at is not None else zlib.crc32(name.casefold().encode()) % len(PALETTE)]


class ClassKey(Frozen):
    label: str
    colour: str
    count: int  # its counted marks, and those counted without a mark
    unlocated: int = 0  # counted by a second reader with no position: not drawn
    note: str | None = None  # the legend's words for them, e.g. "2 counted without a mark ..."


class ModelItem(Frozen):
    model_config = ConfigDict(validate_by_name=True)

    id: str
    class_: str = Field(serialization_alias="class", validation_alias="class")
    name: str | None
    storey: str | None
    global_id: str | None


class StoreyRow(Frozen):
    storey: str
    counts: dict[str, int]  # objects of each class on the storey


class ScheduleRow(Frozen):
    n: int
    box: Box
    cells: tuple[str | None, ...]


class Schedule(Frozen):
    table: str
    title: str | None
    page: int
    box: Box
    columns: tuple[str, ...]
    rows: tuple[ScheduleRow, ...]  # the rows the answer rests on
    of: int  # rows the table has


class Proof(Frozen):
    kind: ProofKind
    legend: tuple[ClassKey, ...]
    arithmetic: str | None  # how the parts make the answer, in one line
    objects: tuple[ModelItem, ...] | None  # a fact of the building model: what it counted
    storeys: tuple[StoreyRow, ...] | None  # the model's objects per storey and class
    schedule: Schedule | None
    # How a second, independent method checked the value, in one line; None: measured once
    check: str | None = None


NO_PROOF = Proof(kind="none", legend=(), arithmetic=None, objects=None, storeys=None, schedule=None)
UNLOCATED = "counted without a mark (second reader)"
# What each method that measures a value is, in words, for the check line
METHODS = {
    "plan_drawing": "the sheet",
    "parser": "the sheet",
    "detector": "the detector",
    "ifc_model": "the IFC model",
    "schedule": "the schedule",
    "printed_label": "the printed room areas",
    "polygon_x_scale": "the room outlines at the sheet's scale",
}


def number(value: float) -> str:
    return f"{value:.2f}".rstrip("0").rstrip(".") if value != int(value) else str(int(value))


def legend(
    marks: Sequence[MarkView], fixed: bool = True, unlocated: Mapping[str, int] | None = None
) -> tuple[ClassKey, ...]:
    """One key per class or label among the marks not rejected, with how many are counted.
    `fixed`: each class its own colour (a count); else the palette in order, so the room labels
    of a sum don't share one. `unlocated`: per class, those counted without a mark; they add to
    the class's count and are named in its `note`."""
    without = unlocated or {}
    seen = Counter(mark.label or "added" for mark in marks if mark.state != "rejected")
    seen.update(without)
    counted = Counter(mark.label or "added" for mark in marks if mark.state in ("counted", "added"))
    counted.update(without)
    return tuple(
        ClassKey(
            label=name,
            colour=colour(name) if fixed else PALETTE[at % len(PALETTE)],
            count=counted[name],
            unlocated=without.get(name, 0),
            note=f"{without[name]} {UNLOCATED}" if without.get(name) else None,
        )
        for at, name in enumerate(seen)
    )


def takeoff_proof(found: Row, drawing: Drawing) -> Proof:
    return _takeoff_proof(found, drawing).model_copy(update={"check": check(found)})


def _takeoff_proof(found: Row, drawing: Drawing) -> Proof:
    keys = legend(found.marks, fixed=found.measure == "count", unlocated=found.unlocated)
    if found.rule.id in MODEL_RULES:
        return _model(found, drawing, keys)
    if found.measure == "count":
        if not set(found.subject.split("+")) <= set(ELEMENT_CLASSES):  # rooms: one key, not
            keys = _one_key(found)  # one per printed name
        terms = [f"{key.count} {key.label}" for key in keys if key.count]
        sums = " + ".join(terms) + f" = {number(found.value)}" if len(terms) > 1 else None
        return Proof(
            kind="count", legend=keys, arithmetic=sums, objects=None, storeys=None, schedule=None
        )
    return Proof(
        kind="sum",
        legend=keys,
        arithmetic=_sum(found),
        objects=None,
        storeys=None,
        schedule=None,
    )


def _one_key(found: Row) -> tuple[ClassKey, ...]:
    """A count of rooms (or apartments) in one key, named by what is counted (`bedroom`)."""
    name = found.subject.split(":", 1)[-1].replace("_", " ")
    counted = sum(mark.state in ("counted", "added") for mark in found.marks)
    return (ClassKey(label=name, colour=colour(name), count=counted),)


SHOWN_UNITS = {"m2": "m²", "m3": "m³"}  # the unit as people write it


def _unit(unit: str) -> str:
    return SHOWN_UNITS.get(unit, unit)


def check(found: Row) -> str | None:
    """How a second method checked the value: both values, and the rule that kept one."""
    if found.first is None or found.second is None:
        return None
    unit = "" if found.unit == "count" else f" {_unit(found.unit)}"
    shown = [f"{METHODS.get(v.method, v.method)} {number(v.value)}{unit}"
             for v in (found.first, found.second)]  # fmt: skip
    if found.conflict is None:
        return f"Checked twice, both agree: {shown[0]}, {shown[1]}"
    text = f"Checked twice, they disagree: {shown[0]}, {shown[1]}"
    if found.settled is not None:
        return f"{text}; settled by a person: {number(found.settled.value)}{unit}"
    if (rule := found.conflict.resolution) is not None:
        return f"{text}; kept {number(rule.value)}{unit}: {rule.rule}"
    return f"{text}; no rule decides, a person must settle it"


def _sum(found: Row) -> str | None:
    parts = [mark for mark in found.marks if mark.state in ("counted", "added")]
    if not parts or any(mark.value is None for mark in parts):
        return None
    total = sum(mark.value or 0.0 for mark in parts)
    text = " + ".join(number(mark.value or 0.0) for mark in parts)
    text += f" = {number(total)} {_unit(found.unit)}"
    if abs(total - found.value) > 0.01:
        text += f"; kept: {number(found.value)} {_unit(found.unit)}"
    out = [mark for mark in found.marks if mark.state == "excluded"]
    if out:
        text += "; left out: " + ", ".join(
            f"{mark.label or mark.id} {number(mark.value or 0.0)} ({mark.reason})" for mark in out
        )
    return text


def _model(found: Row, drawing: Drawing, keys: tuple[ClassKey, ...]) -> Proof:
    objects = drawing.model_objects or ()
    wanted = SPACE if found.subject == "room" else found.subject
    scope = found.scope
    named = scope.name is not None or scope.label is not None or scope.apartment is not None
    chosen = [
        item
        for item in objects
        if item.class_ == wanted
        and (scope.storey is None or normalised(item.storey or "") == scope.storey)
    ]
    # Shown only when it is exactly what was counted (core does not name the objects yet)
    exact = not named and (found.measure != "count" or len(chosen) == found.original_value)
    where = f" on {chosen[0].storey}" if exact and chosen and scope.storey else ""
    return Proof(
        kind="model",
        legend=keys,
        arithmetic=f"{len(chosen)} {found.subject} objects in the model{where}" if exact else None,
        objects=tuple(_item(item) for item in chosen) if exact else None,
        storeys=storey_table(objects),
        schedule=None,
    )


def _item(item: ModelObject) -> ModelItem:
    return ModelItem(
        id=item.id,
        class_=item.class_,
        name=item.long_name or item.name,
        storey=item.storey,
        global_id=item.global_id,
    )


def storey_table(objects: Sequence[ModelObject]) -> tuple[StoreyRow, ...]:
    """Per storey, in the order the model lists them, how many objects of each class it has."""
    rows: dict[str, Counter[str]] = {}
    for item in objects:
        if item.storey is not None:
            rows.setdefault(item.storey, Counter())[item.class_] += 1
    return tuple(StoreyRow(storey=name, counts=dict(sorted(n.items()))) for name, n in rows.items())


def schedule_proof(
    marks: Sequence[MarkView], tables: Sequence[Table], answer: int | float | str | None
) -> Proof:
    """The table whose rows the answer's boxes are, with those rows' cells."""
    best: tuple[Table, list[ScheduleRow]] | None = None
    for table in tables:
        boxes = {(table.page, row.box or table.box): row for row in table.rows}
        rows = [
            ScheduleRow(n=mark.n or at, box=mark.box, cells=boxes[mark.page, mark.box].cells)
            for at, mark in enumerate(marks, start=1)
            if (mark.page, mark.box) in boxes
        ]
        if rows and (best is None or len(rows) > len(best[1])):
            best = (table, rows)
    if best is None:
        return NO_PROOF
    table, rows = best
    schedule = Schedule(
        table=table.id,
        title=table.title,
        page=table.page,
        box=table.box,
        columns=table.columns,
        rows=tuple(rows),
        of=len(table.rows),
    )
    name = table.title or "the schedule"
    sums = f"{len(rows)} of the {len(table.rows)} rows of {name}"
    if isinstance(answer, int) and answer == len(rows):
        sums += f" = {answer}"
    return Proof(
        kind="schedule", legend=(), arithmetic=sums, objects=None, storeys=None, schedule=schedule
    )

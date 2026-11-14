"""The facts of a building drawing or model, per discipline: what it says, as plain numbers and
names, read once at ingest. Answers take their numbers from here; nothing is measured twice.

Any source writes them with the same topics: an IFC model (app/adapters/ifc_model/, e.g.
facts_arch.py), a vector PDF, or a picture read with vision. `source` names the method, so an
answer never assumes which one it was.
A topic is `<entity>.<measure>` in lower_snake case, e.g. "space.net_floor_area"; a subject is
the thing as the file names it (a type, a space, a system), so a question's words can find it.
"""

from typing import Literal

from app.core.drawing.model import Box
from app.core.model import Frozen

Discipline = Literal[
    "architecture",
    "structural",
    "plumbing",
    "heating",
    "ventilation",
    "electrical",
    "fire",
    "site",
    "other",
]


class Spot(Frozen):
    """Where on a drawing a fact's thing is: one counted symbol, or one piece of a run."""

    page: int
    box: Box  # page fractions
    reader: str  # who saw it there: "vlm", "template", "paths", "mask"


class Fact(Frozen):
    topic: str  # e.g. "space.area", "wall_type.thickness", "pipe.length", "system.count"
    subject: str  # the thing: a type, space or system name as the source writes it
    value: float | int | str
    unit: str | None  # "m", "m2", "m3", "count", "mm"; None for text
    storey: str | None = None
    system: str | None = None
    discipline: Discipline
    source: str  # how it was read: "Qto_SpaceBaseQuantities.NetFloorArea", "geometry", ...
    spots: tuple[Spot, ...] = ()  # the marks on the page behind it; none from a model


class FactSheet(Frozen):
    model: str  # an opaque id of the drawing or model file (its stem at runtime)
    disciplines: list[Discipline]
    facts: list[Fact]

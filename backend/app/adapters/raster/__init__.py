"""`EXTRACTOR_RASTER=composite`: the raster route's `Extractor`, built from component readers.

A raster sheet (a CubiCasa PNG) is read by several methods, each good at one part: a detector for
the elements, a plan finder for the plans on the sheet, OCR or segmentation for the rooms. Each
component is itself an `Extractor`. `RASTER_COMPONENTS` says which component gives which part:

    elements=exp:detector/A,sauna_stove=exp:detector/B,plans=one-plan,rooms=exp:ocr/A

- `elements`: every element class; a class named on its own (`door`, `sauna_stove`...) overrides it.
- `rooms`: the rooms; `plans`: the plans (required); `scale`: the scale (left out: `no_scale`).
- What a source name means (`exp:<track>/<arm>`, `dir:<path>`, `one-plan`) is decided in
  app/composition.py, which builds one adapter per distinct source.

Merge rules. Each part has exactly one source, so nothing is counted twice: the elements of a class
come only from that class's source, the rooms only from the rooms' source. A class (or `room`) is
in `read` only when its source looked for it on this sheet (its own `read`; None: everything), so
a source that did not read a sheet leaves its classes unknown, never 0. The plans' source gives
the plans, and every element and room is put on the plan whose box holds its centre (None when no
plan does), so plan ids stay consistent whichever source an item came from. Ids are renumbered
(`p1`, `e1`, `r1`...) and each item keeps its source's attrs (`attrs.score`) plus
`attrs.component`, the source name.
"""

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass

from app.core.drawing.model import (
    ELEMENT_CLASSES,
    Box,
    Element,
    ElementClass,
    Plan,
    ReadClass,
    Room,
    Scale,
)
from app.core.errors import InvalidInputError
from app.core.pipeline.model import DrawingFile, Extracted, Sheet
from app.core.pipeline.ports import Extractor

GROUPS = ("elements", "rooms", "plans", "scale")
PARTS: tuple[str, ...] = (*GROUPS, *ELEMENT_CLASSES)


@dataclass(frozen=True)
class Component:
    """One reader and the source name the spec gave it (kept on every item it gives)."""

    name: str
    reader: Extractor


def parse_components(spec: str) -> dict[str, str]:
    """`RASTER_COMPONENTS` as {part: source name}. Refuses an unknown part, a part named twice,
    an empty source, and a spec without `plans`."""
    parts: dict[str, str] = {}
    for item in (piece.strip() for piece in spec.split(",")):
        if not item:
            continue
        part, sep, source = (text.strip() for text in item.partition("="))
        if not sep or not source:
            raise InvalidInputError(f"RASTER_COMPONENTS: {item!r} is not <part>=<source>")
        if part not in PARTS:
            raise InvalidInputError(
                f"RASTER_COMPONENTS: unknown part {part!r}; parts are {', '.join(PARTS)}"
            )
        if part in parts:
            raise InvalidInputError(f"RASTER_COMPONENTS: {part!r} is given twice")
        parts[part] = source
    if "plans" not in parts:
        raise InvalidInputError(
            "RASTER_COMPONENTS needs plans=<source> (one-plan: the whole page is one plan)"
        )
    return parts


def assemble(
    parts: Mapping[str, str], build: Callable[[str], Extractor]
) -> "CompositeRasterExtractor":
    """The composite for parsed parts; `build` makes the reader of a source name, called once
    per distinct name, so two parts from one source read the sheet once."""
    readers: dict[str, Component] = {}

    def component(name: str) -> Component:
        if name not in readers:
            readers[name] = Component(name, build(name))
        return readers[name]

    elements: dict[ElementClass, Component] = {}
    for kind in ELEMENT_CLASSES:
        name = parts.get(kind, parts.get("elements"))
        if name is not None:
            elements[kind] = component(name)
    rooms, scale = parts.get("rooms"), parts.get("scale")
    return CompositeRasterExtractor(
        elements=elements,
        rooms=None if rooms is None else component(rooms),
        plans=component(parts["plans"]),
        scale=None if scale is None else component(scale),
    )


class CompositeRasterExtractor:
    def __init__(
        self,
        *,
        elements: Mapping[ElementClass, Component],
        rooms: Component | None,
        plans: Component,
        scale: Component | None,
    ) -> None:
        self._elements = dict(elements)
        self._rooms = rooms
        self._plans = plans
        self._scale = scale

    def extract(self, source: DrawingFile, sheet: Sheet) -> Extracted:
        found: dict[str, Extracted] = {}

        def read_by(component: Component) -> Extracted:
            if component.name not in found:
                found[component.name] = component.reader.extract(source, sheet)
            return found[component.name]

        plans = tuple(
            plan.model_copy(update={"id": f"p{index}"})
            for index, plan in enumerate(read_by(self._plans).plans, start=1)
        )
        read: list[ReadClass] = []
        elements: list[Element] = []
        for kind, component in self._elements.items():
            got = read_by(component)
            if not _looked_for(got.read, kind):
                continue
            read.append(kind)
            for element in got.elements:
                if element.class_ == kind:
                    elements.append(
                        element.model_copy(
                            update={
                                "id": f"e{len(elements) + 1}",
                                "plan": _plan_of(plans, element.page, element.box),
                                "attrs": {**element.attrs, "component": component.name},
                            }
                        )
                    )
        rooms: list[Room] = []
        if self._rooms is not None and _looked_for((got := read_by(self._rooms)).read, "room"):
            read.append("room")
            rooms = [
                room.model_copy(
                    update={
                        "id": f"r{index}",
                        "plan": _plan_of(plans, room.page, room.box),
                        "apartment": None,
                        "attrs": {**room.attrs, "component": self._rooms.name},
                    }
                )
                for index, room in enumerate(got.rooms, start=1)
            ]
        scale = Scale(status="no_scale") if self._scale is None else read_by(self._scale).scale
        notes = [f"raster composite: {_who(self.parts())}"]
        for name, got in found.items():
            notes.extend(f"{name}: {note}" for note in got.notes)
        return Extracted(
            method="detector",
            scale=scale,
            plans=plans,
            elements=tuple(elements),
            rooms=tuple(rooms),
            read=tuple(read),
            notes=tuple(notes),
        )

    def parts(self) -> dict[str, str]:
        """Each part (element class, plans, rooms, scale) and the source name it comes from."""
        parts = {kind: component.name for kind, component in self._elements.items()}
        parts["plans"] = self._plans.name
        if self._rooms is not None:
            parts["rooms"] = self._rooms.name
        if self._scale is not None:
            parts["scale"] = self._scale.name
        return parts


def _looked_for(read: Sequence[ReadClass] | None, kind: ReadClass) -> bool:
    return read is None or kind in read


def _plan_of(plans: Sequence[Plan], page: int, box: Box) -> str | None:
    """The first plan on `page` whose box holds the centre of `box`."""
    x, y = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
    for plan in plans:
        x0, y0, x1, y1 = plan.box
        if plan.page == page and x0 <= x <= x1 and y0 <= y <= y1:
            return plan.id
    return None


def _who(parts: Mapping[str, str]) -> str:
    """The parts grouped by source, e.g. `exp:detector/A: door, window; one-plan: plans`."""
    by_source: dict[str, list[str]] = {}
    for part, name in parts.items():
        by_source.setdefault(name, []).append(part)
    return "; ".join(f"{name}: {', '.join(found)}" for name, found in by_source.items())

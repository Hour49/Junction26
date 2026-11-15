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

A plan box with no labelled room on a page where another box has one is not a floor plan
(app/core/pipeline/plan_rooms.py: an elevation beside the plans); what was read inside it stays,
on no plan.

`room_policy` (ROOM_POLICY, app/core/pipeline/room_policy.py) retypes the rooms' source's rooms
before they are placed, whichever source that is; None keeps the reader's types.

`DOUBLE_CHECK_READERS` names more sources to read each sheet with, `<reader name>=<source>` pairs:

    l1=detector:C-yolo26l,m1=detector:C-yolo26m

What a reader saw is kept next to the drawing (`double_check`, by reader name: the classes it
looked for and its elements, renumbered and put on the plans like a part's) and is never
counted. It is there for an answer to say where the readers disagree with it
(app/core/pipeline/disputed_marks.py). A source that is also a part reads the sheet once.

The distinct sources read a sheet at the same time, one thread each (they are independent, and
most wait on ONNX Runtime or a model API); their results are merged in the same order as before,
and what a source's calls cost is charged to the caller's thread (app/core/cost.py).

Each source that read the sheet is one step of the result (`Extracted.steps`, decision 0018): what
it was read for, when it began and how long it ran (sources overlap), what it cost and what it
found; a source whose model calls got no answer is a failed step. The steps a source reports itself
(the count arbiter's three reads) follow its own.
"""

import contextvars
from collections.abc import Callable, Mapping, Sequence
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass

from app.core import cost
from app.core.drawing.model import (
    ELEMENT_CLASSES,
    ArbiterReading,
    Box,
    Element,
    ElementClass,
    Plan,
    ReadClass,
    ReaderView,
    Room,
    Scale,
)
from app.core.errors import InvalidInputError
from app.core.pipeline.disputed_marks import ANSWER
from app.core.pipeline.model import DrawingFile, Extracted, Sheet, StepTrace
from app.core.pipeline.plan_rooms import floor_plans
from app.core.pipeline.ports import Extractor
from app.core.pipeline.steps import found_of, found_words, nested, now_ms, starting
from app.core.wording import SCALE_WORDS, count

RoomPolicy = Callable[[Sequence[Room]], Sequence[Room]]
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


def parse_readers(spec: str) -> dict[str, str]:
    """`DOUBLE_CHECK_READERS` as {reader name: source name}, in the order given. Refuses a pair
    without a name or a source, a name given twice, and the name the count itself has."""
    readers: dict[str, str] = {}
    for item in (piece.strip() for piece in spec.split(",")):
        if not item:
            continue
        name, sep, source = (text.strip() for text in item.partition("="))
        if not sep or not name or not source:
            raise InvalidInputError(f"DOUBLE_CHECK_READERS: {item!r} is not <name>=<source>")
        if name == ANSWER:
            raise InvalidInputError(
                f"DOUBLE_CHECK_READERS: {name!r} is the count itself, give the reader another name"
            )
        if name in readers:
            raise InvalidInputError(f"DOUBLE_CHECK_READERS: {name!r} is given twice")
        readers[name] = source
    return readers


def assemble(
    parts: Mapping[str, str],
    build: Callable[[str], Extractor],
    room_policy: RoomPolicy | None = None,
    double_check: Mapping[str, str] | None = None,
) -> "CompositeRasterExtractor":
    """The composite for parsed parts and parsed double-check readers; `build` makes the reader
    of a source name, called once per distinct name, so two parts from one source read the sheet
    once."""
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
        room_policy=room_policy,
        double_check={name: component(source) for name, source in (double_check or {}).items()},
    )


class CompositeRasterExtractor:
    def __init__(
        self,
        *,
        elements: Mapping[ElementClass, Component],
        rooms: Component | None,
        plans: Component,
        scale: Component | None,
        room_policy: RoomPolicy | None = None,
        double_check: Mapping[str, Component] | None = None,
    ) -> None:
        self._double_check = dict(double_check or {})
        self._elements = dict(elements)
        self._rooms = rooms
        self._plans = plans
        self._scale = scale
        self._room_policy = room_policy

    def extract(self, source: DrawingFile, sheet: Sheet) -> Extracted:
        components = {c.name: c for c in self._components()}
        spent: dict[str, float] = {}  # what each source that ran paid for, failed or not
        failed: dict[str, int] = {}  # and how many of its model calls got no answer
        spans: dict[str, tuple[float, float]] = {}  # when each began and ended, on now_ms()
        try:
            with ThreadPoolExecutor(len(components), thread_name_prefix="raster") as pool:
                pending = {
                    name: pool.submit(
                        contextvars.copy_context().run,  # so the source's step is heard live
                        _charged,
                        component.reader,
                        source,
                        sheet,
                        spent,
                        failed,
                        name,
                        spans,
                        self._label(name),
                    )
                    for name, component in components.items()
                }
                try:
                    merged = self._merge(pending)
                finally:
                    for future in pending.values():
                        future.cancel()
        finally:  # every started source has finished here: charge them all to the caller
            cost.charge(sum(spent.values()))
            cost.fail(sum(failed.values()))
        read = {name: future.result() for name, future in pending.items()}
        steps: list[StepTrace] = []
        for name in sorted(read, key=lambda name: spans[name][0]):
            step = self._step(name, read[name], spans[name], spent[name], failed[name])
            inner = (s.model_copy(update={"id": f"{step.id}/{s.id}"}) for s in read[name].steps)
            steps += [step, *inner]  # and what ran inside it, as `<its id>/<inner id>`
        return merged.model_copy(update={"steps": (*merged.steps, *steps)})

    def _step(
        self,
        name: str,
        got: Extracted,
        span: tuple[float, float],
        paid: float,
        faults: int,
    ) -> StepTrace:
        """One source's step: what it was read for, what it found of that, its time and cost."""
        parts = [part for part, by in self.parts().items() if by == name]
        checks = [check for check, by in self._double_check.items() if by.name == name]
        step_id, label = self._label(name)
        rooms = len(got.rooms) if "rooms" in parts and _looked_for(got.read, "room") else None
        plans = len(got.plans) if "plans" in parts else None
        # a part's source counts only the classes it gives; a double-check reader all it saw
        classes: list[ReadClass] = [
            kind for kind in ELEMENT_CLASSES if kind in parts and _looked_for(got.read, kind)
        ]
        found = found_of(got.elements, classes if parts else got.read, rooms=rooms, plans=plans)
        kinds = [part for part in parts if part in ELEMENT_CLASSES]
        other = [part for part in parts if part not in ELEMENT_CLASSES]
        given = (
            [count(len(kinds), "element class", "element classes"), *other]
            if len(kinds) > 4
            else parts
        )
        said = [f"read for {', '.join(given)}" if parts else "never counted"]
        if checks and parts:
            said.append(f"also double-check reader {', '.join(checks)}")
        said.append(found_words(found))
        if "scale" in parts:
            said.append(SCALE_WORDS[got.scale.status])
        if faults:
            said.append(f"{count(faults, 'model call')} got no answer")
        return StepTrace(
            id=step_id,
            label=label,
            did="; ".join(said),
            at_ms=span[0],
            ms=span[1] - span[0],
            cost_usd=paid,
            state="failed" if faults else "done",
            found=found,
        )

    def _label(self, name: str) -> tuple[str, str]:
        """The step id and label of the source `name`: a double-check reader's says so."""
        step_id, label = source_label(name)
        if name in self.parts().values():
            return step_id, label
        checks = [check for check, by in self._double_check.items() if by.name == name]
        named = ", ".join(checks)
        return f"double_check:{named}", f"Double-check reader {named}: {label}"

    def _components(self) -> list[Component]:
        """Every source this composite reads a sheet with, the parts' first."""
        rooms = [] if self._rooms is None else [self._rooms]
        scale = [] if self._scale is None else [self._scale]
        return [self._plans, *self._elements.values(), *rooms, *scale, *self._double_check.values()]

    def _merge(self, pending: Mapping[str, "Future[Extracted]"]) -> Extracted:
        found: dict[str, Extracted] = {}  # in the order the merge first asks for each source

        def read_by(component: Component) -> Extracted:
            if component.name not in found:
                found[component.name] = pending[component.name].result()
            return found[component.name]

        boxed = read_by(self._plans).plans
        seen_rooms: Sequence[Room] = ()  # asked of the future itself: `found` keeps its order
        if self._rooms is not None:
            by_rooms = pending[self._rooms.name].result()
            seen_rooms = by_rooms.rooms if _looked_for(by_rooms.read, "room") else ()
        kept = floor_plans(boxed, seen_rooms)
        plans = tuple(
            plan.model_copy(update={"id": f"p{index}"}) for index, plan in enumerate(kept, start=1)
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
        retyped: str | None = None
        if self._rooms is not None and _looked_for((got := read_by(self._rooms)).read, "room"):
            read.append("room")
            typed = got.rooms
            if self._room_policy is not None:
                typed = self._room_policy(got.rooms)
                changed = sum(
                    new.type != old.type for new, old in zip(typed, got.rooms, strict=True)
                )
                if changed:
                    retyped = (
                        f"room policy: {changed} of {len(typed)} rooms retyped by their "
                        "printed label"
                    )
            rooms = [
                room.model_copy(
                    update={
                        "id": f"r{index}",
                        "plan": _plan_of(plans, room.page, room.box),
                        "apartment": None,
                        "attrs": {**room.attrs, "component": self._rooms.name},
                    }
                )
                for index, room in enumerate(typed, start=1)
            ]
        arbiter: dict[str, ArbiterReading] = {}  # what a count arbiter among them read, kept
        for component in self._elements.values():
            for family, reading in (read_by(component).count_arbiter or {}).items():
                arbiter.setdefault(family, reading)
        scale = Scale(status="no_scale") if self._scale is None else read_by(self._scale).scale
        seen = {
            name: _view(read_by(component), plans, component.name)
            for name, component in self._double_check.items()
        }
        notes = [f"raster composite: {_who(self.parts())}"]
        if seen:
            named = (f"{name}: {component.name}" for name, component in self._double_check.items())
            notes.append(f"double-check readers: {'; '.join(named)}")
        for name, got in found.items():
            notes.extend(f"{name}: {note}" for note in got.notes)
        if retyped is not None:
            notes.append(retyped)
        if len(kept) < len(boxed):
            notes.append(
                f"raster composite: {len(boxed) - len(kept)} of {len(boxed)} plan boxes hold no "
                "room beside ones with labelled rooms: not floor plans"
            )
        return Extracted(
            method="detector",
            scale=scale,
            plans=plans,
            elements=tuple(elements),
            rooms=tuple(rooms),
            read=tuple(read),
            double_check=seen or None,
            count_arbiter=arbiter or None,
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


def _charged(
    reader: Extractor,
    source: DrawingFile,
    sheet: Sheet,
    spent: dict[str, float],
    failed: dict[str, int],
    name: str,
    spans: dict[str, tuple[float, float]],
    step: tuple[str, str],
) -> Extracted:
    """The reader's result, read on this (worker) thread; what its calls cost goes in
    `spent[name]` also when it fails, when it began and ended in `spans[name]`."""
    before, faulted = cost.mark(), cost.faults()
    started = now_ms()
    starting(*step)
    try:
        with nested(step[0]):  # its own steps are heard as `<its id>/<inner id>`
            return reader.extract(source, sheet)
    finally:
        spent[name] = cost.since(before)
        failed[name] = cost.faults_since(faulted)
        spans[name] = (started, now_ms())


# What a source name's kind (before its first ":") is, as a step: (id, label)
SOURCE_STEPS: dict[str, tuple[str, str]] = {
    "one-plan": ("plans", "Whole page as one plan"),
    "exp": ("reader", "Precomputed reading"),
    "dir": ("reader", "Precomputed reading"),
    "detector": ("detector", "Symbol detector"),
    "detector-v2": ("detector", "Symbol detector, 2 views"),
    "detector-v4": ("detector", "Symbol detector, 4 views"),
    "detector-v8": ("detector", "Symbol detector, 8 views"),
    "photo": ("detector", "Symbol detector for photos"),
    "region": ("detector", "Symbol detector with region model"),
    "verda": ("reader", "Remote reader"),
    "gemini": ("rooms", "Room reader (Gemini)"),
    "regionrooms": ("rooms", "Room reader (Gemini + region model)"),
    "carbon": ("carbon", "Gemini Carbon reader"),
    "arbiter-t1": ("arbiter", "Symbol detector, 8 views + count arbiter"),
    "decisions": ("decisions", "Gemini Decisions count swap"),
    "decisions-s1536": ("decisions", "Gemini Decisions count swap (1536 px)"),
}


def source_label(source: str) -> tuple[str, str]:
    """The step id and label of a RASTER_COMPONENTS source name: `decisions:<inner>` names its
    inner reader too ("Gemini Decisions count swap over Symbol detector")."""
    kind, _, where = source.partition(":")
    step_id, label = SOURCE_STEPS.get(kind, ("reader", f"Reader {source}"))
    if kind.startswith("decisions") and where:
        return step_id, f"{label} over {source_label(where)[1]}"
    return step_id, label


def _looked_for(read: Sequence[ReadClass] | None, kind: ReadClass) -> bool:
    return read is None or kind in read


def _view(got: Extracted, plans: Sequence[Plan], source: str) -> ReaderView:
    """A double-check reader's reading: the element classes it looked for and its elements of
    them, renumbered, each on the plan that holds its centre."""
    read: tuple[ElementClass, ...] = tuple(
        kind for kind in ELEMENT_CLASSES if _looked_for(got.read, kind)
    )
    elements = (element for element in got.elements if element.class_ in read)
    return ReaderView(
        read=read,
        elements=tuple(
            element.model_copy(
                update={
                    "id": f"e{index}",
                    "plan": _plan_of(plans, element.page, element.box),
                    "attrs": {**element.attrs, "component": source},
                }
            )
            for index, element in enumerate(elements, start=1)
        ),
    )


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

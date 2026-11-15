"""The Carbon reader of raster drawings (brief r8 AS-2; .agents/exp/carbon-reader.md):
gemini-4-carbon reads page 1 whole and in full-resolution tiles. contract.py is what is asked and
how the replies become a drawing; reader.py makes the calls. `CarbonSwitch` (CARBON_READER=all,
advanced) sends a raster drawing to it or to the shipped reader; `CarbonThings` (CARBON_READER=
large) takes the things drawn from it and the rooms from the shipped reader; `CarbonChecked`
(CARBON_LEVELS=demote) keeps what it read beside the shipped reading, never counted. The last two
read a sheet with Carbon and the shipped reader at the same time (app/adapters/beside.py), except
`CarbonThings`' few clause, which needs the shipped reader's count first.

Each keeps the shipped reader's steps and adds one `carbon` step (decision 0018): when Carbon
began and ran, what it cost and found, failed when it read nothing, skipped when the few clause
did not need it.
"""

import logging
from collections.abc import Callable, Sequence

from PIL import Image

from app.adapters.beside import beside
from app.adapters.carbon.reader import CarbonClient, CarbonExtractor, CarbonReader
from app.core.drawing.model import Box, CarbonCheck, Element, Plan, ReadClass
from app.core.pipeline.model import DrawingFile, Extracted, Sheet, StepTrace
from app.core.pipeline.ports import Extractor
from app.core.pipeline.steps import Span, found_of, found_words, starting, timed
from app.core.wording import count

__all__ = [
    "CarbonChecked",
    "CarbonClient",
    "CarbonExtractor",
    "CarbonReader",
    "CarbonSwitch",
    "CarbonThings",
]

log = logging.getLogger(__name__)


class CarbonSwitch:
    """CARBON_READER: a drawing `use_carbon` says yes to (by its path) is read by Carbon alone,
    every other by the shipped reader. Ingest flags the first kind with the same `use_carbon`
    (composition `Pipeline.carbon_read`)."""

    def __init__(
        self, other: Extractor, carbon: Extractor, use_carbon: Callable[[str], bool]
    ) -> None:
        self._other = other
        self._carbon = carbon
        self._use_carbon = use_carbon

    def extract(self, source: DrawingFile, sheet: Sheet) -> Extracted:
        if not self._use_carbon(source.path):
            return self._other.extract(source, sheet)
        starting("carbon", "Gemini Carbon reader (the whole sheet)")
        found, span = timed(lambda: self._carbon.extract(source, sheet))
        rooms = len(found.rooms) if found.read is None or "room" in found.read else None
        seen = found_of(found.elements, found.read, rooms=rooms, plans=len(found.plans))
        step = _carbon_step("Gemini Carbon reader (the whole sheet)", span, seen)
        if not found.read:
            step = _read_nothing(step, found.notes)
        return found.model_copy(update={"steps": (*found.steps, step)})


class CarbonThings:
    """CARBON_READER=large: on a drawing `use_carbon` says yes to, Carbon gives the things drawn
    (plans and the element classes it could count) and the shipped reader the rooms, with its
    scale and its double-check readers' views. On the 6 hard floor plans over 4,000 px Carbon won
    on things drawn (28 right, 1 wrong, 9 refused; product 20 / 18 / 0) and refused rooms (3 / 0
    / 24; product 22 / 5 / 0; confidence, 2026-11-14). Every room and element is put on the plan
    that holds its centre. When Carbon found no plan (its page call failed), the shipped reader's
    plans are kept and a note says so; an element class Carbon did not read stays unread (no
    fallback). The count arbiter's reading is dropped: it read the shipped elements, not these.
    A drawing `use_carbon` says no to is read the same way when the shipped reader found fewer
    than `few` elements on it (a scan or photo the detector cannot read; on 6 hard floor plans of
    at most 4,000 px with none found, the split was 59 right / 3 wrong / 1 refused against the
    product's 55 / 8 / 0, and no CubiCasa page of val or golden dev has fewer than 3; confidence,
    carbon-reader.md 5.8-5.9); its path is added to `took`. When Carbon read nothing there (no
    plan, no class: a failed call, a spent budget) the shipped reading is kept and the path is
    not added (fail-1, review-293 S1). Every other drawing is the shipped reader's. Ingest flags
    both kinds (composition `Pipeline.carbon_read`), so no answer on them is certified."""

    def __init__(
        self,
        other: Extractor,
        carbon: Extractor,
        use_carbon: Callable[[str], bool],
        few: int = 0,
        took: set[str] | None = None,
    ) -> None:
        self._other = other
        self._carbon = carbon
        self._use_carbon = use_carbon
        self._few = few
        self._took = took

    def extract(self, source: DrawingFile, sheet: Sheet) -> Extracted:
        why = "a large sheet"  # why Carbon's things drawn replace the shipped reader's
        if self._use_carbon(source.path):  # known before reading: both at the same time
            (shipped, _), (carbon, span) = beside(
                lambda: timed(lambda: self._other.extract(source, sheet)),
                lambda: timed(lambda: self._carbon.extract(source, sheet)),
            )
        else:  # the few clause needs the shipped reader's count first: one after the other
            shipped, by_shipped = timed(lambda: self._other.extract(source, sheet))
            steps = shipped.steps
            if len(shipped.elements) >= self._few:
                ended = by_shipped.at_ms + by_shipped.ms
                skipped = StepTrace(
                    id="carbon",
                    label=THINGS,
                    did=(
                        f"not needed: the shipped reader found "
                        f"{count(len(shipped.elements), 'element')} (it reads a sheet with "
                        f"fewer than {self._few})"
                        if self._few
                        else "not used on this sheet"
                    ),
                    at_ms=ended,
                    state="skipped",
                )
                return shipped.model_copy(update={"steps": (*steps, skipped)})
            starting("carbon", THINGS)
            carbon, span = timed(lambda: self._carbon.extract(source, sheet))
            if not carbon.plans and not carbon.read:  # Carbon read nothing (a failed call, a
                # spent budget): the shipped reading stays, as before the clause
                step = _read_nothing(_carbon_step(THINGS, span, {}), carbon.notes)
                step = step.model_copy(update={"did": f"{step.did}; the shipped reading stays"})
                return shipped.model_copy(update={"steps": (*steps, step)})
            if self._took is not None:
                self._took.add(source.path)
            why = f"{count(len(shipped.elements), 'element')}, fewer than {self._few}"
        seen = found_of(carbon.elements, carbon.read, plans=len(carbon.plans))
        step = _carbon_step(THINGS, span, seen)
        if not carbon.plans:
            step = step.model_copy(update={"did": f"{step.did}; no plan read"})
        none = [kind for kind in carbon.read or () if kind != "room" and kind not in seen]
        said = f"{step.did}; replaces the shipped reading's things drawn ({why})"
        if none:
            said += f"; looked for, none found: {', '.join(k.replace('_', ' ') for k in none)}"
        step = step.model_copy(update={"did": said})
        notes = list(carbon.notes)
        plans = carbon.plans
        if not plans:
            plans = shipped.plans
            notes.append("carbon: no plan read: the plans are the shipped reader's")
        rooms_read = shipped.read is None or "room" in shipped.read
        read: list[ReadClass] = [kind for kind in carbon.read or () if kind != "room"]
        if rooms_read:
            read.append("room")
        notes.append("carbon: the rooms, the scale and the double-check are the shipped reader's")
        views = {
            name: view.model_copy(
                update={
                    "elements": tuple(
                        e.model_copy(update={"plan": _plan_of(plans, e.page, e.box)})
                        for e in view.elements
                    )
                }
            )
            for name, view in (shipped.double_check or {}).items()
        }
        return Extracted(
            method="detector",
            scale=shipped.scale,
            plans=plans,
            elements=tuple(
                e.model_copy(update={"plan": _plan_of(plans, e.page, e.box)})
                for e in _snapped_doors(carbon.elements, shipped.elements)
            ),
            rooms=tuple(
                r.model_copy(update={"plan": _plan_of(plans, r.page, r.box)})
                for r in (shipped.rooms if rooms_read else ())
            ),
            tables=carbon.tables,
            read=tuple(read),
            double_check=views or None,
            notes=(*notes, *shipped.notes),
            steps=(*shipped.steps, step),
        )


class CarbonChecked:
    """CARBON_LEVELS=demote: the drawing is `other`'s, and what Carbon read of the same sheet is
    kept beside it as `carbon_check`, never counted. A Medium answer whose question Carbon
    answers with another value becomes Low (integ's rule, .agents/exp/integ.md AW
    pre-registration 2: on 256 unseen val pages Medium went from 92.4% to 95.4% exact). When
    Carbon read nothing (a failed call, nothing it could count, an image it cannot open, any
    error in the check itself), the check says why and is logged: the reader's drawing is kept,
    no level changes, and the level says it was not checked."""

    def __init__(self, other: Extractor, carbon: Extractor) -> None:
        self._other = other
        self._carbon = carbon

    def extract(self, source: DrawingFile, sheet: Sheet) -> Extracted:
        (found, _), (check, span) = beside(  # independent reads: at the same time
            lambda: timed(lambda: self._other.extract(source, sheet)),
            lambda: timed(lambda: self._check(source, sheet)),
        )
        rooms = len(check.rooms) if "room" in check.read else None
        seen = found_of(check.elements, check.read, rooms=rooms, plans=len(check.plans))
        step = _carbon_step("Gemini Carbon check (never counted)", span, seen, "carbon_check")
        if check.failed is not None:
            step = step.model_copy(update={"did": check.failed, "state": "failed"})
        steps = (*found.steps, step)
        return found.model_copy(update={"carbon_check": check, "steps": steps})

    def _check(self, source: DrawingFile, sheet: Sheet) -> CarbonCheck:
        """What Carbon read of the sheet, or why it read nothing; never raises."""
        try:
            seen = self._carbon.extract(source, sheet)
        except (OSError, Image.DecompressionBombError) as error:  # PIL could not open the image
            check = CarbonCheck(failed=f"the image could not be opened: {type(error).__name__}")
        except Exception as error:  # a bug in a check that is never counted keeps the drawing
            log.exception("Carbon check of %s raised", source.path)
            return CarbonCheck(failed=f"the check failed: {type(error).__name__}")
        else:
            check = CarbonCheck(
                read=tuple(seen.read or ()),
                plans=seen.plans,
                elements=seen.elements,
                rooms=seen.rooms,
                failed=None if seen.read else _why(seen.notes),
            )
        if check.failed is not None:
            log.warning("Carbon did not check %s: %s", source.path, check.failed)
        return check


THINGS = "Gemini Carbon reader (things drawn)"


def _carbon_step(
    label: str, span: Span, found: dict[str, int], step_id: str = "carbon"
) -> StepTrace:
    """Carbon's step: what it found, failed when one of its model calls got no answer. Its id is
    `carbon` for the reader and `carbon_check` for the check, so both keep theirs side by side
    (decision 0018)."""
    did = found_words(found)
    if span.faults:
        did += f"; {count(span.faults, 'model call')} got no answer"
    return StepTrace(
        id=step_id,
        label=label,
        did=did,
        at_ms=span.at_ms,
        ms=span.ms,
        cost_usd=span.cost_usd,
        state="failed" if span.faults else "done",
        found=found,
    )


def _read_nothing(step: StepTrace, notes: Sequence[str]) -> StepTrace:
    """`step` failed: Carbon read nothing, and why."""
    return step.model_copy(update={"did": f"read nothing: {_why(notes)}", "state": "failed"})


def _why(notes: Sequence[str]) -> str:
    """Why Carbon read nothing, from its first note (contract.assemble puts the reason first)."""
    first = notes[0] if notes else "carbon: no usable reply"
    return first.removeprefix("carbon: ")


def _snapped_doors(carbon: Sequence[Element], shipped: Sequence[Element]) -> list[Element]:
    """Carbon's elements, each door on the box of a shipped door whose centre lies inside it. Carbon
    boxes a door with its swing arc, a square about five times the opening the detector and the
    gold box mark: on golden's two CubiCasa pages over 4,000 px its 19 door boxes matched 0 of 22
    gold doors at IoU 0.5, snapped 18, as the detector (answer, 2026-11-14; .agents/exp/answer.md).
    The pairs are a maximum matching (each shipped door once, as many Carbon doors snapped as can
    be, whatever the reply's order; codecheck, review-310 S1). Overlap only breaks ties: a Carbon
    door takes its best-overlap free candidate and moves an earlier door only when none is free.
    Windows are not snapped (Carbon's matched 25, snapped 21). A door left without a shipped door
    keeps Carbon's box; no element is added or dropped, so every count stays Carbon's."""
    doors = [e for e in shipped if e.class_ == "door"]
    options = {
        i: sorted(
            (k for k, d in enumerate(doors) if d.page == e.page and _holds(e.box, d.box)),
            key=lambda k: -_iou(e.box, doors[k].box),
        )
        for i, e in enumerate(carbon)
        if e.class_ == "door"
    }
    owner: dict[int, int] = {}  # shipped door -> the Carbon element on its box

    def take(i: int, seen: set[int]) -> bool:  # an augmenting path from Carbon door i
        for k in options[i]:
            if k not in seen:
                seen.add(k)
                if k not in owner or take(owner[k], seen):
                    owner[k] = i
                    return True
        return False

    for i in options:  # a free shipped door first, best overlap first; else an augmenting path
        free = next((k for k in options[i] if k not in owner), None)
        if free is not None:
            owner[free] = i
        else:
            take(i, set())
    box = {i: doors[k].box for k, i in owner.items()}
    return [
        e.model_copy(update={"box": box[i], "attrs": {**e.attrs, "box_from": "detector"}})
        if i in box
        else e
        for i, e in enumerate(carbon)
    ]


def _holds(box: Box, other: Box) -> bool:
    """Whether `other`'s centre lies inside `box`."""
    x, y = (other[0] + other[2]) / 2, (other[1] + other[3]) / 2
    return box[0] <= x <= box[2] and box[1] <= y <= box[3]


def _iou(a: Box, b: Box) -> float:
    width = min(a[2], b[2]) - max(a[0], b[0])
    height = min(a[3], b[3]) - max(a[1], b[1])
    inter = max(0.0, width) * max(0.0, height)
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union > 0 else 0.0


def _plan_of(plans: Sequence[Plan], page: int, box: Box) -> str | None:
    """The first plan on `page` whose box holds the centre of `box`, as the composite places."""
    x, y = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
    for plan in plans:
        if (
            plan.page == page
            and plan.box[0] <= x <= plan.box[2]
            and plan.box[1] <= y <= plan.box[3]
        ):
            return plan.id
    return None

"""The Carbon reader of raster drawings (brief r8 AS-2; .agents/exp/carbon-reader.md):
gemini-4-carbon reads page 1 whole and in full-resolution tiles. contract.py is what is asked and
how the replies become a drawing; reader.py makes the calls. `CarbonSwitch` (CARBON_READER=all,
advanced) sends a raster drawing to it or to the shipped reader; `CarbonThings` (CARBON_READER=
large) takes the things drawn from it and the rooms from the shipped reader; `CarbonChecked`
(CARBON_LEVELS=demote) keeps what it read beside the shipped reading, never counted. The last two
read a sheet with Carbon and the shipped reader at the same time (app/adapters/beside.py), except
`CarbonThings`' few clause, which needs the shipped reader's count first.
"""

import logging
from collections.abc import Callable, Sequence

from PIL import Image

from app.adapters.beside import beside
from app.adapters.carbon.reader import CarbonClient, CarbonExtractor, CarbonReader
from app.core.drawing.model import Box, CarbonCheck, Element, Plan, ReadClass
from app.core.pipeline.model import DrawingFile, Extracted, Sheet
from app.core.pipeline.ports import Extractor

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
        reader = self._carbon if self._use_carbon(source.path) else self._other
        return reader.extract(source, sheet)


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
        if self._use_carbon(source.path):  # known before reading: both at the same time
            shipped, carbon = beside(
                lambda: self._other.extract(source, sheet),
                lambda: self._carbon.extract(source, sheet),
            )
        else:  # the few clause needs the shipped reader's count first: one after the other
            shipped = self._other.extract(source, sheet)
            if len(shipped.elements) >= self._few:
                return shipped
            carbon = self._carbon.extract(source, sheet)
            if not carbon.plans and not carbon.read:  # Carbon read nothing (a failed call, a
                return shipped  # spent budget): the shipped reading stays, as before the clause
            if self._took is not None:
                self._took.add(source.path)
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
        found, check = beside(  # independent reads of the same sheet: at the same time
            lambda: self._other.extract(source, sheet), lambda: self._check(source, sheet)
        )
        return found.model_copy(update={"carbon_check": check})

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

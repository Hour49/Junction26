"""The Carbon reader of raster drawings (brief r8 AS-2; .agents/exp/carbon-reader.md):
gemini-4-carbon reads page 1 whole and in full-resolution tiles. contract.py is what is asked and
how the replies become a drawing; reader.py makes the calls. `CarbonSwitch` (CARBON_READER=all,
advanced) sends a raster drawing to it or to the shipped reader; `CarbonThings` (CARBON_READER=
large) takes the things drawn from it and the rooms from the shipped reader; `CarbonChecked`
(CARBON_LEVELS=demote) keeps what it read beside the shipped reading, never counted. The last two
read a sheet with Carbon and the shipped reader at the same time (app/adapters/beside.py).
"""

import logging
from collections.abc import Callable, Sequence

from PIL import Image

from app.adapters.beside import beside
from app.adapters.carbon.reader import CarbonClient, CarbonExtractor, CarbonReader
from app.core.drawing.model import Box, CarbonCheck, Plan, ReadClass
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
    Every other drawing is the shipped reader's. Ingest flags the first kind (composition
    `Pipeline.carbon_read`), so no answer on them is certified."""

    def __init__(
        self, other: Extractor, carbon: Extractor, use_carbon: Callable[[str], bool]
    ) -> None:
        self._other = other
        self._carbon = carbon
        self._use_carbon = use_carbon

    def extract(self, source: DrawingFile, sheet: Sheet) -> Extracted:
        if not self._use_carbon(source.path):
            return self._other.extract(source, sheet)
        shipped, carbon = beside(  # independent reads of the same sheet: at the same time
            lambda: self._other.extract(source, sheet), lambda: self._carbon.extract(source, sheet)
        )
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
                for e in carbon.elements
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

"""The local raster reading (the detectors, the arbiter, the region and room readers of the
composite) one sheet at a time in this process.

Ingest reads several drawing groups at once (INGEST_GROUPS_IN_FLIGHT) so that their Carbon calls,
which mostly wait on the network, overlap. The local reading of a big sheet holds gigabytes (eight
views of a 138-megapixel page): four of them side by side went past the backend's memory and
swapped (codecheck, 2026-11-15: a 6-image upload 37 s -> 288 s on cached replies). Held only around
the local reader, this lock keeps one such reading in memory at a time while the Carbon calls the
reader is wrapped in (CarbonThings, CarbonChecked, PrintedScale run them beside it) go on.

A reading that waited for a slot reports the wait as the `local_slot` step, before the inner
reader's steps (decision 0018), so the ingest screen shows why its readers began late; a reading
that got a slot at once (under `WAITED_MS`) reports no step. The step is reporting only: the lock,
its count and what it wraps are the same with or without it."""

import threading

from app.core.pipeline.model import DrawingFile, Extracted, Sheet, StepTrace
from app.core.pipeline.ports import Extractor
from app.core.pipeline.steps import now_ms

STEP_ID = "local_slot"  # stable (docs/API.md)
LABEL = "Waited for the local reader"
WAITED_MS = 10.0  # a shorter wait is the lock's own cost, not a wait for another sheet: no step

_slots: dict[int, threading.BoundedSemaphore] = {}  # by the count: one per process
_slots_guard = threading.Lock()


class OneAtATime:
    """`slots` local readings at once (INGEST_LOCAL_IN_FLIGHT), shared by every pipeline of the
    process; 1 is one at a time."""

    def __init__(self, inner: Extractor, slots: int = 1) -> None:
        self._inner, self._count = inner, slots
        with _slots_guard:
            self._slots = _slots.setdefault(slots, threading.BoundedSemaphore(slots))

    def extract(self, source: DrawingFile, sheet: Sheet) -> Extracted:
        asked = now_ms()
        with self._slots:
            waited = now_ms() - asked
            found = self._inner.extract(source, sheet)
        if waited < WAITED_MS:
            return found
        step = _waited(asked, waited, self._count)
        return found.model_copy(update={"steps": (step, *found.steps)})


def _waited(asked: float, ms: float, slots: int) -> StepTrace:
    """The wait for a slot as a step: from `asked` (on `now_ms()`'s clock), `ms` long."""
    took = f"{ms / 1000:.1f} s" if ms >= 1000 else f"{ms:.0f} ms"
    pace = "one sheet" if slots == 1 else f"{slots} sheets"
    did = f"waited {took}: the local readers read {pace} at a time"
    return StepTrace(id=STEP_ID, label=LABEL, did=did, at_ms=asked, ms=ms)

"""Model calls of the local raster reading asked before its slot (one_at_a_time.py).

The composite reads a sheet inside the one-at-a-time slot, and two of its components ask Gemini
there: the Decisions reader (decisions/uses.py) and the Gemini rooms reader under RegionRooms.
Cold, those calls held the slot while they waited on the network, so the next sheet waited too
(codecheck, 2026-11-15: 10 cold files, the slot held 64.7 s in all). Neither call needs the local
reading: both send the page as uploaded. So OneAtATime starts them on their own threads before it
waits for the slot, and the component that asks inside the slot gets that started call's result:
the same call, the same reply object (its note still says how long the call took), and the
dollars it cost charged on the thread that takes it, as if it had been paid there.

A started call belongs to one reading: it is keyed by that reading's `Sheet` object, which the
composite hands unchanged to its components, so two projects reading the same file at once never
take each other's call. A started call that is not taken (the reading failed before its component
asked) is settled: waited for and charged, so the trace still counts what was paid. A call not
started yet when its component asks is cancelled and asked inline, as before. Each kind of call
runs on its own small pool: a Gemini rooms call holds its decoded page while it waits, so how many
run at once bounds the memory they add next to the slot's reading.
"""

import threading
from collections.abc import Callable, Iterator
from concurrent.futures import Future, ThreadPoolExecutor
from contextlib import contextmanager
from typing import Protocol

from app.adapters.decisions.g1main import PageCounts
from app.adapters.decisions.uses import CountsReader
from app.core import cost
from app.core.pipeline.model import DrawingFile, Extracted, Sheet
from app.core.pipeline.ports import DrawingFiles, Extractor

# Calls at once per kind, process-wide. A Decisions call sends the file's bytes as they are; a
# Gemini rooms call decodes the page (a big sheet: 0.1-0.4 GB) and holds it until the reply
DECISIONS_AHEAD = 8
ROOMS_AHEAD = 3
Paid = tuple[object, cost.Carry]  # the result (or the exception raised), its costs


class Ahead(Protocol):
    def start(self, source: DrawingFile, sheet: Sheet) -> None:
        """Ask this reading's call now, on another thread."""
        ...

    def settle(self, sheet: Sheet) -> None:
        """The reading has ended: a call it started and did not take is waited for and charged
        on this thread."""
        ...


class _Started[T]:
    """Calls started by reading (the id of its `Sheet`), each taken once; `workers` threads."""

    def __init__(self, workers: int, name: str) -> None:
        self._pool = ThreadPoolExecutor(workers, thread_name_prefix=name)
        self._started: dict[int, Future[Paid]] = {}
        self._guard = threading.Lock()

    def start(self, sheet: Sheet, call: Callable[[], T]) -> None:
        carried = cost.Carry()

        def paid() -> Paid:
            try:
                found: object = carried.run(call)
            except Exception as error:  # handed to the taker, raised there
                found = error
            return found, carried

        future = self._pool.submit(paid)
        with self._guard:
            self._started[id(sheet)] = future

    def take(self, sheet: Sheet, call: Callable[[], T]) -> T:
        with self._guard:
            future = self._started.pop(id(sheet), None)
        if future is None or future.cancel():  # none, or not started yet: ask it here
            return call()
        found, carried = future.result()
        carried.hand_back()  # its dollars and failed calls, on the reading's thread
        if isinstance(found, Exception):
            raise found
        return found  # type: ignore[return-value]  # what `call` returned

    def settle(self, sheet: Sheet) -> None:
        with self._guard:
            future = self._started.pop(id(sheet), None)
        if future is not None and not future.cancel():
            future.result()[1].hand_back()


class AheadDecisions:
    """The Decisions reader of a DecisionsCountExtractor wrapped in `AheadDecisions.reading`:
    `read(image)` takes the call started for the reading this thread is in, else asks it."""

    def __init__(self, reader: CountsReader, files: DrawingFiles, workers: int) -> None:
        self._reader = reader
        self._files = files
        self._calls: _Started[PageCounts] = _Started(workers, "ahead-decisions")
        self._reading = threading.local()  # the Sheet this thread's component is reading

    def start(self, source: DrawingFile, sheet: Sheet) -> None:
        self._calls.start(sheet, lambda: self._reader.read(self._files.read(source.path)))

    def read(self, image: bytes) -> PageCounts:
        sheet: Sheet | None = getattr(self._reading, "sheet", None)
        if sheet is None:
            return self._reader.read(image)
        return self._calls.take(sheet, lambda: self._reader.read(image))

    def settle(self, sheet: Sheet) -> None:
        self._calls.settle(sheet)

    @contextmanager
    def reading(self, sheet: Sheet) -> Iterator[None]:
        self._reading.sheet = sheet
        try:
            yield
        finally:
            self._reading.sheet = None


class DecisionsReading:
    """A DecisionsCountExtractor whose reader is `ahead`: tells it which reading asks."""

    def __init__(self, inner: Extractor, ahead: AheadDecisions) -> None:
        self._inner = inner
        self._ahead = ahead

    def extract(self, source: DrawingFile, sheet: Sheet) -> Extracted:
        with self._ahead.reading(sheet):
            return self._inner.extract(source, sheet)


class AheadExtractor:
    """A component that only asks a model (the Gemini rooms reader): `extract` takes the reading
    started for that sheet, else reads it."""

    def __init__(self, inner: Extractor, workers: int) -> None:
        self._inner = inner
        self._calls: _Started[Extracted] = _Started(workers, "ahead-rooms")

    def start(self, source: DrawingFile, sheet: Sheet) -> None:
        self._calls.start(sheet, lambda: self._inner.extract(source, sheet))

    def extract(self, source: DrawingFile, sheet: Sheet) -> Extracted:
        return self._calls.take(sheet, lambda: self._inner.extract(source, sheet))

    def settle(self, sheet: Sheet) -> None:
        self._calls.settle(sheet)

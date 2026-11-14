"""Per-file, per-stage timing of a pipeline run, without touching the pipeline: each port the
stages call is wrapped, and the wrapper notes how long its call took for which sheet. The
pipeline's own trace lines say what each stage found; these say how long it took and which
stage was running when one failed."""

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

from app.core import cost
from app.core.drawing.model import Drawing, Page
from app.core.ingest.model import Stage
from app.core.ingest.ports import Clock
from app.core.pipeline.model import DrawingFile, Extracted, Measurement, Sheet
from app.core.pipeline.ports import Extractor, PageReader, SecondCounter


@dataclass
class StageClock:
    """`ms[path][stage]`: time spent in each stage for the sheet at `path`, `usd[path][stage]`
    the model calls it paid for (app/core/cost.py). `running` is the (stage, path) whose call has
    started and not returned: after an exception, the one that failed."""

    clock: Clock
    on_start: Callable[[Stage, str], None] = lambda stage, path: None  # shows the live stage
    ms: dict[str, dict[Stage, float]] = field(default_factory=dict[str, dict[Stage, float]])
    usd: dict[str, dict[Stage, float]] = field(default_factory=dict[str, dict[Stage, float]])
    running: tuple[Stage, str] | None = None
    _ended: dict[str, float] = field(default_factory=dict[str, float])
    _spent: float = 0.0  # cost.spent() when the running call started

    def start(self, stage: Stage, path: str) -> float:
        self.running = (stage, path)
        self.on_start(stage, path)
        self._spent = cost.spent()
        return self.clock()

    def stop(self, stage: Stage, path: str, started: float) -> None:
        now = self.clock()
        spent = self.ms.setdefault(path, {})
        spent[stage] = spent.get(stage, 0.0) + (now - started) * 1000
        self._charged(stage, path)
        self._ended[path] = now
        self.running = None

    def _charged(self, stage: Stage, path: str) -> None:
        paid, self._spent = cost.spent() - self._spent, cost.spent()
        if paid:
            usd = self.usd.setdefault(path, {})
            usd[stage] = usd.get(stage, 0.0) + paid

    def since_last(self, path: str) -> float:
        """When the last timed call for `path` returned (the start of the untimed stages)."""
        return self._ended.get(path, self.clock())


class TimedPages:
    def __init__(self, inner: PageReader, timer: StageClock) -> None:
        self._inner, self._timer = inner, timer

    def pages(self, file: DrawingFile) -> tuple[Page, ...]:
        started = self._timer.start("normalise", file.path)
        found = self._inner.pages(file)
        self._timer.stop("normalise", file.path, started)
        return found


class TimedExtractor:
    def __init__(self, inner: Extractor, timer: StageClock) -> None:
        self._inner, self._timer = inner, timer

    def extract(self, source: DrawingFile, sheet: Sheet) -> Extracted:
        started = self._timer.start("extract", sheet.file.path)
        found = self._inner.extract(source, sheet)
        self._timer.stop("extract", sheet.file.path, started)
        return found


class TimedCounter:
    def __init__(self, inner: SecondCounter, timer: StageClock) -> None:
        self._inner, self._timer = inner, timer

    def measure(self, source: DrawingFile, sheet: Sheet) -> Sequence[Measurement]:
        started = self._timer.start("second_count", sheet.file.path)
        found = self._inner.measure(source, sheet)
        self._timer.stop("second_count", sheet.file.path, started)
        return found


class CollectingSink:
    """The `DrawingSink` of one group's run: keeps the drawings for the service to store, and
    times the rules and takeoff, which run between the last timed call and the write."""

    def __init__(self, timer: StageClock) -> None:
        self._timer = timer
        self.drawings: dict[str, Drawing] = {}

    def write(self, drawing: Drawing) -> None:
        started = self._timer.since_last(drawing.file)
        self._timer.stop("takeoff", drawing.file, started)
        self.drawings[drawing.file] = drawing

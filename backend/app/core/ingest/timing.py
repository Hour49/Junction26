"""Per-file, per-stage timing of a pipeline run, without touching the pipeline: each port the
stages call is wrapped, and the wrapper notes how long its call took for which sheet. The
pipeline's own trace lines say what each stage found; these say how long it took and which
stage was running when one failed."""

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

from app.core import cost
from app.core.drawing.model import Drawing, Page
from app.core.ingest.model import Stage, StageTrace
from app.core.ingest.ports import Clock
from app.core.pipeline.model import DrawingFile, Extracted, Measurement, Sheet, StepTrace
from app.core.pipeline.ports import Extractor, PageReader, SecondCounter
from app.core.pipeline.steps import listening, now_ms, shifted
from app.core.wording import count


@dataclass
class StageClock:
    """`ms[path][stage]`: time spent in each stage for the sheet at `path`, `usd[path][stage]`
    the model calls it paid for (app/core/cost.py). `running` is the (stage, path) whose call has
    started and not returned: after an exception, the one that failed."""

    clock: Clock
    on_start: Callable[[Stage, str], None] = lambda stage, path: None  # shows the live stage
    # shows the live step: (path, step id, label)
    on_step: Callable[[str, str, str], None] = lambda path, step_id, label: None
    ms: dict[str, dict[Stage, float]] = field(default_factory=dict[str, dict[Stage, float]])
    usd: dict[str, dict[Stage, float]] = field(default_factory=dict[str, dict[Stage, float]])
    faults: dict[str, int] = field(default_factory=dict[str, int])  # model calls that failed
    # what ran inside each stage (decision 0018), `at_ms` after the stage's first call began
    steps: dict[str, dict[Stage, list[StepTrace]]] = field(
        default_factory=dict[str, dict[Stage, list[StepTrace]]]
    )
    running: tuple[Stage, str] | None = None
    _ended: dict[str, float] = field(default_factory=dict[str, float])
    _spent: int = 0  # cost.mark() when the running call started
    _failed: int = 0  # cost.faults() when the running call started

    def start(self, stage: Stage, path: str) -> float:
        self.running = (stage, path)
        self.on_start(stage, path)
        self._spent = cost.mark()
        self._failed = cost.faults()
        return self.clock()

    def stop(self, stage: Stage, path: str, started: float) -> None:
        now = self.clock()
        spent = self.ms.setdefault(path, {})
        spent[stage] = spent.get(stage, 0.0) + (now - started) * 1000
        self._charged(stage, path)
        self._ended[path] = now
        self.running = None

    def _charged(self, stage: Stage, path: str) -> None:
        paid, self._spent = cost.since(self._spent), cost.mark()
        failed, self._failed = cost.faults_since(self._failed), cost.faults()
        if failed:
            self.faults[path] = self.faults.get(path, 0) + failed
        if paid:
            usd = self.usd.setdefault(path, {})
            usd[stage] = usd.get(stage, 0.0) + paid

    def add_steps(
        self, stage: Stage, path: str, steps: Sequence[StepTrace], began: float, at_ms: float
    ) -> None:
        """`steps` of a call to `stage` for `path` that began at `began` on the steps' clock
        (`now_ms`) and `at_ms` into the stage's time: a stage called twice, as on a fallback,
        lists both calls' steps one after the other."""
        if steps:
            moved = shifted(steps, at_ms - began)
            self.steps.setdefault(path, {}).setdefault(stage, []).extend(moved)

    def since_last(self, path: str) -> float:
        """When the last timed call for `path` returned (the start of the untimed stages)."""
        return self._ended.get(path, self.clock())


class TimedPages:
    def __init__(self, inner: PageReader, timer: StageClock) -> None:
        self._inner, self._timer = inner, timer

    def pages(self, file: DrawingFile) -> tuple[Page, ...]:
        before = self._timer.ms.get(file.path, {}).get("normalise", 0.0)
        started = self._timer.start("normalise", file.path)
        began = now_ms()
        found = self._inner.pages(file)
        self._timer.stop("normalise", file.path, started)
        first = found[0] if found else None
        step = StepTrace(
            id="pages",
            label="Page size",
            did=f"{count(len(found), 'page')}"
            + (f", page 1 is {first.width:g} x {first.height:g} {first.unit}" if first else ""),
            at_ms=began,
            ms=now_ms() - began,
        )
        self._timer.add_steps("normalise", file.path, [step], began, before)
        return found


class TimedExtractor:
    def __init__(self, inner: Extractor, timer: StageClock) -> None:
        self._inner, self._timer = inner, timer

    def extract(self, source: DrawingFile, sheet: Sheet) -> Extracted:
        path = sheet.file.path
        before = self._timer.ms.get(path, {}).get("extract", 0.0)
        started = self._timer.start("extract", path)
        began = now_ms()  # the steps' clock: they say when they began on it
        with listening(lambda step_id, label: self._timer.on_step(path, step_id, label)):
            found = self._inner.extract(source, sheet)
        self._timer.stop("extract", path, started)
        self._timer.add_steps("extract", path, found.steps, began, before)
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


def with_steps(
    stages: Sequence[StageTrace], steps: dict[Stage, list[StepTrace]]
) -> list[StageTrace]:
    """`stages` with the steps that ran inside each, in start order (decision 0018), each id
    once in its stage (`unique`)."""
    return [
        stage.model_copy(
            update={"steps": unique(sorted(steps[stage.stage], key=lambda step: step.at_ms))}
        )
        if steps.get(stage.stage)
        else stage
        for stage in stages
    ]


def unique(steps: Sequence[StepTrace]) -> tuple[StepTrace, ...]:
    """`steps` with an id met again given a number: `detector`, `detector-2`, `detector-3`, so
    a live `step_id` names one step."""
    seen: set[str] = set()
    found: list[StepTrace] = []
    for step in steps:
        step_id, n = step.id, 1
        while step_id in seen:
            n += 1
            step_id = f"{step.id}-{n}"
        seen.add(step_id)
        found.append(step if step_id == step.id else step.model_copy(update={"id": step_id}))
    return tuple(found)

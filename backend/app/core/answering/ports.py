"""What answering needs from outside, as Protocols (see app/core/pipeline/ports.py)."""

from typing import Protocol

from app.core.answering.model import Answer, Prior, Query, TableQuery, Unsupported
from app.core.drawing.model import Drawing


class QuestionParser(Protocol):
    """Question text in any of the dataset's languages to a query over the drawing model."""

    def parse(self, text: str) -> Query | TableQuery | Unsupported: ...


class DrawingSource(Protocol):
    """The stored drawing model of a file, or None when the file has none."""

    def drawing(self, file: str) -> Drawing | None: ...


class AnswerSink(Protocol):
    """Where an answer goes."""

    def write(self, answer: Answer) -> None: ...


class Clock(Protocol):
    """Seconds from a fixed point, for measuring latency."""

    def __call__(self) -> float: ...


class AnswerPrior(Protocol):
    """The best estimate for a family of questions (`Query.family()`) on one dataset source,
    or None when there is none."""

    def prior(self, source: str, family: str) -> Prior | None: ...

"""What answering needs from outside, as Protocols (see app/core/pipeline/ports.py)."""

from typing import Protocol

from app.core.answering.model import Answer, Query, Unsupported
from app.core.drawing.model import Drawing


class QuestionParser(Protocol):
    """Question text in any of the dataset's languages to a query over the drawing model."""

    def parse(self, text: str) -> Query | Unsupported: ...


class DrawingSource(Protocol):
    """The stored drawing model of a file, or None when the file has none."""

    def drawing(self, file: str) -> Drawing | None: ...


class AnswerSink(Protocol):
    """Where an answer goes."""

    def write(self, answer: Answer) -> None: ...


class Clock(Protocol):
    """Seconds from a fixed point, for measuring latency."""

    def __call__(self) -> float: ...

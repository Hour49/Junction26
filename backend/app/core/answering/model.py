"""Questions, queries and answers. `Answer` serialises as answer_v1
(docs/decisions/0002-answer-format.md)."""

from typing import Literal

from pydantic import Field

from app.core.drawing.model import Box
from app.core.model import Frozen

Unit = Literal["count", "m", "m2", "m3", "ft", "ft2"]


class Question(Frozen):
    id: int = Field(ge=1)  # the 1-based line number in the dataset's questions.jsonl
    file: str  # the drawing file it is asked about
    text: str


class Query(Frozen):
    """A question the drawing model can be asked: one quantity of the takeoff."""

    quantity: str  # a key of COUNT_KEYS


class Unsupported(Frozen):
    """A question the parser cannot turn into a query, and why."""

    reason: str


class Evidence(Frozen):
    file: str
    page: int = Field(ge=1)
    box: Box


class Answer(Frozen):
    id: int = Field(ge=1)
    answer: int | float | str | None  # None: no answer
    unit: Unit | None
    evidence: tuple[Evidence, ...]
    method: str = Field(min_length=1)  # how it was answered, or `refused:<why>`
    cost_usd: float = Field(ge=0)
    latency_s: float = Field(ge=0)

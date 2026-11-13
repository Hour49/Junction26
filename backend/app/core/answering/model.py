"""Questions, queries and answers. `Answer` serialises as answer_v1
(docs/decisions/0002-answer-format.md)."""

from typing import Literal

from pydantic import Field

from app.core.drawing.model import Box
from app.core.model import Frozen
from app.core.pipeline.model import Measure
from app.core.pipeline.takeoff import quantity_key

Unit = Literal["count", "m", "m2", "m3", "ft", "ft2"]


class Question(Frozen):
    id: int = Field(ge=1)  # the 1-based line number in the dataset's questions.jsonl
    file: str  # the drawing file it is asked about
    text: str


class Query(Frozen):
    """A question the drawing model can be asked: one quantity of the takeoff
    (app/core/pipeline/takeoff.py). `subject` is an element class, `room`, `room:<type>`,
    `apartment`, `plan` or a combined count of app/core/pipeline/rules.py COMBINED; the other
    fields pick the items. Its `key()` is the takeoff key the answer is looked up under."""

    measure: Measure = "count"
    subject: str = Field(min_length=1)
    label: str | None = None  # every room with this printed name
    name: str | None = None  # the one room with this name or number
    apartment: str | None = None  # the apartment with this label
    storey: str | None = None  # only the items on this storey
    indoor: bool = False  # only rooms that are not outdoor
    model: bool = False  # the whole building model, not this sheet

    def key(self) -> str:
        return quantity_key(
            self.measure,
            self.subject,
            label=self.label,
            name=self.name,
            apartment=self.apartment,
            storey=self.storey,
            indoor=self.indoor,
            model=self.model,
        )


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
    abstain: bool | None = None  # answer_v1.1: True on a refusal
    explanation: str | None = None  # answer_v1.1: why it was refused

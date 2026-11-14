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
    largest: bool = False  # the largest of the rooms picked, not their sum
    read_as: tuple[str, ...] = ()  # misspelt words read as others: "'mnay' as 'many'"

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
            largest=self.largest,
        )

    def family(self) -> str:
        """The key with each filter's value masked as `*`: every question of the same kind
        whatever room, label, apartment or storey it names (the key of an `AnswerPrior`)."""

        def masked(value: str | None) -> str | None:
            return None if value is None else WILDCARD

        return quantity_key(
            self.measure,
            self.subject,
            label=masked(self.label),
            name=masked(self.name),
            apartment=masked(self.apartment),
            storey=masked(self.storey),
            indoor=self.indoor,
            model=self.model,
            largest=self.largest,
        )


WILDCARD = "*"


def source_of(file: str) -> str:
    """The dataset source of a drawing path, `data/<source>/<name>`; "" for any other path."""
    parts = file.split("/")
    return parts[1] if len(parts) > 2 and parts[0] == "data" else ""


class Prior(Frozen):
    """The best estimate for a family of questions when the drawing gives no value: the dev
    answers' mode (counts) or median (area, length, volume). `confidence` is the share of dev
    answers that value gets right; `n` how many dev answers it rests on."""

    value: int | float
    unit: Unit
    confidence: float = Field(ge=0.0, le=1.0)
    n: int = Field(ge=1)


class TableFilter(Frozen):
    """Rows whose cell, in the column that holds one of `values`, is one of them. The column is
    found from the values (the one column whose cells hold them); `cue`, the words the question
    puts before them ("frame", "note", "wide"), picks among several. `every`: each column the
    cue names must hold it ("all four walls finished with W1")."""

    values: tuple[str, ...] = Field(min_length=1)  # as printed: a code, a number, a dimension
    cue: tuple[str, ...] = ()
    every: bool = False


class TableQuery(Frozen):
    """A question about a schedule printed on the sheet (Drawing.tables): count its rows, sum a
    column, or read cells. `kind`: what its rows are ("door", "room"); `column` (sum, read): the
    words that name the column(s) to sum or read; `meaning`: a read also gives what each code
    means, from the sheet's legend tables."""

    op: Literal["count", "sum", "read"]
    kind: str | None = None
    column: tuple[tuple[str, ...], ...] = ()  # one tuple of words per column read or summed
    filters: tuple[TableFilter, ...] = ()
    every_row: bool = False  # a count or sum over the whole table was asked for ("all", "listed")
    meaning: bool = False

    def family(self) -> str:
        """The prior's key: what is done to which kind of table."""
        return f"table:{self.op}:{self.kind or WILDCARD}"


class Unsupported(Frozen):
    """A question the parser cannot turn into a query, and why."""

    reason: str


# Unsupported reasons the answer explains in its own words: a count where answering would drop
# part of the question (R1-5-2).
SEVERAL_THINGS = "a count that names more than one kind of thing"
IN_ONE_ROOM = "a count within one room is not taken off"


class Evidence(Frozen):
    file: str
    page: int = Field(ge=1)
    box: Box


class ConflictValue(Frozen):
    """answer_v1.1: one of the values two methods measured for the answer, with its evidence."""

    value: int | float
    unit: Unit | None
    method: str = Field(min_length=1)
    file: str
    page: int | None = Field(default=None, ge=1)  # None for a value from an IFC model
    box: Box | None = None


class Answer(Frozen):
    id: int = Field(ge=1)
    answer: int | float | str | None  # None: no answer
    unit: Unit | None
    evidence: tuple[Evidence, ...]
    method: str = Field(min_length=1)  # how it was answered, or `refused:<why>`
    cost_usd: float = Field(ge=0)
    latency_s: float = Field(ge=0)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)  # answer_v1.1
    sure: bool | None = (
        None  # answer_v1.1: confidence at or above the gate (GATE_POLICY); None: ungated
    )
    abstain: bool | None = None  # answer_v1.1: True on a refusal; `answer` may hold a prior
    explanation: str | None = None  # answer_v1.1: why it was refused, or what an estimate rests on
    estimate: bool | None = None  # answer_v1.1: True when the value rests on an estimated reading
    conflicts: tuple[ConflictValue, ...] | None = None  # answer_v1.1: the values that disagree
    resolution: str | None = None  # answer_v1.1: which value was kept, and why

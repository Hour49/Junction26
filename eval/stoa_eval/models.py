"""File formats: the dataset's questions, our golden rows, and the answers our system writes.

`Answer` is the interface between the system and this scorer (answer_v1). Its JSON Schema is
generated into eval/schemas/ (`python -m stoa_eval schema`) and a test fails when it drifts.
"""

import json
from pathlib import Path
from typing import Annotated, Literal, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictFloat,
    StrictInt,
    StrictStr,
    model_validator,
)

Unit = Literal["count", "m", "m2", "m3", "ft", "ft2"]
QuestionType = Literal["count", "area", "length", "volume", "text", "other"]
Split = Literal["dev", "holdout"]
AnswerValue = StrictInt | StrictFloat | StrictStr
FREE_TEXT_TYPES: frozenset[str] = frozenset({"text", "other"})
Fraction = Annotated[float, Field(ge=0.0, le=1.0)]


class Question(BaseModel):
    """One line of the dataset's questions.jsonl."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    path: str
    question: str
    answer: AnswerValue
    unit: Unit | None
    type: QuestionType

    @model_validator(mode="after")
    def _answer_matches_type(self) -> Self:
        if self.type in FREE_TEXT_TYPES:
            ok = isinstance(self.answer, str)
        elif self.type == "count":
            ok = isinstance(self.answer, int)
        else:
            ok = not isinstance(self.answer, str)
        if not ok:
            raise ValueError(f"a {self.type} question can't have the answer {self.answer!r}")
        return self


class GoldenItem(Question):
    """A selected question with what the selection knows about it (golden_v0.jsonl)."""

    id: int = Field(ge=1, description="1-based line number in questions.jsonl")
    source: str = Field(description="dataset folder, e.g. swiss_dwellings")
    language: str = Field(description="language code from the question text, e.g. en, de")
    template: str = Field(description="question with quoted names and numbers masked")
    group: str = Field(description="drawing or building; a group's questions share one split")
    split: Split


class Evidence(BaseModel):
    """Where on a drawing the answer came from."""

    model_config = ConfigDict(extra="forbid")

    file: str = Field(description="dataset path, e.g. data/swiss_dwellings/site1_bldg2_floor3.pdf")
    page: int = Field(ge=1, description="1-based page; 1 for a single image")
    box: tuple[Fraction, Fraction, Fraction, Fraction] = Field(
        description="[x0, y0, x1, y1] as fractions of the page width and height, origin top left"
    )

    @model_validator(mode="after")
    def _box_is_ordered(self) -> Self:
        x0, y0, x1, y1 = self.box
        if x0 > x1 or y0 > y1:
            raise ValueError(f"box {list(self.box)} needs x0 <= x1 and y0 <= y1")
        return self


class Answer(BaseModel):
    """One line our system writes per question (answer_v1)."""

    model_config = ConfigDict(extra="forbid", title="Answer_v1")

    id: int = Field(ge=1, description="the question's 1-based line number in questions.jsonl")
    answer: AnswerValue | None = Field(description="null means no answer, scored as wrong")
    unit: Unit | None = Field(description="count, m, m2, m3, ft or ft2; null for text")
    evidence: list[Evidence] = Field(description="may be empty")
    method: str = Field(min_length=1, description="how it was answered, e.g. ifc, dxf, vision")
    cost_usd: float = Field(ge=0.0)
    latency_s: float = Field(ge=0.0)


SCHEMA_DIR = Path(__file__).resolve().parent.parent / "schemas"
SCHEMA_MODELS: dict[str, type[BaseModel]] = {
    "answer_v1.schema.json": Answer,
    "golden_v0.schema.json": GoldenItem,
}


def render_schemas() -> dict[str, str]:
    """File name -> JSON Schema text, as committed in eval/schemas/."""
    return {
        name: json.dumps(model.model_json_schema(), indent=2, ensure_ascii=False) + "\n"
        for name, model in SCHEMA_MODELS.items()
    }

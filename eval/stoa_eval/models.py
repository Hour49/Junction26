"""File formats: the dataset's questions, our golden rows, and the answers our system writes.

`Answer` is the interface between the system and this scorer (answer_v1). Its JSON Schema is
generated into eval/schemas/ (`python -m stoa_eval schema`) and a test fails when it drifts.
"""

import json
from pathlib import Path
from typing import Annotated, Literal, Self

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    StrictFloat,
    StrictInt,
    StrictStr,
    model_validator,
)

from .extraction import Extraction

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


class NumberedQuestion(Question):
    """A dataset line with its id (data/stoa/split/dev.jsonl and eval.jsonl)."""

    id: int = Field(ge=1, description="1-based line number in questions.jsonl")


class GoldenItem(NumberedQuestion):
    """A selected question with what the selection knows about it (golden_<version>.jsonl)."""

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


Against = Literal["golden", "all", "dev", "eval"]


class Stats(BaseModel):
    """Aggregate numbers for a group of questions."""

    model_config = ConfigDict(extra="forbid")

    n: int = Field(ge=0)
    correct: int = Field(ge=0)
    accuracy: float | None
    answered: int | None = Field(description="all/dev/eval runs only")
    coverage: float | None = Field(description="answered / n; all/dev/eval runs only")


class RunRecord(BaseModel):
    """One recorded score run in eval/results/runs.jsonl (run_record_v1). The repo is public, so
    a row holds aggregates only: no question text, answers, templates or file names."""

    model_config = ConfigDict(extra="forbid", title="RunRecord_v1")

    recorded_at: AwareDatetime = Field(description="from the clock, Europe/Helsinki")
    commit: str = Field(pattern=r"^[0-9a-f]{7,40}$", description="short git sha of HEAD")
    dirty: bool = Field(description="tracked files had uncommitted changes")
    name: str = Field(min_length=1, description="the method's name")
    note: str | None
    against: Against
    golden_version: str | None = Field(description="the golden set's version; golden runs only")
    milestone: bool
    part: Literal["answering"] = Field(
        default="answering", description="golden Part 2 (answers); rows before v2 have no field"
    )
    reads: Literal["gold-extraction", "pipeline-extraction"] | None = Field(
        default=None, description="what the answerer read as input; golden v2 runs only"
    )
    questions_sha256: str
    score_sha256: str = Field(description="sha256 of the full score JSON (gitignored runs folder)")
    overall: Stats
    numeric: Stats
    by_source_type: dict[str, Stats]
    evidence_coverage: float | None
    cost_total_usd: float
    cost_mean_usd: float | None
    latency_mean_s: float | None
    latency_p95_s: float | None

    @model_validator(mode="after")
    def _eval_only_at_milestones(self) -> Self:
        if self.against == "eval" and not self.milestone:
            raise ValueError("a run against the sealed eval split is recorded only as a milestone")
        return self


class Ratio(BaseModel):
    model_config = ConfigDict(extra="forbid")

    n: int = Field(ge=0)
    correct: int = Field(ge=0)
    rate: float | None


class ExtractionRecord(BaseModel):
    """One recorded Part 1 run (extraction vs gold) in eval/results/runs.jsonl, next to the answer
    rows; aggregates only (extraction_record_v1)."""

    model_config = ConfigDict(extra="forbid", title="ExtractionRecord_v1")

    recorded_at: AwareDatetime = Field(description="from the clock, Europe/Helsinki")
    commit: str = Field(pattern=r"^[0-9a-f]{7,40}$", description="short git sha of HEAD")
    dirty: bool = Field(description="tracked files had uncommitted changes")
    name: str = Field(min_length=1, description="the method's name")
    note: str | None
    part: Literal["extraction"] = Field(description="golden Part 1")
    against: Literal["golden", "dev", "eval"]
    golden_version: str | None = Field(description="the golden set's version; golden runs only")
    milestone: bool
    gold_sha256: str = Field(description="sha256 over the gold files' names and contents")
    score_sha256: str = Field(description="sha256 of the full score JSON (gitignored runs folder)")
    files: int = Field(ge=0)
    predicted: int = Field(ge=0)
    multiplicity: bool = Field(description="counts weighed elements by attrs.multiplicity")
    elements_f1: float | None
    elements_f1_by_source: dict[str, float | None]
    room_f1: float | None
    room_type_accuracy: float | None
    room_area_accuracy: float | None
    plans_exact: Ratio
    counts_exact: Ratio
    counts_exact_by_source: dict[str, Ratio]
    scale_status: Ratio = Field(description="scale cases whose predicted status is as expected")
    scale_m_per_unit: Ratio = Field(description="scaled gold cases predicted scaled within 2%")
    scale_m_per_unit_by_case: dict[str, Ratio]
    scale_estimate_median_error: float | None = Field(description="estimates vs reference")
    scale_estimate_within_20: float | None

    @model_validator(mode="after")
    def _eval_only_at_milestones(self) -> Self:
        if self.against == "eval" and not self.milestone:
            raise ValueError("a run against the sealed eval split is recorded only as a milestone")
        return self


SCHEMA_DIR = Path(__file__).resolve().parent.parent / "schemas"
SCHEMA_MODELS: dict[str, type[BaseModel]] = {
    "answer_v1.schema.json": Answer,
    "golden_v0.schema.json": GoldenItem,
    "run_record_v1.schema.json": RunRecord,
    "extraction_record_v1.schema.json": ExtractionRecord,
    "extraction_v1.schema.json": Extraction,
}


def render_schemas() -> dict[str, str]:
    """File name -> JSON Schema text, as committed in eval/schemas/."""
    return {
        name: json.dumps(model.model_json_schema(), indent=2, ensure_ascii=False) + "\n"
        for name, model in SCHEMA_MODELS.items()
    }

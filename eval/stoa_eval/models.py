"""File formats: the dataset's questions, our golden rows, and the answers our system writes.

`Answer` is the interface between the system and this scorer (answer_v1, with the optional
answer_v1.1 fields of the 2026-11-13 amendment to decision 0002). Its JSON Schema is generated into
eval/schemas/ (`python -m stoa_eval schema`) and a test fails when it drifts.
"""

import json
from pathlib import Path
from typing import Annotated, Literal, Self

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
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
        if not fits_type(self.type, self.answer):
            raise ValueError(f"a {self.type} question can't have the answer {self.answer!r}")
        return self


def fits_type(type_: QuestionType, answer: AnswerValue) -> bool:
    if type_ in FREE_TEXT_TYPES:
        return isinstance(answer, str)
    if type_ == "count":
        return isinstance(answer, int)
    return not isinstance(answer, str)


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


PageBox = tuple[Fraction, Fraction, Fraction, Fraction]


def _ordered(box: PageBox | None) -> None:
    if box is not None and (box[0] > box[2] or box[1] > box[3]):
        raise ValueError(f"box {list(box)} needs x0 <= x1 and y0 <= y1")


class Evidence(BaseModel):
    """Where on a drawing the answer came from."""

    model_config = ConfigDict(extra="forbid")

    file: str = Field(description="dataset path, e.g. data/swiss_dwellings/site1_bldg2_floor3.pdf")
    page: int = Field(ge=1, description="1-based page; 1 for a single image")
    box: PageBox = Field(
        description="[x0, y0, x1, y1] as fractions of the page width and height, origin top left"
    )
    polygon: Annotated[list[tuple[Fraction, Fraction]], Field(min_length=3)] | None = Field(
        default=None, description="v1.1: the outline as page fractions"
    )
    global_id: str | None = Field(default=None, min_length=1, description="v1.1: IFC GlobalId")

    @model_validator(mode="after")
    def _box_is_ordered(self) -> Self:
        _ordered(self.box)
        return self


class ConflictValue(BaseModel):
    """v1.1: one of the disagreeing values behind an answer."""

    model_config = ConfigDict(extra="forbid")

    value: AnswerValue
    unit: Unit | None
    method: str = Field(min_length=1)
    file: str
    page: int | None = Field(default=None, ge=1, description="null for a value from an IFC model")
    box: PageBox | None = None

    @model_validator(mode="after")
    def _box_is_ordered(self) -> Self:
        _ordered(self.box)
        return self


class Excluded(BaseModel):
    """v1.1: a region deliberately not counted, and why."""

    model_config = ConfigDict(extra="forbid")

    file: str
    page: int = Field(ge=1)
    box: PageBox
    reason: str = Field(min_length=1)

    @model_validator(mode="after")
    def _box_is_ordered(self) -> Self:
        _ordered(self.box)
        return self


class Answer(BaseModel):
    """One line our system writes per question (answer_v1; the fields after latency_s are the
    optional answer_v1.1 additions)."""

    model_config = ConfigDict(extra="forbid", title="Answer_v1.1")

    id: int = Field(ge=1, description="the question's 1-based line number in questions.jsonl")
    answer: AnswerValue | None = Field(description="null means no answer, scored as wrong")
    unit: Unit | None = Field(description="count, m, m2, m3, ft or ft2; null for text")
    evidence: list[Evidence] = Field(description="may be empty")
    method: str = Field(min_length=1, description="how it was answered, e.g. ifc, dxf, vision")
    cost_usd: float = Field(ge=0.0)
    latency_s: float = Field(ge=0.0)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0, description="v1.1: 0..1")
    abstain: StrictBool | None = Field(
        default=None, description="v1.1: too unsure to answer; `answer` still holds the estimate"
    )
    conflicts: list[ConflictValue] | None = Field(
        default=None, min_length=2, description="v1.1: the values that disagree"
    )
    resolution: str | None = Field(
        default=None, min_length=1, description="v1.1: which value was kept, and why"
    )
    explanation: str | None = Field(default=None, description="v1.1: how the answer was reached")
    excluded: list[Excluded] | None = Field(default=None, description="v1.1: regions not counted")
    inputs: list[str] | None = Field(default=None, description="v1.1: the files read")

    @model_validator(mode="after")
    def _resolution_needs_conflicts(self) -> Self:
        if self.resolution is not None and self.conflicts is None:
            raise ValueError("resolution explains conflicts: give conflicts too")
        return self


ExtraKind = Literal["paraphrase", "unanswerable", "conflict"]
EXTRA_ID_MIN = 1_000_001  # above every dataset line number
EXTRA_STYLES: dict[str, frozenset[str]] = {  # review-7's convention, accepted 23:12
    "paraphrase": frozenset({"reworded", "restructured", "typo", "hint_dropped"}),
    "unanswerable": frozenset({"scale", "fact", "class"}),
}


class Expect(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answer: AnswerValue | None = None
    abstain: StrictBool | None = None
    conflict_values: Annotated[list[StrictInt | StrictFloat], Field(min_length=2)] | None = None


class ExtraItem(BaseModel):
    """One line of part2_answering/extras.jsonl: a question Stoa didn't write (formats-v1-1 §3).
    Scored as its own slice, never in the headline."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    path: str
    question: str
    answer: AnswerValue | None = Field(description="null for unanswerable lines")
    unit: Unit | None
    type: QuestionType | Literal["unanswerable"] = Field(
        description="the origin's type; unanswerable for unanswerable lines"
    )
    id: int = Field(ge=EXTRA_ID_MIN, description="from 1000001 up, never a dataset line")
    source: str
    language: str
    template: str
    group: str
    split: Literal["dev"] = Field(description="extras are made from dev files only")
    kind: ExtraKind
    origin_id: int | None = Field(description="paraphrase: the dataset question it rewords")
    expect: Expect
    why: str | None
    style: str | None = Field(
        default=None, description="paraphrase: reworded, restructured, typo, hint_dropped; "
        "unanswerable: scale, fact, class",
    )  # fmt: skip

    @model_validator(mode="after")
    def _fits_kind(self) -> Self:
        expect = self.expect
        problems: list[str] = []
        styles = EXTRA_STYLES.get(self.kind)
        if styles is not None and self.style is not None and self.style not in styles:
            problems.append(f"style {self.style!r} is not one of {sorted(styles)}")
        if (self.kind == "unanswerable") != (self.type == "unanswerable"):
            problems.append("type is unanswerable exactly on unanswerable lines")
        if self.kind == "unanswerable":
            if expect.abstain is not True or expect.answer is not None or expect.conflict_values:
                problems.append("unanswerable expects only abstain: true")
            if self.answer is not None or self.unit is not None:
                problems.append("unanswerable has answer and unit null")
            if not self.why:
                problems.append("unanswerable says why")
        elif self.type != "unanswerable":
            if expect.answer is None or expect.answer != self.answer or expect.abstain:
                problems.append(f"{self.kind} expects its own answer, without abstain")
            elif not fits_type(self.type, expect.answer):
                problems.append(f"a {self.type} question can't have the answer {expect.answer!r}")
            if (self.kind == "conflict") != (expect.conflict_values is not None):
                problems.append("conflict_values belong to conflict lines, and they need them")
            if self.kind == "conflict" and self.type in FREE_TEXT_TYPES:
                problems.append("a conflict line asks for a number")
            for value in expect.conflict_values or []:
                if not fits_type(self.type, value):
                    problems.append(f"a {self.type} question can't have the value {value!r}")
        if self.kind == "paraphrase" and self.origin_id is None:
            problems.append("a paraphrase names its origin_id")
        if problems:
            raise ValueError(f"extras line {self.id}: " + "; ".join(problems))
        return self


Against = Literal["golden", "all", "dev", "eval"]


class Stats(BaseModel):
    """Aggregate numbers for a group of questions."""

    model_config = ConfigDict(extra="forbid")

    n: int = Field(ge=0)
    correct: int = Field(ge=0)
    accuracy: float | None
    answered: int | None = Field(description="all/dev/eval runs only")
    coverage: float | None = Field(description="answered / n; all/dev/eval runs only")


class Ratio(BaseModel):
    model_config = ConfigDict(extra="forbid")

    n: int = Field(ge=0)
    correct: int = Field(ge=0)
    rate: float | None


class ExtrasRecord(BaseModel):
    """Part 2 extras, per kind (formats-v1-1 §3)."""

    model_config = ConfigDict(extra="forbid")

    extras_sha256: str
    paraphrase: Ratio = Field(description="paraphrases answered right")
    paraphrase_origin: Ratio = Field(description="their origin questions answered right")
    paraphrase_gap: float | None = Field(description="paraphrase minus origin accuracy")
    unanswerable_abstained: Ratio = Field(description="unanswerable lines with abstain: true")
    conflict_pass: Ratio = Field(description="both values in `conflicts` and the answer right")
    conflict_values_shown: Ratio
    conflict_answer_right: Ratio


class CalibrationBucket(BaseModel):
    model_config = ConfigDict(extra="forbid")

    low: float
    high: float
    n: int = Field(ge=0)
    correct: int = Field(ge=0)
    accuracy: float | None
    mean_confidence: float | None


class AnswerV11Record(BaseModel):
    """answer_v1.1 on the golden questions: abstention and calibration (never headline)."""

    model_config = ConfigDict(extra="forbid")

    answers: int = Field(ge=0, description="golden questions with an answer line")
    abstained: int = Field(ge=0)
    abstain_rate: float | None
    not_abstained_accuracy: Ratio
    abstained_accuracy: Ratio = Field(description="the best estimate in `answer`, judged")
    with_confidence: int = Field(ge=0)
    calibration: list[CalibrationBucket]


class TablesRecord(BaseModel):
    """Part 1 schedules (truth tables, or tables next to elements); not headline."""

    model_config = ConfigDict(extra="forbid")

    files: int = Field(ge=0)
    tables_found: Ratio = Field(description="gold tables matched by title or box IoU >= 0.3")
    tables_extra: int = Field(ge=0, description="predicted tables matching no gold table")
    row_recall: Ratio
    row_precision: Ratio = Field(description="rows of found tables only")
    cell_accuracy: Ratio = Field(description="non-key cells of matched rows")


class AreaEstimates(BaseModel):
    """Estimated gold room areas of one source against the predicted areas."""

    model_config = ConfigDict(extra="forbid")

    rooms: int = Field(ge=0, description="matched rooms with an estimated gold area")
    missing: int = Field(ge=0, description="of those, without a predicted area")
    median_error: float | None
    within_10: float | None
    within_20: float | None


class ConflictCounts(BaseModel):
    model_config = ConfigDict(extra="forbid")

    found: Ratio = Field(description="gold conflict entries the prediction calls a conflict")
    agree: int = Field(ge=0, description="gold agree entries")
    false_alarms: int = Field(ge=0, description="gold agree entries called a conflict")
    unlisted: int = Field(ge=0, description="predicted conflicts gold has no entry for")


class ConflictsRecord(BaseModel):
    """Part 1 conflict slice (ingestion stage 8): recall and false alarms; not headline."""

    model_config = ConfigDict(extra="forbid")

    files: int = Field(ge=0)
    overall: ConflictCounts
    by_quantity: dict[str, ConflictCounts]


class RunRecord(BaseModel):
    """One recorded score run, a file in eval/results/runs/ (run_record_v1). The repo is public, so
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
    extras: ExtrasRecord | None = Field(
        default=None, description="the extras slice (golden v2 with extras.jsonl); not headline"
    )
    answer_v1_1: AnswerV11Record | None = Field(
        default=None, description="abstain and calibration, when answers carry v1.1 fields"
    )

    @model_validator(mode="after")
    def _eval_only_at_milestones(self) -> Self:
        if self.against in ("eval", "all") and not self.milestone:
            raise ValueError("a run against the sealed eval split is recorded only as a milestone")
        return self


class ExtractionRecord(BaseModel):
    """One recorded Part 1 run (extraction vs gold), a file in eval/results/runs/ next to the
    answer runs; aggregates only (extraction_record_v1)."""

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
    room_area_accuracy: float | None = Field(description="exact gold areas within 2%")
    room_area_estimates: dict[str, AreaEstimates] = Field(
        default_factory=dict[str, AreaEstimates], description="per source; estimated gold areas"
    )
    plans_exact: Ratio
    counts_exact: Ratio
    counts_exact_by_source: dict[str, Ratio]
    scale_status: Ratio = Field(description="scale cases whose predicted status is as expected")
    scale_status_by_source: dict[str, Ratio] = Field(default_factory=dict[str, Ratio])
    scale_m_per_unit: Ratio = Field(description="scaled gold cases predicted scaled within 2%")
    scale_m_per_unit_by_case: dict[str, Ratio]
    scale_estimate_median_error: float | None = Field(description="estimates vs reference")
    scale_estimate_within_20: float | None
    tables: TablesRecord | None = Field(default=None, description="when the gold has tables")
    conflicts: ConflictsRecord | None = Field(
        default=None, description="when the gold has a conflict slice"
    )

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
    "extras_v1.schema.json": ExtraItem,
}


def render_schemas() -> dict[str, str]:
    """File name -> JSON Schema text, as committed in eval/schemas/."""
    return {
        name: json.dumps(model.model_json_schema(), indent=2, ensure_ascii=False) + "\n"
        for name, model in SCHEMA_MODELS.items()
    }

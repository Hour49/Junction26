"""Part 1 scale cases, by kind of evidence (Bogdan, 2026-11-13 22:31: "print rooms with areas,
calculate it from dimension lines, from the scale, and those with nothing say no scale and those who
say no scale the rsult should be not to scale").

gold case -> expected prediction -> scored:
- scale text or bar -> scaled -> status, m_per_unit within 2%
- printed areas (no text or bar) -> scaled -> same
- dimension lines only -> scaled -> same
- nothing (no_scale) -> estimated or no_scale -> status; estimates against reference_m_per_unit
- a not-to-scale note -> not_to_scale -> status

Scales compare as metres across the first page (m_per_unit x page width), so a prediction rendered
at another resolution or unit still compares. A gold file whose notes start "scale not reviewed"
or "scale dropped" (two checks disagreed) is not a scale case.
"""

from statistics import median
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, computed_field

from .extraction import Extraction

ScaleCase = Literal[
    "scale_text_or_bar", "printed_areas", "dimension_lines", "nothing", "not_to_scale"
]
SCALE_CASES: tuple[ScaleCase, ...] = ScaleCase.__args__
GOLD_STATUSES = ("scaled", "no_scale", "not_to_scale")
PRED_COLUMNS = ("scaled", "estimated", "no_scale", "not_to_scale", "missing")
EXCLUDED_NOTES = ("scale not reviewed", "scale dropped")
SCALE_TOLERANCE = 0.02
_SLACK = 1e-9


def case_of(gold: Extraction) -> ScaleCase | None:
    """The gold file's scale case, or None when it is not one (excluded by a note)."""
    if any(note.lower().startswith(EXCLUDED_NOTES) for note in gold.notes):
        return None
    scale = gold.scale
    if scale.status == "estimated":
        raise ValueError(f"{gold.file}: gold scale cannot be estimated")
    if scale.status == "not_to_scale":
        return "not_to_scale"
    if scale.status == "no_scale":
        return "nothing"
    if "scale_text" in scale.evidence or "scale_bar" in scale.evidence:
        return "scale_text_or_bar"
    if "printed_areas" in scale.evidence:
        return "printed_areas"
    return "dimension_lines"


def page_metres(m_per_unit: float, extraction: Extraction) -> float:
    return m_per_unit * extraction.pages[0].width


def relative_error(pred: Extraction, gold: Extraction, want_m_per_unit: float) -> float | None:
    if pred.scale.m_per_unit is None:
        return None
    want = page_metres(want_m_per_unit, gold)
    return abs(page_metres(pred.scale.m_per_unit, pred) - want) / want


class Rate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    n: int = 0
    correct: int = 0

    @computed_field
    @property
    def rate(self) -> float | None:
        return self.correct / self.n if self.n else None

    def add(self, ok: bool) -> None:
        self.n += 1
        self.correct += ok


class CaseStats(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Rate = Field(default_factory=Rate, description="status as expected")
    m_per_unit: Rate = Field(
        default_factory=Rate, description="scaled, within 2%; scaled gold only"
    )


class Estimates(BaseModel):
    """`estimated` predictions on gold without a scale, against reference_m_per_unit."""

    model_config = ConfigDict(extra="forbid")

    errors: list[float] = Field(default_factory=list[float], description="relative, per file")

    @computed_field
    @property
    def median_error(self) -> float | None:
        return median(self.errors) if self.errors else None

    @computed_field
    @property
    def within_10(self) -> float | None:
        return (
            sum(e <= 0.10 + _SLACK for e in self.errors) / len(self.errors) if self.errors else None
        )

    @computed_field
    @property
    def within_20(self) -> float | None:
        return (
            sum(e <= 0.20 + _SLACK for e in self.errors) / len(self.errors) if self.errors else None
        )


class ScaleScore(BaseModel):
    model_config = ConfigDict(extra="forbid")

    confusion: dict[str, dict[str, int]] = Field(
        default_factory=lambda: {gold: dict.fromkeys(PRED_COLUMNS, 0) for gold in GOLD_STATUSES},
        description="gold status -> predicted status (or missing) -> files",
    )
    by_case: dict[str, CaseStats] = Field(default_factory=dict[str, CaseStats])
    by_evidence: dict[str, Rate] = Field(
        default_factory=dict[str, Rate],
        description="m_per_unit pass per evidence kind, scaled gold",
    )
    estimates: Estimates = Field(default_factory=Estimates)
    excluded: int = 0

    def add(self, gold: Extraction, pred: Extraction | None, case: ScaleCase) -> str:
        """Score one scale case; returns "<gold status>-><predicted column>"."""
        column = "missing" if pred is None else pred.scale.status
        self.confusion[gold.scale.status][column] += 1
        stats = self.by_case.setdefault(case, CaseStats())
        expected = {
            "scaled": ("scaled",),
            "no_scale": ("estimated", "no_scale"),
            "not_to_scale": ("not_to_scale",),
        }[gold.scale.status]
        stats.status.add(column in expected)
        if gold.scale.status == "scaled" and gold.scale.m_per_unit is not None:
            error = relative_error(pred, gold, gold.scale.m_per_unit) if pred else None
            passed = column == "scaled" and error is not None and error <= SCALE_TOLERANCE + _SLACK
            stats.m_per_unit.add(passed)
            for kind in gold.scale.evidence:
                self.by_evidence.setdefault(kind, Rate()).add(passed)
        reference = gold.scale.reference_m_per_unit
        if column == "estimated" and pred is not None and reference is not None:
            error = relative_error(pred, gold, reference)
            if error is not None:
                self.estimates.errors.append(error)
        return f"{gold.scale.status}->{column}"

    def merge(self, other: "ScaleScore") -> None:
        for gold, row in other.confusion.items():
            for column, n in row.items():
                self.confusion[gold][column] += n
        for case, stats in other.by_case.items():
            mine = self.by_case.setdefault(case, CaseStats())
            for name in ("status", "m_per_unit"):
                rate, theirs = getattr(mine, name), getattr(stats, name)
                rate.n, rate.correct = rate.n + theirs.n, rate.correct + theirs.correct
        for kind, theirs in other.by_evidence.items():
            rate = self.by_evidence.setdefault(kind, Rate())
            rate.n, rate.correct = rate.n + theirs.n, rate.correct + theirs.correct
        self.estimates.errors += other.estimates.errors
        self.excluded += other.excluded


def _pct(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.1%}"


def format_scale_table(name: str, score: ScaleScore) -> str:
    lines = [f"scale, {name}: gold status x predicted status ({score.excluded} files not cases)"]
    lines.append(f"{'gold \\ pred':<14}" + "".join(f"{column:>14}" for column in PRED_COLUMNS))
    for gold, row in score.confusion.items():
        lines.append(f"{gold:<14}" + "".join(f"{row[column]:>14}" for column in PRED_COLUMNS))
    lines.append(f"{'case':<20} {'files':>6} {'status ok':>10} {'m 2% pass':>10}")
    for case in SCALE_CASES:
        if case in score.by_case:
            stats = score.by_case[case]
            lines.append(
                f"{case:<20} {stats.status.n:>6} {_pct(stats.status.rate):>10} "
                f"{_pct(stats.m_per_unit.rate):>10}"
            )
    if score.by_evidence:
        lines.append(
            "m_per_unit pass per evidence kind: "
            + ", ".join(
                f"{k} {_pct(r.rate)} of {r.n}" for k, r in sorted(score.by_evidence.items())
            )
        )
    estimates = score.estimates
    if estimates.errors:
        lines.append(
            f"estimates vs reference: {len(estimates.errors)} files, median error "
            f"{_pct(estimates.median_error)}, within 10% {_pct(estimates.within_10)}, within 20% "
            f"{_pct(estimates.within_20)}"
        )
    return "\n".join(lines)

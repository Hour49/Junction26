"""The hard slice (r8 section BA): sheets our CubiCasa-trained readers were not made for (huge,
multi-plan, colour or concept plans, photos, hand-drawn) and drawings that look like plans but are
not (MEP, structural, site, elevations), labelled by eye as `hard_set_v1`. Scored apart from the
headline, like the conflict slice, so the Carbon-first arms (sheet kind, Carbon reader, big-sheet
tiles, printed scale) are measured the same way as everything else.

- Classifier: `sheet_kind` accuracy; `floor_plan_on_sheet` recall and precision; agreement on
  `takeoff_possible` and `advanced`.
- Reader: per family, the answers inside the labelled [lo, hi]. A refusal counts against the hit
  rate and is counted apart; a family labelled `cannot_tell`, a family left out of the labels and a
  family the arm does not answer at all are not scored. A count given on a sheet with no floor plan
  is listed, not scored.
- Scale: the printed ratio (1:N) read exactly; the page scale's relative error where the labels give
  a `scale_check` (two pixel points and the metres between them; a printed ratio alone can't score
  a pixel scale, the print's DPI is unknown).

An arm is one `hard_pred_v1` line per file (`HardPred`; a field left null: the arm does not say).
`preds_from_run` builds them from a pipeline run of `questions_for`'s questions (`app.cli answer`):
counts from its answers, the floor-plan verdict from its ingest report (set aside or read), the page
scale from its extraction files. A classifier that has no run (the sheet kind step) writes the lines
itself; `merge_preds` lays them over a run's.
"""

import math
import re
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path, PurePosixPath
from statistics import median
from typing import Literal, cast

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator, model_validator

SheetKind = Literal[
    "architectural_floor_plan",
    "multi_view_sheet",
    "mep_plan",
    "structural_plan",
    "roof_or_ceiling_plan",
    "site_plan_or_map",
    "elevation",
    "section",
    "detail",
    "perspective_or_axonometric",
    "schedule_or_text",
    "not_a_drawing",
    "other",
]  # the sheet-kind contract's words (.agents/exp/vlm-kind.md 1.1), so a reply scores unmapped
# eval's count families, in the order the questions are asked
FAMILIES = (
    "plan", "door", "window", "toilet", "sink", "shower+bathtub", "sauna",
    "room:bedroom", "room:bathroom", "room:kitchen", "room:wc", "room:balcony",
)  # fmt: skip
# One question per family, our own words (the dataset's are partner data); the backend's template
# parser reads each as its family (tests/test_hard_scoring.py checks it where backend/ has a venv).
QUESTIONS = {
    "plan": "How many floor plans are shown on this sheet?",
    "door": "How many doors are shown on this floor plan?",
    "window": "How many windows are shown on this floor plan?",
    "toilet": "How many toilets are shown on this floor plan?",
    "sink": "How many sinks are shown on this floor plan?",
    "shower+bathtub": "How many showers and bathtubs are shown on this floor plan?",
    "sauna": "How many saunas are shown on this floor plan?",
    "room:bedroom": "How many bedrooms are there in this floor plan?",
    "room:bathroom": "How many bathrooms are there in this floor plan?",
    "room:kitchen": "How many kitchens are there in this floor plan?",
    "room:wc": "How many separate WC rooms are there in this floor plan?",
    "room:balcony": "How many balconies are there in this floor plan?",
}
LICENCES = {
    "PD-USGov", "PDM", "CC0", "OGL-UK-3.0",
    "CC-BY-2.0", "CC-BY-3.0", "CC-BY-4.0", "CC-BY-SA-2.0", "CC-BY-SA-3.0", "CC-BY-SA-4.0",
}  # fmt: skip
IMAGES = {".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff", ".gif", ".bmp"}
_EXTRA_FAMILY = re.compile(r"room:[a-z][a-z0-9_ -]*")


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class CountRange(_Strict):
    lo: int = Field(ge=0)
    hi: int = Field(ge=0)

    @model_validator(mode="after")
    def _ordered(self) -> "CountRange":
        if self.lo > self.hi:
            raise ValueError(f"lo {self.lo} > hi {self.hi}")
        return self


Count = CountRange | Literal["cannot_tell"]


class PrintedScale(_Strict):
    text: str = Field(min_length=1)
    ratio: float | None = Field(default=None, gt=0, description="the 1:N it means; null: NTS")
    how: Literal["text", "bar", "both"]


class ScaleCheck(_Strict):
    p1: tuple[float, float]
    p2: tuple[float, float]
    metres: float = Field(gt=0)
    from_: str = Field(alias="from", min_length=1)

    @computed_field
    @property
    def m_per_px(self) -> float:
        return self.metres / math.dist(self.p1, self.p2)

    @model_validator(mode="after")
    def _apart(self) -> "ScaleCheck":
        if math.dist(self.p1, self.p2) <= 0:
            raise ValueError("p1 and p2 are the same point")
        return self


class HardFile(_Strict):
    file: str = Field(min_length=1)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    page: int = Field(default=1, ge=1)
    source_url: str = Field(min_length=1)
    licence: str
    attribution: str
    gold_commit_ok: bool
    sheet_kind: SheetKind
    floor_plan_on_sheet: bool
    takeoff_possible: bool
    advanced: bool
    why: str = Field(min_length=1)
    printed_scale: PrintedScale | None
    scale_check: ScaleCheck | None = None
    counts: dict[str, Count] | None = None
    printed_facts: list[str] = Field(default_factory=list[str])
    checked_by: str = Field(min_length=1)
    minutes: float = Field(ge=0)
    # think-local's additions (hard set, 2026-11-14): how the file was got, its pixel size, a note
    fetched: str | None = None
    px: tuple[int, int] | None = None
    note: str | None = None

    @field_validator("licence")
    @classmethod
    def _licence(cls, value: str) -> str:
        if value in LICENCES or (value.startswith("other:") and len(value) > 6):
            if "NC" in value.split(":")[0] or "ND" in value.split(":")[0]:
                raise ValueError(f"{value}: no NC/ND files in the set")
            return value
        raise ValueError(f"licence {value!r}: one of {sorted(LICENCES)} or other:<words>")

    @field_validator("counts")
    @classmethod
    def _families(cls, value: dict[str, Count] | None) -> dict[str, Count] | None:
        for key in value or {}:
            if key not in FAMILIES and key != "rooms_total" and not _EXTRA_FAMILY.fullmatch(key):
                raise ValueError(f"count {key!r}: one of {FAMILIES}, room:<word> or rooms_total")
        return value

    @model_validator(mode="after")
    def _consistent(self) -> "HardFile":
        if self.counts is not None and not self.floor_plan_on_sheet:
            raise ValueError(f"{self.file}: counts given but no floor plan on the sheet")
        if self.advanced and not self.floor_plan_on_sheet:
            raise ValueError(f"{self.file}: advanced is false when there is no floor plan")
        if self.gold_commit_ok and self.licence.startswith("other:"):
            raise ValueError(f"{self.file}: gold_commit_ok needs a listed licence")
        if self.scale_check is not None and PurePosixPath(self.file).suffix.lower() not in IMAGES:
            raise ValueError(f"{self.file}: scale_check is in image pixels, images only")
        return self


class HardLabels(_Strict):
    schema_: Literal["hard_set_v1"] = Field(alias="schema")
    files: list[HardFile]


def load_labels(paths: Sequence[Path]) -> list[HardFile]:
    """Every labelled file of `paths`; a file name labelled twice is refused."""
    files: list[HardFile] = []
    seen: dict[str, Path] = {}
    for path in paths:
        for item in HardLabels.model_validate_json(path.read_text(encoding="utf-8")).files:
            if item.file in seen:
                raise ValueError(f"{item.file} is labelled in {seen[item.file]} and {path}")
            seen[item.file] = path
            files.append(item)
    return files


def public_gold(files: Iterable[HardFile]) -> list[dict[str, object]]:
    """The labels whose licence lets the gold be committed (images never are), as they were
    written: a hard_set_v1 file's `files`."""
    kept = [item.model_dump(mode="json", by_alias=True) for item in files if item.gold_commit_ok]
    for item in kept:
        check = item.get("scale_check")
        if isinstance(check, dict):
            cast(dict[str, object], check).pop("m_per_px", None)
    return kept


_FRACTION = r"(\d+(?:\.\d+)?(?:\s*/\s*\d+)?|\d+\s+\d+\s*/\s*\d+)"


def _number(text: str) -> float:
    parts = text.split()
    if len(parts) == 2:  # "1 1/2"
        return float(parts[0]) + _number(parts[1])
    if "/" in text:
        top, bottom = text.split("/")
        return float(top) / float(bottom)
    return float(text)


def ratio_of(text: str) -> float | None:
    """The 1:N a printed scale means: "1:200" -> 200, '1/4" = 1\'-0"' -> 48, '1" = 40\'' -> 480;
    None for "NTS", "not to scale" or a form it does not know."""
    words = text.strip().lower().replace("\u2019", "'").replace("\u201d", '"')
    words = words.replace("\u2033", '"')  # typographic apostrophe, quote, double prime
    if "nts" in words.split() or "not to scale" in words:
        return None
    ratio = re.search(r"(\d+(?:[.,]\d+)?)\s*:\s*(\d+(?:[.,]\d+)?)", words)
    if ratio:
        left, right = (float(v.replace(",", ".")) for v in ratio.groups())
        return right / left if left > 0 else None
    imperial = re.search(
        _FRACTION + r'\s*(?:"|in(?:ch(?:es)?)?)\s*=\s*(\d+(?:\.\d+)?)\s*(?:\'|ft|feet|foot)'
        r'(?:\s*-?\s*(\d+(?:\.\d+)?)\s*(?:"|in(?:ch(?:es)?)?))?',
        words,
    )
    if imperial:
        inches = _number(imperial.group(1))
        real = float(imperial.group(2)) * 12 + float(imperial.group(3) or 0)
        return real / inches if inches > 0 else None
    return None


def questions_for(files: Sequence[HardFile], folder: str) -> list[dict[str, object]]:
    """One question per (file, family) for `app.cli answer`; `folder` is where the files are,
    relative to the --dataset root. Every file is asked, plan or not: on a sheet with no floor
    plan the honest answer is a refusal."""
    rows: list[dict[str, object]] = []
    for item in files:
        for family in FAMILIES:
            path = str(PurePosixPath(folder) / item.file)
            rows.append({"id": len(rows) + 1, "path": path, "question": QUESTIONS[family]})
    return rows


class HardPred(_Strict):
    file: str = Field(min_length=1, description="the labelled file name")
    sheet_kind: SheetKind | None = None
    floor_plan_on_sheet: bool | None = None
    takeoff_possible: bool | None = None
    advanced: bool | None = None
    printed_scale_ratio: float | None = Field(default=None, gt=0)
    m_per_px: float | None = Field(default=None, gt=0)
    # family -> the answered count; None: refused; a family not here was not asked
    counts: dict[str, int | None] = Field(default_factory=dict[str, int | None])


def load_preds(path: Path) -> list[HardPred]:
    lines = path.read_text(encoding="utf-8").splitlines()
    return [HardPred.model_validate_json(line) for line in lines if line.strip()]


def merge_preds(base: Sequence[HardPred], over: Sequence[HardPred]) -> list[HardPred]:
    """`over`'s fields laid on `base`'s, file by file (a null in `over` keeps `base`'s value)."""
    merged = {pred.file: pred for pred in base}
    for pred in over:
        old = merged.get(pred.file, HardPred(file=pred.file))
        fields = {
            k: v for k, v in pred.model_dump(exclude={"file", "counts"}).items() if v is not None
        }
        merged[pred.file] = old.model_copy(
            update={**fields, "counts": {**old.counts, **pred.counts}}
        )
    return list(merged.values())


_FAMILY_OF = {text: family for family, text in QUESTIONS.items()}


def preds_from_run(
    questions: Iterable[Mapping[str, object]],
    answers: Iterable[Mapping[str, object]],
    ingest: Mapping[str, Sequence[Mapping[str, object]]] | None = None,
    scales: Mapping[str, float] | None = None,
) -> list[HardPred]:
    """A pipeline run of `questions_for`'s questions as predictions: each answered count (an answer
    that is not a whole number, or null, is a refusal), the file read as a floor plan unless the
    ingest report set it aside, and the extraction's metres per pixel (`scales`, by file name)."""
    asked = {int(str(q["id"])): (PurePosixPath(str(q["path"])).name, _FAMILY_OF[str(q["question"])])
             for q in questions}  # fmt: skip
    counts: dict[str, dict[str, int | None]] = {name: {} for name, _ in asked.values()}
    for row in answers:
        found = asked.get(int(str(row["id"])))
        if found is None:
            continue
        value = row.get("answer")
        whole = isinstance(value, int) and not isinstance(value, bool) and value >= 0
        counts[found[0]][found[1]] = value if whole and isinstance(value, int) else None
    set_aside: set[str] = set()
    read: set[str] = set()
    if ingest is not None:
        for entry in ingest.get("set_aside", ()):
            set_aside.add(PurePosixPath(str(entry["path"])).name)
        for sheet in ingest.get("sheets", ()):
            read.add(PurePosixPath(str(sheet["file"])).name)
    preds: list[HardPred] = []
    for name, by in counts.items():
        plan = False if name in set_aside else True if name in read else None
        scale = None if scales is None else scales.get(name)
        preds.append(HardPred(file=name, floor_plan_on_sheet=plan, m_per_px=scale, counts=by))
    return preds


class Agreement(BaseModel):
    labelled: int = 0
    said: int = 0
    right: int = 0

    @computed_field
    @property
    def rate(self) -> float | None:
        return self.right / self.said if self.said else None


class PlanVerdicts(BaseModel):
    tp: int = 0
    fp: int = 0
    fn: int = 0
    tn: int = 0
    not_said: int = 0

    @computed_field
    @property
    def recall(self) -> float | None:
        return self.tp / (self.tp + self.fn) if self.tp + self.fn else None

    @computed_field
    @property
    def precision(self) -> float | None:
        return self.tp / (self.tp + self.fp) if self.tp + self.fp else None


class FamilyHits(BaseModel):
    labelled: int = 0
    asked: int = 0
    hit: int = 0
    refused: int = 0
    cannot_tell: int = 0

    @computed_field
    @property
    def hit_rate(self) -> float | None:
        return self.hit / self.asked if self.asked else None


class ScaleErrors(BaseModel):
    ratio_labelled: int = 0
    ratio_read: int = 0
    ratio_exact: int = 0
    px_labelled: int = 0
    px_errors: list[float] = Field(default_factory=list[float])

    @computed_field
    @property
    def px_median(self) -> float | None:
        return median(self.px_errors) if self.px_errors else None

    @computed_field
    @property
    def px_within_10(self) -> int:
        return sum(e <= 0.10 for e in self.px_errors)

    @computed_field
    @property
    def px_within_20(self) -> int:
        return sum(e <= 0.20 for e in self.px_errors)


class HardReport(BaseModel):
    files: int
    predicted: int
    kind: Agreement
    plan: PlanVerdicts
    takeoff: Agreement
    advanced: Agreement
    families: dict[str, FamilyHits]
    pooled: FamilyHits
    non_plan_counts: list[tuple[str, str, int]] = Field(
        description="(file, family, count) answered on a sheet with no floor plan"
    )
    scale: ScaleErrors
    missed: list[tuple[str, str, str]] = Field(
        description="(file, family, why) per labelled range not hit: the answer, or refused"
    )


def _agree(agreement: Agreement, truth: object, said: object) -> None:
    agreement.labelled += 1
    if said is not None:
        agreement.said += 1
        agreement.right += said == truth


def score(files: Sequence[HardFile], preds: Sequence[HardPred]) -> HardReport:
    by_file = {pred.file: pred for pred in preds}
    kind, takeoff, advanced, plan = Agreement(), Agreement(), Agreement(), PlanVerdicts()
    families: dict[str, FamilyHits] = {}
    non_plan: list[tuple[str, str, int]] = []
    missed: list[tuple[str, str, str]] = []
    scale = ScaleErrors()
    for item in files:
        pred = by_file.get(item.file, HardPred(file=item.file))
        _agree(kind, item.sheet_kind, pred.sheet_kind)
        _agree(takeoff, item.takeoff_possible, pred.takeoff_possible)
        _agree(advanced, item.advanced, pred.advanced)
        if pred.floor_plan_on_sheet is None:
            plan.not_said += 1
        elif item.floor_plan_on_sheet:
            plan.tp += pred.floor_plan_on_sheet
            plan.fn += not pred.floor_plan_on_sheet
        else:
            plan.fp += pred.floor_plan_on_sheet
            plan.tn += not pred.floor_plan_on_sheet
        if not item.floor_plan_on_sheet:
            non_plan += [(item.file, f, c) for f, c in pred.counts.items() if c is not None]
        for family, truth in (item.counts or {}).items():
            hits = families.setdefault(family, FamilyHits())
            hits.labelled += 1
            if truth == "cannot_tell":
                hits.cannot_tell += 1
                continue
            if family not in pred.counts:
                continue
            hits.asked += 1
            said = pred.counts[family]
            if said is None:
                hits.refused += 1
                missed.append((item.file, family, "refused"))
            elif truth.lo <= said <= truth.hi:
                hits.hit += 1
            else:
                missed.append((item.file, family, f"{said} (truth {truth.lo}-{truth.hi})"))
        if item.printed_scale is not None and item.printed_scale.ratio is not None:
            scale.ratio_labelled += 1
            if pred.printed_scale_ratio is not None:
                scale.ratio_read += 1
                truth_ratio = item.printed_scale.ratio
                scale.ratio_exact += (
                    abs(pred.printed_scale_ratio - truth_ratio) <= 1e-6 * truth_ratio
                )
        if item.scale_check is not None:
            scale.px_labelled += 1
            if pred.m_per_px is not None:
                truth_scale = item.scale_check.m_per_px
                scale.px_errors.append(abs(pred.m_per_px - truth_scale) / truth_scale)
    pooled = FamilyHits()
    for name in ("labelled", "asked", "hit", "refused", "cannot_tell"):
        setattr(pooled, name, sum(getattr(h, name) for h in families.values()))
    order = {family: n for n, family in enumerate(FAMILIES)}
    return HardReport(
        files=len(files),
        predicted=sum(item.file in by_file for item in files),
        kind=kind,
        plan=plan,
        takeoff=takeoff,
        advanced=advanced,
        families=dict(sorted(families.items(), key=lambda kv: (order.get(kv[0], 99), kv[0]))),
        pooled=pooled,
        non_plan_counts=non_plan,
        scale=scale,
        missed=missed,
    )


def _share(part: int, whole: int) -> str:
    return f"{part}/{whole} {100 * part / whole:.1f}%" if whole else f"{part}/{whole} n/a"


def format_report(report: HardReport, details: bool = True) -> str:
    """The slice as text; `details` adds the file names (local use, never a record)."""
    p = report.plan
    lines = [
        f"hard slice (not in the headline): {report.files} files, {report.predicted} predicted",
        f"  sheet kind       {_share(report.kind.right, report.kind.said)} right "
        f"({report.kind.labelled - report.kind.said} not said)",
        f"  floor plan       recall {_share(p.tp, p.tp + p.fn)}, "
        f"precision {_share(p.tp, p.tp + p.fp)} "
        f"({p.not_said} not said; non-plans read as plans {p.fp}, set aside {p.tn})",
        f"  takeoff possible {_share(report.takeoff.right, report.takeoff.said)} agree",
        f"  advanced         {_share(report.advanced.right, report.advanced.said)} agree",
        "  counts in range (refusals count as misses; cannot_tell and families not asked left out)",
        f"    {'family':<16} {'labelled':>8} {'hit/asked':>16} {'refused':>8} {'cannot tell':>12}",
    ]
    for family, hits in [*report.families.items(), ("pooled", report.pooled)]:
        lines.append(
            f"    {family:<16} {hits.labelled:>8} {_share(hits.hit, hits.asked):>16} "
            f"{hits.refused:>8} {hits.cannot_tell:>12}"
        )
    lines.append(f"  counts answered on sheets with no floor plan: {len(report.non_plan_counts)}")
    s = report.scale
    median_text = "n/a" if s.px_median is None else f"{100 * s.px_median:.1f}%"
    lines += [
        f"  printed scale    read {s.ratio_read}/{s.ratio_labelled}, exact {s.ratio_exact}",
        f"  page scale       {len(s.px_errors)}/{s.px_labelled} with a value, median error "
        f"{median_text}, within 10% {s.px_within_10}, within 20% {s.px_within_20}",
    ]
    if details:
        lines += [f"    missed {f} {fam}: {why}" for f, fam, why in report.missed]
        lines += [f"    non-plan {f} {fam}: {c}" for f, fam, c in report.non_plan_counts]
    return "\n".join(lines)


def aggregates(report: HardReport) -> dict[str, object]:
    """The report without file names, for a public record."""
    body = report.model_dump(mode="json", exclude={"missed", "non_plan_counts"})
    body["scale"].pop("px_errors", None)
    body["non_plan_counts"] = len(report.non_plan_counts)
    return body

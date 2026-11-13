"""Part 1 of the golden set: score the pipeline's extraction_v1 files against the extraction gold.

Files pair by `file`. A gold file is scored only on what its `truth` covers:
- `elements`: per class, one-to-one matching on the same page by IoU >= 0.5 (greedy, highest IoU
  first) -> precision, recall, F1. IoU is of the polygons when gold and prediction both have one
  (the boxes of diagonal walls on a rotated plan are large and overlap), else of the boxes. Also a
  centre-hit rate per class: predictions whose box centre lies in a gold polygon (or box, without
  one), and gold items holding at least one such centre. Rooms match like elements (any type), then
  type accuracy and `area_m2` within 2% where the gold area is exact (`area_status` exact or unset).
  An estimated gold area (CubiCasa: polygon x an approximate scale) is scored like a scale estimate:
  the relative error of the predicted area, as a median and the shares within 10% and 20%, per
  source. Plans: count exact. Counts per key per file: exact-match
  rate (an element with `attrs.multiplicity` counts that many times only with `multiplicity`).
- `counts`: only the counts in the gold's `counts` object.
- `tables`: only the schedules (table_scoring.py); a gold file with `tables` and truth `elements`
  is scored on both.
Scale is scored per case of evidence (scale_scoring.py): a status confusion table, the m_per_unit
pass rate per case and per evidence kind, and estimates against a reference. Gold files that list
`conflicts` form the conflict slice (conflict_scoring.py). Tables and conflicts are reported in
their own sections and never change the headline numbers. A file in `slice_only` (it joined golden
v2 only for the conflict slice) is scored in that slice and nowhere else (orchestrator,
2026-11-13 23:29: the headline stays comparable with the runs recorded before the slice).

A missing prediction file means every gold item on it is missed and every count is wrong. A class
(or rooms at all) that no gold file of a source lists is not scored for that source: the swiss gold
has no stairs, the CubiCasa gold no walls. Predictions of such classes are counted as not scored.
"""

from collections.abc import Iterable, Mapping, Sequence, Set

from pydantic import BaseModel, ConfigDict, Field, computed_field
from shapely.geometry import Point
from shapely.geometry import Polygon as Shape

from .conflict_scoring import ConflictScore, format_conflict_section
from .extraction import Element, Extraction, Room
from .families import source_of
from .geometry import Box, iou
from .scale_scoring import Estimates, Rate, ScaleScore, case_of, format_scale_table
from .table_scoring import TableScore, format_table_section

IOU_MIN = 0.5
AREA_TOLERANCE = 0.02
_SLACK = 1e-9  # a value exactly at a threshold passes despite float rounding


def _shape(item: Element | Room) -> Shape | None:
    """The item's polygon as a valid shapely shape, or None without one or when it has no area."""
    if item.polygon is None:
        return None
    shape = Shape(item.polygon)
    shape = shape if shape.is_valid else shape.buffer(0)
    return shape if shape.area > 0 else None


def _touch(a: Box, b: Box) -> bool:
    return a[0] <= b[2] and b[0] <= a[2] and a[1] <= b[3] and b[1] <= a[3]


def overlap(gold: Element | Room, pred: Element | Room) -> float:
    """IoU of the polygons when both have one with an area, else of the boxes."""
    if gold.page != pred.page or not _touch(gold.box, pred.box):
        return 0.0
    gold_shape, pred_shape = _shape(gold), _shape(pred)
    if gold_shape is not None and pred_shape is not None:
        union = gold_shape.union(pred_shape).area
        return float(gold_shape.intersection(pred_shape).area / union) if union > 0 else 0.0
    return iou(gold.box, pred.box)


def match(gold: Sequence[Element | Room], pred: Sequence[Element | Room]) -> list[tuple[int, int]]:
    """One-to-one (gold index, pred index) pairs on the same page with IoU >= IOU_MIN, taken
    greedily from the highest IoU; ties go to the lower indexes."""
    candidates = sorted(
        (-value, g, p)
        for g, gold_item in enumerate(gold)
        for p, pred_item in enumerate(pred)
        if (value := overlap(gold_item, pred_item)) >= IOU_MIN * (1 - _SLACK)
    )
    used_gold: set[int] = set()
    used_pred: set[int] = set()
    pairs: list[tuple[int, int]] = []
    for _, g, p in candidates:
        if g not in used_gold and p not in used_pred:
            used_gold.add(g)
            used_pred.add(p)
            pairs.append((g, p))
    return pairs


def within(got: float | None, want: float, tolerance: float) -> bool:
    return got is not None and abs(got - want) <= tolerance * abs(want) * (1 + _SLACK)


def centre_hits(gold: Sequence[Element | Room], pred: Sequence[Element | Room]) -> tuple[int, int]:
    """(gold items holding at least one prediction's box centre, predictions whose box centre lies
    in some gold item), same page; a gold item is its polygon, or its box without one."""
    regions = [(item.page, _shape(item), item.box) for item in gold]
    hit_gold: set[int] = set()
    hit_pred = 0
    for item in pred:
        x, y = (item.box[0] + item.box[2]) / 2, (item.box[1] + item.box[3]) / 2
        inside = {
            g
            for g, (page, shape, box) in enumerate(regions)
            if page == item.page
            and box[0] <= x <= box[2]
            and box[1] <= y <= box[3]
            and (shape is None or shape.covers(Point(x, y)))
        }
        hit_gold |= inside
        hit_pred += bool(inside)
    return len(hit_gold), hit_pred


def counts_of(extraction: Extraction, multiplicity: bool = False) -> dict[str, int]:
    """The file's counts: its `counts` object for truth counts, else derived from its lists."""
    if extraction.truth == "counts":
        return dict(extraction.counts or {})
    return extraction.derived_counts(multiplicity=multiplicity)


class Prf(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tp: int = 0
    fp: int = 0
    fn: int = 0

    @computed_field
    @property
    def precision(self) -> float | None:
        return self.tp / (self.tp + self.fp) if self.tp + self.fp else None

    @computed_field
    @property
    def recall(self) -> float | None:
        return self.tp / (self.tp + self.fn) if self.tp + self.fn else None

    @computed_field
    @property
    def f1(self) -> float | None:
        denominator = 2 * self.tp + self.fp + self.fn
        return 2 * self.tp / denominator if denominator else None

    def add(self, other: "Prf") -> None:
        self.tp, self.fp, self.fn = self.tp + other.tp, self.fp + other.fp, self.fn + other.fn


class CentreStats(BaseModel):
    model_config = ConfigDict(extra="forbid")

    gold: int = 0
    pred: int = 0
    gold_hit: int = 0
    pred_hit: int = 0

    @computed_field
    @property
    def pred_rate(self) -> float | None:
        """Share of predictions whose box centre lies in a gold item."""
        return self.pred_hit / self.pred if self.pred else None

    @computed_field
    @property
    def gold_rate(self) -> float | None:
        """Share of gold items that hold at least one prediction's box centre."""
        return self.gold_hit / self.gold if self.gold else None


class RoomStats(BaseModel):
    model_config = ConfigDict(extra="forbid")

    boxes: Prf = Prf()
    type: Rate = Rate()
    area: Rate = Field(default_factory=Rate, description="exact gold areas within 2%")
    area_estimated: Estimates = Field(
        default_factory=Estimates, description="estimated gold areas: relative errors"
    )
    area_estimated_missing: int = Field(
        default=0, description="matched rooms with an estimated gold area and no predicted area"
    )


class FileResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    file: str
    source: str
    split: str
    truth: str
    predicted: bool
    scale: str | None = Field(description="<gold status>-><predicted>, or null if not a scale case")
    counts_wrong: dict[str, tuple[int, int | None]]  # key -> (gold, predicted)


class ExtractionScore(BaseModel):
    """The full Part 1 score (gitignored runs folder): per source x class, and overall."""

    model_config = ConfigDict(extra="forbid")

    files: int
    predicted: int
    multiplicity: bool = Field(description="counts used attrs.multiplicity")
    elements: dict[str, Prf]  # "<source> <class>"
    centre: dict[str, CentreStats]  # "<source> <class>"
    not_scored: dict[str, int]  # "<source> <class or rooms>": predictions the gold never covers
    elements_by_source: dict[str, Prf]
    elements_overall: Prf
    rooms: dict[str, RoomStats]  # by source
    plans: dict[str, Rate]  # by source, count exact
    counts: dict[str, Rate]  # "<source> <key>"
    counts_by_source: dict[str, Rate]
    counts_overall: Rate
    scale: dict[str, ScaleScore]  # by source
    scale_overall: ScaleScore
    per_file: list[FileResult]
    slice_only_files: int = Field(default=0, description="scored only in the conflict slice")
    tables: TableScore | None = Field(default=None, description="when a gold file has tables")
    conflicts: ConflictScore | None = Field(
        default=None, description="when a gold file lists conflicts (the conflict slice)"
    )


def _covered(golds: Iterable[Extraction]) -> dict[str, set[str]]:
    """Per source, the count keys its truth-elements gold files cover (plans always)."""
    covered: dict[str, set[str]] = {}
    for gold in golds:
        if gold.truth == "elements":
            keys = covered.setdefault(source_of(gold.file), {"plan"})
            keys.update(gold.derived_counts())
    return covered


def score_extraction(
    golds: Sequence[Extraction],
    preds: Mapping[str, Extraction],
    multiplicity: bool = False,
    slice_only: Set[str] = frozenset(),
) -> ExtractionScore:
    covered = _covered(gold for gold in golds if gold.file not in slice_only)
    elements: dict[str, Prf] = {}
    centre: dict[str, CentreStats] = {}
    not_scored: dict[str, int] = {}
    rooms: dict[str, RoomStats] = {}
    plans: dict[str, Rate] = {}
    counts: dict[str, Rate] = {}
    scale: dict[str, ScaleScore] = {}
    per_file: list[FileResult] = []
    tables, conflicts = TableScore(), ConflictScore()
    for gold in sorted(golds, key=lambda extraction: extraction.file):
        source = source_of(gold.file)
        pred = preds.get(gold.file)
        if gold.conflicts:
            rooms_of = match(gold.rooms, pred.rooms) if pred else []
            room_map = {pred.rooms[p].id: gold.rooms[g].id for g, p in rooms_of} if pred else {}
            conflicts.add(gold, pred, room_map)
        elif pred is not None:
            conflicts.not_scored += sum(item.status == "conflict" for item in pred.conflicts or [])
        if gold.file in slice_only:
            continue
        if gold.tables:
            tables.add(gold, pred)
        if gold.truth == "elements":
            keys = covered[source]
            for cls in sorted(key for key in keys if key != "plan" and ":" not in key):
                gold_items = [e for e in gold.elements if e.class_ == cls]
                pred_items = [e for e in pred.elements if e.class_ == cls] if pred else []
                pairs = len(match(gold_items, pred_items))
                tally = elements.setdefault(f"{source} {cls}", Prf())
                tally.add(Prf(tp=pairs, fp=len(pred_items) - pairs, fn=len(gold_items) - pairs))
                gold_hit, pred_hit = centre_hits(gold_items, pred_items)
                hits = centre.setdefault(f"{source} {cls}", CentreStats())
                hits.gold, hits.pred = hits.gold + len(gold_items), hits.pred + len(pred_items)
                hits.gold_hit, hits.pred_hit = hits.gold_hit + gold_hit, hits.pred_hit + pred_hit
            for element in pred.elements if pred else []:
                if element.class_ not in keys:
                    key = f"{source} {element.class_}"
                    not_scored[key] = not_scored.get(key, 0) + 1
            pred_rooms = pred.rooms if pred else []
            if not any(key.startswith("room:") for key in keys):
                if pred_rooms:
                    not_scored[f"{source} rooms"] = not_scored.get(f"{source} rooms", 0) + len(
                        pred_rooms
                    )
                pred_rooms = []
            stats = rooms.setdefault(source, RoomStats())
            pairs = match(gold.rooms, pred_rooms)
            stats.boxes.add(
                Prf(tp=len(pairs), fp=len(pred_rooms) - len(pairs), fn=len(gold.rooms) - len(pairs))
            )
            for g, p in pairs:
                stats.type.add(gold.rooms[g].type == pred_rooms[p].type)
                want, got = gold.rooms[g].area_m2, pred_rooms[p].area_m2
                if want is None:
                    continue
                if gold.rooms[g].area_status != "estimated":
                    stats.area.add(within(got, want, AREA_TOLERANCE))
                elif got is None:
                    stats.area_estimated_missing += 1
                elif want > 0:
                    stats.area_estimated.errors.append(abs(got - want) / want)
            plans.setdefault(source, Rate()).add(
                pred is not None and len(pred.plans) == len(gold.plans)
            )
        else:
            keys = set(gold.counts or {})
        want_counts = counts_of(gold, multiplicity)
        got_counts = counts_of(pred, multiplicity) if pred else None
        wrong: dict[str, tuple[int, int | None]] = {}
        for key in sorted(keys):
            want = want_counts.get(key, 0)
            got = None if got_counts is None else got_counts.get(key, 0)
            counts.setdefault(f"{source} {key}", Rate()).add(got == want)
            if got != want:
                wrong[key] = (want, got)
        case = case_of(gold)
        scale_stats = scale.setdefault(source, ScaleScore())
        outcome = None if case is None else scale_stats.add(gold, pred, case)
        scale_stats.excluded += case is None
        per_file.append(
            FileResult(
                file=gold.file,
                source=source,
                split=gold.split,
                truth=gold.truth,
                predicted=pred is not None,
                scale=outcome,
                counts_wrong=wrong,
            )
        )
    return ExtractionScore(
        files=len(per_file),
        predicted=sum(result.predicted for result in per_file),
        multiplicity=multiplicity,
        elements=elements,
        centre=centre,
        not_scored=dict(sorted(not_scored.items())),
        elements_by_source=_rollup(elements, Prf),
        elements_overall=_total(elements.values(), Prf),
        rooms=rooms,
        plans=plans,
        counts=counts,
        counts_by_source=_rollup(counts, Rate),
        counts_overall=_total(counts.values(), Rate),
        scale=scale,
        scale_overall=_merged(scale.values()),
        per_file=per_file,
        slice_only_files=len(golds) - len(per_file),
        tables=tables if tables.files else None,
        conflicts=conflicts if conflicts.files else None,
    )


def _merged(parts: Iterable[ScaleScore]) -> ScaleScore:
    total = ScaleScore()
    for part in parts:
        total.merge(part)
    return total


def _total[T: Prf | Rate](parts: Iterable[T], kind: type[T]) -> T:
    items = list(parts)  # summed once per field, so a generator must not run dry after the first
    fields = list(kind.model_fields)
    return kind(**{field: sum(getattr(item, field) for item in items) for field in fields})


def _rollup[T: Prf | Rate](groups: Mapping[str, T], kind: type[T]) -> dict[str, T]:
    sources = sorted({key.split(" ", 1)[0] for key in groups})
    return {
        source: _total((v for k, v in groups.items() if k.split(" ", 1)[0] == source), kind)
        for source in sources
    }


def _pct(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.1%}"


def format_extraction_table(result: ExtractionScore) -> str:
    lines = [f"{result.predicted} of {result.files} gold files have a prediction"]
    if result.slice_only_files:
        lines[0] += f" ({result.slice_only_files} more are scored only in the conflict slice)"
    lines.append("")
    lines.append(
        f"{'elements':<36} {'tp':>6} {'fp':>6} {'fn':>6} {'prec':>7} {'recall':>7} {'f1':>7} "
        f"{'ctr pred':>8} {'ctr gold':>8}"
    )
    rows = [*result.elements.items(), *result.elements_by_source.items()]
    for key, prf in [*rows, ("overall", result.elements_overall)]:
        hits = result.centre.get(key)
        lines.append(
            f"{key:<36} {prf.tp:>6} {prf.fp:>6} {prf.fn:>6} {_pct(prf.precision):>7} "
            f"{_pct(prf.recall):>7} {_pct(prf.f1):>7} "
            f"{_pct(hits and hits.pred_rate):>8} {_pct(hits and hits.gold_rate):>8}"
        )
    if result.not_scored:
        lines += [
            "",
            "not scored (no gold file of the source lists them): "
            + ", ".join(f"{key} {n}" for key, n in result.not_scored.items()),
        ]
    lines += [
        "",
        f"{'rooms':<20} {'f1':>7} {'type acc':>9} {'area 2%':>8} {'plans exact':>12}   "
        "estimated areas: rooms, no area, median error, within 10%, within 20%",
    ]
    for source in sorted(set(result.rooms) | set(result.plans)):
        stats, plan = result.rooms.get(source, RoomStats()), result.plans.get(source, Rate())
        estimates = stats.area_estimated
        estimated = (
            f"   {len(estimates.errors) + stats.area_estimated_missing}, "
            f"{stats.area_estimated_missing}, {_pct(estimates.median_error)}, "
            f"{_pct(estimates.within_10)}, {_pct(estimates.within_20)}"
            if estimates.errors or stats.area_estimated_missing
            else ""
        )
        lines.append(
            f"{source:<20} {_pct(stats.boxes.f1):>7} {_pct(stats.type.rate):>9} "
            f"{_pct(stats.area.rate):>8} {_pct(plan.rate):>12}{estimated}"
        )
    lines += ["", f"{'counts exact':<36} {'n':>6} {'exact':>7}"]
    for key, rate in [*result.counts.items(), *result.counts_by_source.items()]:
        lines.append(f"{key:<36} {rate.n:>6} {_pct(rate.rate):>7}")
    lines.append(
        f"{'overall':<36} {result.counts_overall.n:>6} {_pct(result.counts_overall.rate):>7}"
    )
    for key, stats in [*result.scale.items(), ("overall", result.scale_overall)]:
        lines += ["", format_scale_table(key, stats)]
    if result.tables is not None:
        lines += ["", format_table_section(result.tables)]
    if result.conflicts is not None:
        lines += ["", format_conflict_section(result.conflicts)]
    return "\n".join(lines)

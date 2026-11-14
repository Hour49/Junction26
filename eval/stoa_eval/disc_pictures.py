"""The discipline-picture bench (spec docs/specs/backend/discipline-pictures.md, P4): a picture
reader's fact sheets scored against the renderer's truth, per discipline and per variant, with the
AC-16 (leave Low) and AC-18 (cost) bars.

- Truth: one `DiscTruth` per rendered picture (`<picture>.truth.json`, anywhere under the bench
  folder): its building, discipline, variant, page size, every legend label's plan points (page
  fractions) and every run's length per system (size None: the system total) and per printed size.
- Prediction: one `DiscPred` line per picture: the reader's `FactSheet` (facts may carry `spots`),
  the double-check's `agreed` map (label -> agree) and the page's cost and seconds.
- Units: a count unit is a (picture, legend label); its prediction is the `.count` fact whose
  subject is the label (the kind's `all` total is not a unit). A run unit is a (picture, system,
  size); its prediction is `<kind>.size_length` (subject the size) or `<kind>.length` (subject
  `all`) of that system. A unit with no fact is a refusal.
- Symbols: per (picture, label), a predicted spot's centre matches a truth point closer than
  `near` of the page diagonal, one to one, greedy by distance.
- The split is by building (`manifest.json`: {"dev": [...], "test": [...]}); test is scored only
  at a milestone.
"""

import math
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from statistics import median
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

NEAR = 0.006  # of the page diagonal (spec, Method 2)
BUDGET_USD = 0.15  # per page (spec, Cost per page)


class _Model(BaseModel):
    model_config = ConfigDict(frozen=True)


class Symbol(_Model):
    label: str
    kind: str
    points: tuple[tuple[float, float], ...]  # plan centres, page fractions


class TruthRun(_Model):
    kind: str
    system: str
    size: str | None  # None: the system's total
    length_m: float = Field(gt=0)


class DiscTruth(_Model):
    picture: str
    building: str
    discipline: str
    storey: str | None = None
    dpi: int
    degradation: str  # clean, scan, photo
    legend: bool = True
    scale: bool = True
    width_px: int = Field(gt=0)
    height_px: int = Field(gt=0)
    symbols: tuple[Symbol, ...] = ()
    runs: tuple[TruthRun, ...] = ()

    @property
    def variant(self) -> str:
        flags = ("" if self.legend else "-no-legend") + ("" if self.scale else "-no-scale")
        return f"{self.dpi}dpi-{self.degradation}{flags}"


class Spot(_Model):
    page: int = 1
    box: tuple[float, float, float, float]
    reader: str = ""


class PredFact(_Model):
    model_config = ConfigDict(frozen=True, extra="ignore")
    topic: str
    subject: str
    value: float | int | str
    system: str | None = None
    spots: tuple[Spot, ...] = ()


class PredSheet(_Model):
    model_config = ConfigDict(frozen=True, extra="ignore")
    model: str
    facts: tuple[PredFact, ...] = ()


class DiscPred(_Model):
    picture: str
    sheet: PredSheet
    agreed: dict[str, bool] = Field(default_factory=dict[str, bool])
    cost_usd: float = Field(default=0.0, ge=0)
    seconds: float = Field(default=0.0, ge=0)


class Metrics(_Model):
    pages: int = 0  # pictures with a prediction
    counts: int = 0
    count_exact: int = 0
    count_within_1: int = 0
    count_refused: int = 0
    agreed: int = 0
    agreed_exact: int = 0
    truth_points: int = 0
    pred_spots: int = 0
    spot_hits: int = 0
    runs: int = 0
    run_within_5: int = 0
    run_within_10: int = 0
    run_refused: int = 0
    costs: tuple[float, ...] = ()
    seconds: tuple[float, ...] = ()

    def __add__(self, other: "Metrics") -> "Metrics":
        a, b = self.model_dump(), other.model_dump()
        return Metrics.model_validate({key: a[key] + b[key] for key in a})

    @property
    def agreed_lower(self) -> float:
        return wilson_lower(self.agreed_exact, self.agreed)

    @property
    def refused_share(self) -> float | None:
        units = self.counts + self.runs
        return (self.count_refused + self.run_refused) / units if units else None

    @property
    def cost_median(self) -> float | None:
        return median(self.costs) if self.costs else None

    @property
    def cost_p95(self) -> float | None:
        return _rank(self.costs, 0.95)

    @property
    def over_budget(self) -> int:
        return sum(cost > BUDGET_USD for cost in self.costs)

    @property
    def seconds_median(self) -> float | None:
        return median(self.seconds) if self.seconds else None


class DiscReport(_Model):
    overall: Metrics
    by_discipline: dict[str, Metrics]
    by_variant: dict[str, Metrics]
    gate: Metrics  # the AC-16 subset: 150 dpi, clean + scan, with legend and scale


def wilson_lower(k: int, n: int, z: float = 1.959964) -> float:
    """The lower end of the Wilson 95% interval of k successes in n (0 when n is 0)."""
    if n == 0:
        return 0.0
    p = k / n
    d = 1 + z * z / n
    mid = (p + z * z / (2 * n)) / d
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return max(0.0, mid - half)


def _rank(values: Sequence[float], q: float) -> float | None:
    """The nearest-rank quantile."""
    if not values:
        return None
    ordered = sorted(values)
    return ordered[max(0, math.ceil(q * len(ordered)) - 1)]


def _share(part: int, whole: int) -> float | None:
    return part / whole if whole else None


RENDER_FIELDS = ("building", "discipline", "dpi", "width_px", "height_px", "symbols", "runs")


def truth_from_render(body: Mapping[str, Any]) -> DiscTruth:
    """A renderer truth file (P3, `plan_picture.py`: one `<picture>.json` beside the picture) as a
    `DiscTruth`: symbols one per instance in pixels -> points per label in page fractions; runs per
    (system, size) plus `system_lengths_m` as the systems' totals."""
    missing = [key for key in RENDER_FIELDS if key not in body]
    missing += sorted({key for s in body.get("symbols", ()) for key in ("label", "kind", "x", "y")
                       if key not in s})  # fmt: skip
    missing += sorted({key for r in body.get("runs", ()) for key in ("kind", "system", "length_m")
                       if key not in r})  # fmt: skip
    if missing:
        raise ValueError(f"truth {body.get('picture')!r} lacks {', '.join(missing)}")
    width, height = body["width_px"], body["height_px"]
    points: dict[str, list[tuple[float, float]]] = defaultdict(list)
    kinds: dict[str, str] = {}
    for symbol in body["symbols"]:
        points[symbol["label"]].append((symbol["x"] / width, symbol["y"] / height))
        kinds[symbol["label"]] = symbol["kind"]
    kind_of_system = {r["system"]: r["kind"] for r in body["runs"]}
    orphans = sorted(set(body.get("system_lengths_m", {})) - set(kind_of_system))
    if orphans:
        raise ValueError(f"truth {body.get('picture')!r}: system(s) {orphans} have no runs")
    runs = [
        {"kind": kind_of_system[system], "system": system, "size": None, "length_m": length}
        for system, length in body.get("system_lengths_m", {}).items()
    ]
    runs += [
        {"kind": r["kind"], "system": r["system"], "size": r.get("size"), "length_m": r["length_m"]}
        for r in body["runs"]
    ]
    return DiscTruth.model_validate(
        {
            "picture": body.get("picture", ""),
            "building": body["building"],
            "discipline": body["discipline"],
            "storey": body.get("storey"),
            "dpi": body["dpi"],
            "degradation": body.get("variant", "clean"),
            "legend": bool(body.get("legend", True)),
            "scale": bool(body.get("scale", True)),
            "width_px": width,
            "height_px": height,
            "symbols": [
                {"label": label, "kind": kinds[label], "points": pts}
                for label, pts in points.items()
            ],
            "runs": runs,
        }
    )


def pick_split(
    truths: Sequence[DiscTruth], manifest: Mapping[str, Sequence[str]], split: str
) -> list[DiscTruth]:
    """The pictures of the split's buildings, in the given order."""
    both = set(manifest.get("dev", ())) & set(manifest.get("test", ()))
    if both:
        raise ValueError(f"{len(both)} building(s) in both dev and test")
    chosen = set(manifest.get(split, ()))
    return [t for t in truths if t.building in chosen]


def _hits(points: Sequence[tuple[float, float]], centres: Sequence[tuple[float, float]],
          width: int, height: int, near: float) -> int:  # fmt: skip
    """One-to-one matches closer than `near` of the diagonal, greedy by distance."""
    limit = near * math.hypot(width, height)
    pairs = sorted(
        (math.hypot((p[0] - c[0]) * width, (p[1] - c[1]) * height), i, j)
        for i, p in enumerate(points)
        for j, c in enumerate(centres)
    )
    used_p: set[int] = set()
    used_c: set[int] = set()
    for dist, i, j in pairs:
        if dist >= limit:
            break
        if i not in used_p and j not in used_c:
            used_p.add(i)
            used_c.add(j)
    return len(used_p)


def _number(value: float | int | str) -> float | None:
    try:
        return float(value)
    except ValueError:
        return None


def score_one(truth: DiscTruth, pred: DiscPred | None, near: float = NEAR) -> Metrics:
    facts = pred.sheet.facts if pred else ()
    counts = {f.subject: f for f in facts if f.topic.endswith(".count") and f.subject != "all"}
    m: dict[str, Any] = {"pages": int(pred is not None)}
    if pred:
        m |= {"costs": (pred.cost_usd,), "seconds": (pred.seconds,)}
    tally: dict[str, int] = defaultdict(int)
    for symbol in truth.symbols:
        tally["counts"] += 1
        tally["truth_points"] += len(symbol.points)
        said = counts.get(symbol.label)
        value = _number(said.value) if said else None
        if said is None or value is None:
            tally["count_refused"] += 1
            continue
        exact = value == len(symbol.points)
        tally["count_exact"] += exact
        tally["count_within_1"] += abs(value - len(symbol.points)) <= 1
        if pred and pred.agreed.get(symbol.label):
            tally["agreed"] += 1
            tally["agreed_exact"] += exact
        centres = [((s.box[0] + s.box[2]) / 2, (s.box[1] + s.box[3]) / 2) for s in said.spots]
        tally["pred_spots"] += len(centres)
        tally["spot_hits"] += _hits(symbol.points, centres, truth.width_px, truth.height_px, near)
    # spots on labels the truth does not have are false positives too
    known = {s.label for s in truth.symbols}
    tally["pred_spots"] += sum(len(f.spots) for label, f in counts.items() if label not in known)
    for run in truth.runs:
        tally["runs"] += 1
        topic, subject = (".length", "all") if run.size is None else (".size_length", run.size)
        said = next(
            (f for f in facts
             if f.topic == run.kind + topic and f.subject == subject and f.system == run.system),
            None,
        )  # fmt: skip
        value = _number(said.value) if said else None
        if value is None:
            tally["run_refused"] += 1
            continue
        error = abs(value - run.length_m) / run.length_m
        tally["run_within_5"] += error <= 0.05 + 1e-9
        tally["run_within_10"] += error <= 0.10 + 1e-9
    return Metrics.model_validate(m | tally)


def score(truths: Sequence[DiscTruth], preds: Iterable[DiscPred], near: float = NEAR) -> DiscReport:
    by_picture = {t.picture: t for t in truths}
    said: dict[str, DiscPred] = {}
    for pred in preds:
        if pred.picture not in by_picture:
            raise ValueError(f"prediction for {pred.picture!r} has no truth in this split")
        said[pred.picture] = pred
    overall = Metrics()
    gate = Metrics()
    by_discipline: dict[str, Metrics] = defaultdict(Metrics)
    by_variant: dict[str, Metrics] = defaultdict(Metrics)
    for truth in truths:
        m = score_one(truth, said.get(truth.picture), near)
        overall += m
        by_discipline[truth.discipline] += m
        by_variant[truth.variant] += m
        if truth.variant in ("150dpi-clean", "150dpi-scan"):
            gate += m
    return DiscReport(
        overall=overall, by_discipline=dict(by_discipline), by_variant=dict(by_variant), gate=gate
    )


def bars(report: DiscReport) -> dict[str, dict[str, Any]]:
    """AC-16 on the gate subset and AC-18 on every page, each bar's value and pass."""
    g, o = report.gate, report.overall
    exact = _share(g.agreed_exact, g.agreed)
    recall = _share(g.spot_hits, g.truth_points)
    length = _share(g.run_within_10, g.runs)
    ac16: dict[str, Any] = {
        "units": g.agreed, "exact": exact, "lower": g.agreed_lower, "recall": recall,
        "runs": g.runs, "length_within_10": length,
        "pass": {
            "units": g.agreed >= 60, "exact": (exact or 0) >= 0.90, "lower": g.agreed_lower >= 0.85,
            "recall": (recall or 0) >= 0.90, "runs": g.runs >= 30, "length": (length or 0) >= 0.80,
        },
    }  # fmt: skip
    median_cost, p95 = o.cost_median, o.cost_p95
    ac18: dict[str, Any] = {
        "median": median_cost, "p95": p95, "over_budget": o.over_budget,
        "pass": {
            "median": median_cost is not None and median_cost <= 0.05,
            "p95": p95 is not None and p95 <= BUDGET_USD,
            "over_budget": o.over_budget == 0,
        },
    }  # fmt: skip
    return {"ac16": ac16, "ac18": ac18}


def _summary(m: Metrics) -> dict[str, Any]:
    return {
        "pages": m.pages,
        "counts": m.counts,
        "count_exact": _share(m.count_exact, m.counts),
        "count_within_1": _share(m.count_within_1, m.counts),
        "agreed_share": _share(m.agreed, m.counts),
        "agreed": m.agreed,
        "exact_when_agreed": _share(m.agreed_exact, m.agreed),
        "exact_when_agreed_lower": m.agreed_lower,
        "symbol_recall": _share(m.spot_hits, m.truth_points),
        "symbol_precision": _share(m.spot_hits, m.pred_spots),
        "runs": m.runs,
        "length_within_5": _share(m.run_within_5, m.runs),
        "length_within_10": _share(m.run_within_10, m.runs),
        "refused": m.refused_share,
        "cost_median": m.cost_median,
        "cost_p95": m.cost_p95,
        "over_budget": m.over_budget,
        "seconds_median": m.seconds_median,
    }


def aggregates(report: DiscReport) -> dict[str, Any]:
    """The report without picture ids, labels or buildings, for a public record."""
    return {
        "overall": _summary(report.overall),
        "by_discipline": {k: _summary(v) for k, v in sorted(report.by_discipline.items())},
        "by_variant": {k: _summary(v) for k, v in sorted(report.by_variant.items())},
        "bars": bars(report),
    }


def _pct(value: float | None) -> str:
    return "-" if value is None else f"{value:.1%}"


def _usd(value: float | None) -> str:
    return "-" if value is None else f"${value:.3f}"


def format_report(report: DiscReport) -> str:
    rows = [("all", report.overall)]
    rows += [(f"disc {k}", v) for k, v in sorted(report.by_discipline.items())]
    rows += [(f"var {k}", v) for k, v in sorted(report.by_variant.items())]
    lines = [
        f"{'':28} {'units':>5} {'count exact':>11} {'±1':>6} {'agreed':>6} {'exact|agr':>9} "
        f"{'recall':>6} {'prec':>6} {'runs':>4} {'len10%':>6} {'refused':>7} {'$ med':>7} "
        f"{'$ p95':>7}"
    ]
    for name, m in rows:
        s = _summary(m)
        lines.append(
            f"{name:28} {m.counts:>5} {_pct(s['count_exact']):>11} {_pct(s['count_within_1']):>6} "
            f"{_pct(s['agreed_share']):>6} {_pct(s['exact_when_agreed']):>9} "
            f"{_pct(s['symbol_recall']):>6} {_pct(s['symbol_precision']):>6} {m.runs:>4} "
            f"{_pct(s['length_within_10']):>6} {_pct(s['refused']):>7} "
            f"{_usd(s['cost_median']):>7} {_usd(s['cost_p95']):>7}"
        )
    for ac, body in bars(report).items():
        failed = [k for k, ok in body["pass"].items() if not ok]
        lines.append(f"{ac.upper()}: " + ("pass" if not failed else "fail: " + ", ".join(failed)))
    return "\n".join(lines)

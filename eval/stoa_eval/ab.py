"""A/B comparison of two experiment arms on one part of the experiment split (`stoa_eval ab`).

Both arms answer the part's dev questions from their extraction_v1 files with the backend's
templates parser and takeoff (`ab_backend.py`), and each answer is judged by Stoa's rule
(`scoring.judge`: counts exact). An image an arm has no file for is refused, so its questions
are wrong. The comparison is paired, with the image as the unit:

- the difference in exact-match rate (B minus A) with a 95% percentile bootstrap interval over
  images, resampled with a fixed seed: a win needs the interval to exclude 0;
- an exact two-sided McNemar p over the questions only one arm gets right. The questions are not
  independent (English and Finnish ask the same count on one image), so this p is overconfident:
  the verdict comes from the bootstrap interval only.

Each arm also gets the exact rate per question family (the parser's), per CubiCasa style (the
file name before the number: colorful, high_quality, high_quality_architectural) and, given an
orientation map, per orientation; and per count key (element class, room:<type>, plan) the share
of images whose count equals the dev gold's and the mean absolute error. A class the file does
not read (`read`) or a missing file counts as wrong, with 0 as its value for the error.
"""

import random
from collections import Counter, defaultdict
from collections.abc import Callable, Iterable, Mapping, Sequence
from math import comb
from pathlib import PurePosixPath
from typing import Literal, cast

from pydantic import BaseModel, ConfigDict, Field

from .extraction import Extraction
from .extraction_scoring import counts_of
from .models import Answer, NumberedQuestion
from .scoring import judge

BOOTSTRAP_REPS = 10_000
AB_SEED = 20261114
REFERENCE_ARMS = ("gold", "prior", "none")
WORST = 10  # images listed per arm, to open first (exp-common, round 1c)
MCNEMAR_NOTE = "questions, not independent"  # EN/FI pairs on one image: not evidence on its own
Verdict = Literal["B better", "A better", "no difference"]


class Rate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    hits: int
    n: int
    rate: float | None


class CountStat(BaseModel):
    model_config = ConfigDict(extra="forbid")

    images: int
    exact: int
    exact_rate: float | None
    mae: float | None = Field(description="mean |predicted - gold| over the images")


class WorstImage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    file: str
    wrong: int = Field(description="questions on the image the arm gets wrong")
    questions: int
    count_error: int | None = Field(description="sum of |predicted - gold| over the count keys")
    families: list[str] = Field(description="families with a wrong answer on the image")


class ArmResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    source: str = Field(description="the arm's folder, or what a reference arm is")
    images: int
    missing_images: int = Field(description="images of the part the arm has no file for")
    overall: Rate
    by_family: dict[str, Rate]
    by_style: dict[str, Rate]
    by_orientation: dict[str, Rate] | None
    counts: dict[str, CountStat] | None = Field(description="null for an arm with no extraction")
    worst: list[WorstImage] = Field(description="the images to look at first: most wrong")


class Paired(BaseModel):
    model_config = ConfigDict(extra="forbid")

    images: int
    questions: int
    diff: float | None = Field(description="exact rate of B minus A")
    ci_low: float | None
    ci_high: float | None
    a_only: int = Field(description="questions only A gets right")
    b_only: int = Field(description="questions only B gets right")
    mcnemar_p: float
    verdict: Verdict


class AbResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    part: str
    split_sha256: str
    prior_sha256: str | None
    seed: int
    bootstrap_reps: int
    orientation: str = Field(description="where upright/rotated came from, or why it is missing")
    a: ArmResult
    b: ArmResult
    paired: Paired
    paired_by_family: dict[str, Paired] = Field(
        description="per family, with its own interval (not corrected for the number of families)"
    )
    per_image: dict[str, tuple[int, int, int]] = Field(description="file -> questions, A, B hits")


def orientation_label(value: object) -> str:
    """An orientation map's value as a label: a string as it is, or {"turn": degrees,
    "mirrored": bool} as "upright", "turn 90", "turn 180 mirrored" and so on."""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        fields = cast(dict[str, object], value)
        turn, mirrored = fields.get("turn"), fields.get("mirrored", False)
        if isinstance(turn, int) and not isinstance(turn, bool) and isinstance(mirrored, bool):
            label = "upright" if turn % 360 == 0 else f"turn {turn % 360}"
            return f"{label} mirrored" if mirrored else label
    raise ValueError(f'orientation: a label or {{"turn": int, "mirrored": bool}}, not {value!r}')


def style_of(file: str) -> str:
    """data/cubicasa5k/high_quality-123.png -> high_quality."""
    return PurePosixPath(file).stem.rsplit("-", 1)[0]


def hits_of(
    questions: Iterable[NumberedQuestion], answers: Mapping[int, Answer]
) -> dict[int, bool]:
    """question id -> exact under Stoa's rule; a missing answer is wrong."""
    return {q.id: judge(q, answers.get(q.id)) == "ok" for q in questions}


def _rate(hits: int, n: int) -> Rate:
    return Rate(hits=hits, n=n, rate=hits / n if n else None)


def rates_by(
    questions: Iterable[NumberedQuestion],
    hits: Mapping[int, bool],
    key: Callable[[NumberedQuestion], str],
) -> dict[str, Rate]:
    tally: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for q in questions:
        tally[key(q)][0] += hits[q.id]
        tally[key(q)][1] += 1
    return {name: _rate(*tally[name]) for name in sorted(tally)}


def count_keys(golds: Iterable[Extraction]) -> list[str]:
    """plan, then element classes, then room:<type>, each as the gold has them."""
    keys: set[str] = set()
    for gold in golds:
        keys |= set(counts_of(gold))
    return sorted(keys, key=lambda key: (key != "plan", key.startswith("room:"), key))


def _known(extraction: Extraction, key: str) -> bool:
    """Whether the file read what `key` counts (`read` null: everything)."""
    if extraction.read is None or key == "plan" or extraction.truth == "counts":
        return True
    return ("room" if key.startswith("room:") else key) in extraction.read


def count_stats(
    golds: Mapping[str, Extraction], preds: Mapping[str, Extraction], keys: Sequence[str]
) -> dict[str, CountStat]:
    """Per key over the gold images: exact share and mean absolute error of the arm's counts."""
    exact: Counter[str] = Counter()
    error: Counter[str] = Counter()
    for file, gold in golds.items():
        want = counts_of(gold)
        pred = preds.get(file)
        got = counts_of(pred) if pred is not None else {}
        for key in keys:
            known = pred is not None and _known(pred, key)
            value = got.get(key, 0) if known else 0
            exact[key] += known and value == want.get(key, 0)
            error[key] += abs(value - want.get(key, 0))
    n = len(golds)
    return {
        key: CountStat(
            images=n,
            exact=exact[key],
            exact_rate=exact[key] / n if n else None,
            mae=error[key] / n if n else None,
        )
        for key in keys
    }


def count_errors(
    golds: Mapping[str, Extraction], preds: Mapping[str, Extraction], keys: Sequence[str]
) -> dict[str, int]:
    """file -> sum over the keys of |predicted - gold| (a missing file or unread class as 0)."""
    errors: dict[str, int] = {}
    for file, gold in golds.items():
        want, pred = counts_of(gold), preds.get(file)
        got = counts_of(pred) if pred is not None else {}
        errors[file] = sum(
            abs(
                (got.get(key, 0) if pred is not None and _known(pred, key) else 0)
                - want.get(key, 0)
            )
            for key in keys
        )
    return errors


def worst_images(
    questions: Iterable[NumberedQuestion],
    hits: Mapping[int, bool],
    families: Mapping[int, str],
    errors: Mapping[str, int] | None,
    top: int = WORST,
) -> list[WorstImage]:
    """The `top` images with the most wrong answers, then the largest count error."""
    asked: Counter[str] = Counter()
    wrong: Counter[str] = Counter()
    missed: dict[str, set[str]] = defaultdict(set)
    for q in questions:
        asked[q.path] += 1
        if not hits[q.id]:
            wrong[q.path] += 1
            missed[q.path].add(families.get(q.id, "unsupported"))
    order = sorted(asked, key=lambda f: (-wrong[f], -(errors.get(f, 0) if errors else 0), f))
    return [
        WorstImage(
            file=file,
            wrong=wrong[file],
            questions=asked[file],
            count_error=errors.get(file) if errors is not None else None,
            families=sorted(missed[file]),
        )
        for file in order[:top]
    ]


def mcnemar_p(a_only: int, b_only: int) -> float:
    """Exact two-sided McNemar p: the binomial test of the discordant pairs at 1/2."""
    n = a_only + b_only
    if n == 0:
        return 1.0
    tail = sum(comb(n, i) for i in range(min(a_only, b_only) + 1))
    return min(1.0, 2 * tail / 2**n)


def paired(
    questions: Sequence[NumberedQuestion],
    hits_a: Mapping[int, bool],
    hits_b: Mapping[int, bool],
    seed: int = AB_SEED,
    reps: int = BOOTSTRAP_REPS,
) -> Paired:
    """B against A on the same questions; the bootstrap resamples images (reps 0: no interval)."""
    per_image: dict[str, list[int]] = defaultdict(lambda: [0, 0])  # questions, B - A hits
    a_only = b_only = 0
    for q in questions:
        a, b = hits_a[q.id], hits_b[q.id]
        a_only += a and not b
        b_only += b and not a
        per_image[q.path][0] += 1
        per_image[q.path][1] += int(b) - int(a)
    files = sorted(per_image)
    sizes = [per_image[f][0] for f in files]
    deltas = [per_image[f][1] for f in files]
    total = sum(sizes)
    diff = sum(deltas) / total if total else None
    low = high = None
    if reps > 0 and files:
        rng = random.Random(seed)
        draws: list[float] = []
        for _ in range(reps):
            picks = rng.choices(range(len(files)), k=len(files))
            draws.append(sum(map(deltas.__getitem__, picks)) / sum(map(sizes.__getitem__, picks)))
        draws.sort()
        low, high = draws[int(0.025 * reps)], draws[min(reps - 1, int(0.975 * reps))]
    p = mcnemar_p(a_only, b_only)
    if low is not None and high is not None:
        verdict: Verdict = "B better" if low > 0 else "A better" if high < 0 else "no difference"
    else:
        verdict = "no difference"
    return Paired(
        images=len(files),
        questions=total,
        diff=diff,
        ci_low=low,
        ci_high=high,
        a_only=a_only,
        b_only=b_only,
        mcnemar_p=p,
        verdict=verdict,
    )


def arm_result(
    name: str,
    source: str,
    questions: Sequence[NumberedQuestion],
    hits: Mapping[int, bool],
    families: Mapping[int, str],
    files: Sequence[str],
    present: Iterable[str],
    counts: dict[str, CountStat] | None,
    orientation: Mapping[str, str] | None,
    errors: Mapping[str, int] | None = None,
) -> ArmResult:
    have = set(present)
    return ArmResult(
        name=name,
        source=source,
        images=len(files),
        missing_images=sum(file not in have for file in files),
        overall=_rate(sum(hits[q.id] for q in questions), len(questions)),
        by_family=rates_by(questions, hits, lambda q: families.get(q.id, "unsupported")),
        by_style=rates_by(questions, hits, lambda q: style_of(q.path)),
        by_orientation=None
        if orientation is None
        else rates_by(questions, hits, lambda q: orientation.get(q.path, "unknown")),
        counts=counts,
        worst=worst_images(questions, hits, families, errors),
    )


def compare(
    questions: Sequence[NumberedQuestion],
    a: tuple[ArmResult, Mapping[int, bool]],
    b: tuple[ArmResult, Mapping[int, bool]],
    families: Mapping[int, str],
    seed: int = AB_SEED,
    reps: int = BOOTSTRAP_REPS,
) -> tuple[Paired, dict[str, Paired], dict[str, tuple[int, int, int]]]:
    """The overall paired comparison, one per family (the same seed and resamples, the family's
    questions only), and per-image hits."""
    (_, hits_a), (_, hits_b) = a, b
    overall = paired(questions, hits_a, hits_b, seed, reps)
    grouped: dict[str, list[NumberedQuestion]] = defaultdict(list)
    for q in questions:
        grouped[families.get(q.id, "unsupported")].append(q)
    by_family = {
        name: paired(grouped[name], hits_a, hits_b, seed, reps) for name in sorted(grouped)
    }
    per_image: dict[str, list[int]] = defaultdict(lambda: [0, 0, 0])
    for q in questions:
        per_image[q.path][0] += 1
        per_image[q.path][1] += hits_a[q.id]
        per_image[q.path][2] += hits_b[q.id]
    return overall, by_family, {f: (n, x, y) for f, (n, x, y) in sorted(per_image.items())}


def _pct(rate: float | None) -> str:
    return "n/a" if rate is None else f"{rate:.1%}"


def _signed(value: float | None) -> str:
    return "n/a" if value is None else f"{value * 100:+.1f} pp"


def format_ab(result: AbResult) -> str:
    a, b, p = result.a, result.b, result.paired
    lines = [
        f"## A/B on {result.part}: A = {a.name}, B = {b.name}",
        "",
        f"A: {a.source} ({a.missing_images} of {a.images} images missing)  ",
        f"B: {b.source} ({b.missing_images} of {b.images} images missing)",
        "",
        "| | A | B | B - A |",
        "| --- | --- | --- | --- |",
        f"| exact, all questions | {_pct(a.overall.rate)} ({a.overall.hits}/{a.overall.n}) "
        f"| {_pct(b.overall.rate)} ({b.overall.hits}/{b.overall.n}) | {_signed(p.diff)} |",
        "",
        f"Paired over {p.images} images, {p.questions} questions: B - A = {_signed(p.diff)}, "
        f"95% bootstrap interval [{_signed(p.ci_low)}, {_signed(p.ci_high)}] "
        f"({result.bootstrap_reps} resamples, seed {result.seed}). Verdict (from the interval): "
        f"**{p.verdict}**. McNemar exact p = {p.mcnemar_p:.3g} ({MCNEMAR_NOTE}; only A right "
        f"{p.a_only}, only B right {p.b_only}).",
        "",
        "Per family: the same bootstrap on the family's questions. Each interval holds for a "
        "family named in advance; across all families, about 1 in 20 excludes 0 by chance.",
        "",
        f"| family | questions | A | B | B - A | 95% interval | verdict | McNemar p "
        f"({MCNEMAR_NOTE}) |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for name, pair in result.paired_by_family.items():
        ra, rb = a.by_family[name], b.by_family[name]
        lines.append(
            f"| {name} | {ra.n} | {_pct(ra.rate)} | {_pct(rb.rate)} | {_signed(pair.diff)} "
            f"| [{_signed(pair.ci_low)}, {_signed(pair.ci_high)}] | {pair.verdict} "
            f"| {pair.mcnemar_p:.3g} |"
        )
    lines += ["", "| style | questions | A | B |", "| --- | --- | --- | --- |"]
    for name, ra in a.by_style.items():
        rb = b.by_style[name]
        lines.append(f"| {name} | {ra.n} | {_pct(ra.rate)} | {_pct(rb.rate)} |")
    lines.append("")
    if a.by_orientation is not None and b.by_orientation is not None:
        lines += ["| orientation | questions | A | B |", "| --- | --- | --- | --- |"]
        for name, ra in a.by_orientation.items():
            rb = b.by_orientation[name]
            lines.append(f"| {name} | {ra.n} | {_pct(ra.rate)} | {_pct(rb.rate)} |")
        lines.append("")
    lines.append(f"Orientation: {result.orientation}")
    for label, arm in (("A", a), ("B", b)):
        lines += [
            "",
            f"{label} ({arm.name}): the {len(arm.worst)} images with the most wrong answers",
            "",
            "| image | wrong | count error | families wrong |",
            "| --- | --- | --- | --- |",
        ]
        for image in arm.worst:
            error = "-" if image.count_error is None else str(image.count_error)
            lines.append(
                f"| {image.file} | {image.wrong}/{image.questions} | {error} "
                f"| {', '.join(image.families)} |"
            )
    keys = list((a.counts or b.counts or {}).keys())
    if keys:
        lines += [
            "",
            "Counts against the dev gold, per image (exact share; mean absolute error):",
            "",
            "| count | images | A exact | A MAE | B exact | B MAE |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
        for key in keys:
            ca = a.counts[key] if a.counts else None
            cb = b.counts[key] if b.counts else None
            either = ca or cb
            images = either.images if either is not None else 0
            lines.append(
                f"| {key} | {images} | {_pct(ca.exact_rate) if ca else '-'} "
                f"| {f'{ca.mae:.2f}' if ca and ca.mae is not None else '-'} "
                f"| {_pct(cb.exact_rate) if cb else '-'} "
                f"| {f'{cb.mae:.2f}' if cb and cb.mae is not None else '-'} |"
            )
    return "\n".join(lines)

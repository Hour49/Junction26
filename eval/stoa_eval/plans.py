"""Golden v2, picked by drawing file: the files whose extraction is scored (Part 1) and whose
questions are answered (Part 2). dev/eval come from the sealed split, by drawing group.

Spread within a source: files are dealt round-robin over strata, each stratum in seeded order.
CubiCasa strata are multi-plan vs single-plan sheets (from the "How many floors" answer, never from
annotations); ifc_models and opening_design strata are the model or project, so every model is
picked once before any is picked twice.

The scale case list adds files until each scale case (scale_scoring.ScaleCase) has SCALE_QUOTA files
in dev and in eval where the gold has them, dealt round-robin over sources; plan picks count first.

The conflict slice: every file in the gold's `_conflicts/conflicts.jsonl` (review-10) joins v2 after
the plan and scale picks, so adding conflicts never changes which other files are picked; its
conflicts are merged into the copied gold file. A file that joins only for the slice (stratum
`conflict`) is scored only there: no scale case, no Part 1 headline, and its questions stay out of
Part 2 (orchestrator, 2026-11-13 23:29).

A frozen set (`select-plans --keep <v2 manifest>`): every file of an earlier v2 stays with its split
and stratum, and only the conflict slice and the scale-case labels are recomputed, so better gold
never reshuffles the set the recorded runs compare against (orchestrator, 2026-11-13 23:48).
"""

from collections.abc import Iterable, Mapping, Sequence, Set
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .extraction import Conflict
from .families import group_of, source_of
from .models import Question
from .scale_scoring import ScaleCase
from .split import DEFAULT_SEED, rank

Quota = tuple[int, int]  # dev, eval
QUOTAS: dict[str, Quota] = {
    "cubicasa5k": (30, 10),
    "swiss_dwellings": (22, 8),
    "ifc_models": (11, 4),
    "opening_design": (8, 2),
}
SCALE_QUOTA: Quota = (10, 3)  # per scale case
FLOORS_QUESTION = "How many floors"
Split = Literal["dev", "eval"]
CONFLICT_EXTRA_IDS = range(1_001_001, 1_002_000)  # review-10's extras ids (formats-v1-1 §3)


class ConflictFile(BaseModel):
    """One line of extraction_gold/_conflicts/conflicts.jsonl: a file's checked conflicts."""

    model_config = ConfigDict(extra="forbid")

    file: str
    split: Split
    conflicts: list[Conflict] = Field(min_length=1)


class PlansParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: str = "v2"
    seed: int = DEFAULT_SEED
    quotas: dict[str, Quota] = Field(default_factory=lambda: dict(QUOTAS))
    scale_quota: Quota = SCALE_QUOTA


class PlanFile(BaseModel):
    """One line of part1_extraction/files.jsonl."""

    model_config = ConfigDict(extra="forbid")

    file: str
    source: str
    split: Literal["dev", "eval"]
    truth: Literal["elements", "counts", "tables"] | None = Field(
        description="from the gold; null if none"
    )
    stratum: str = Field(
        description="the plan stratum; scale or conflict for a file picked for that slice"
    )
    scale_case: ScaleCase | None = Field(description="its scale case, if the gold makes it one")


class SourceCount(BaseModel):
    model_config = ConfigDict(extra="forbid")

    wanted: Quota
    picked: Quota
    available: Quota


class PlansManifest(BaseModel):
    """data/stoa/golden/v2/manifest.json: how both parts were made, and every file's sha256."""

    model_config = ConfigDict(extra="forbid")

    params: PlansParams
    questions_sha256: str
    split_manifest_sha256: str
    by_source: dict[str, SourceCount]
    scale_cases: dict[str, SourceCount] = Field(description="scale case -> files (dev, eval)")
    missing_gold: list[str]
    conflict_files: list[str] = Field(
        default_factory=list[str], description="files whose gold lists conflicts (the slice)"
    )
    unscaled: list[str] = Field(
        default_factory=list[str],
        description="--allow-unscaled: gold without a scale value or room areas, built anyway",
    )
    kept: str | None = Field(
        default=None,
        description="--keep: sha256 of the earlier files.jsonl whose files were kept; null when "
        "the files were picked",
    )
    files_sha256: dict[str, str] = Field(description="path under v2/ -> sha256, both parts")


def strata(questions: Iterable[Question]) -> dict[str, str]:
    """file -> stratum for every drawing that has a question, in the four picked sources (IFC
    model files are not drawings: their questions stay out of v2)."""
    found: dict[str, str] = {}
    for question in questions:
        source = source_of(question.path)
        if source not in QUOTAS or question.path.endswith(".ifc"):
            continue
        if source == "cubicasa5k":
            current = found.setdefault(question.path, "single-plan")
            multi = question.question.startswith(FLOORS_QUESTION) and question.answer not in (0, 1)
            found[question.path] = "multi-plan" if multi else current
        elif source in ("ifc_models", "opening_design"):
            found[question.path] = group_of(question.path)
        else:
            found[question.path] = "all"
    return found


def _deal(files: Iterable[str], stratum_of: Mapping[str, str], want: int, seed: int) -> list[str]:
    """Up to `want` files, round-robin over strata (sorted by name), each in seeded order."""
    queues: dict[str, list[str]] = {}
    for file in sorted(files, key=lambda file: rank(seed, "plan", file)):
        queues.setdefault(stratum_of[file], []).append(file)
    picked: list[str] = []
    while len(picked) < want and any(queues.values()):
        for name in sorted(queues):
            if queues[name] and len(picked) < want:
                picked.append(queues[name].pop(0))
    return picked


def pick(
    stratum_of: Mapping[str, str], eval_groups: Set[str], params: PlansParams
) -> tuple[dict[str, Literal["dev", "eval"]], dict[str, tuple[Quota, Quota]]]:
    """file -> split for the picked files, and per source ((picked dev, eval), (available dev,
    eval))."""
    chosen: dict[str, Literal["dev", "eval"]] = {}
    counts: dict[str, tuple[Quota, Quota]] = {}
    for source, (want_dev, want_eval) in sorted(params.quotas.items()):
        files = [file for file in stratum_of if source_of(file) == source]
        held = [file for file in files if group_of(file) in eval_groups]
        dev = [file for file in files if group_of(file) not in eval_groups]
        dev_picked = _deal(dev, stratum_of, want_dev, params.seed)
        eval_picked = _deal(held, stratum_of, want_eval, params.seed)
        chosen.update(dict.fromkeys(dev_picked, "dev"))
        chosen.update(dict.fromkeys(eval_picked, "eval"))
        counts[source] = ((len(dev_picked), len(eval_picked)), (len(dev), len(held)))
    return chosen, counts


def pick_scale_cases(
    cases: Mapping[str, tuple[ScaleCase, Split]], chosen: Mapping[str, Split], params: PlansParams
) -> tuple[dict[str, Split], dict[str, tuple[Quota, Quota]]]:
    """Extra files (file -> split) so that every scale case reaches the quota in dev and eval, and
    per case ((files dev, eval), (available dev, eval)). `cases` holds every gold scale case."""
    extra: dict[str, Split] = {}
    counts: dict[str, tuple[Quota, Quota]] = {}
    for case in sorted({case for case, _ in cases.values()}):
        got: list[int] = []
        available: list[int] = []
        for split, want in zip(("dev", "eval"), params.scale_quota, strict=True):
            files = [f for f, (c, s) in cases.items() if c == case and s == split]
            have = [f for f in files if f in chosen]
            rest = [f for f in files if f not in chosen]
            more = _deal(rest, {f: source_of(f) for f in rest}, want - len(have), params.seed)
            extra.update(dict.fromkeys(more, split))
            got.append(len(have) + len(more))
            available.append(len(files))
        counts[case] = ((got[0], got[1]), (available[0], available[1]))
    return extra, counts


def keep(
    kept: Sequence[PlanFile],
    stratum_of: Mapping[str, str],
    eval_groups: Set[str],
    params: PlansParams,
) -> tuple[dict[str, Split], dict[str, str], dict[str, tuple[Quota, Quota]]]:
    """A frozen set: file -> split and file -> stratum for every kept file but the conflict-only
    ones (the slice is recomputed), and per source ((plan picks dev, eval), (available dev, eval))
    counted as `pick` counts them."""
    files = {line.file: line for line in kept if line.stratum != "conflict"}
    counts: dict[str, tuple[Quota, Quota]] = {}
    for source in sorted(params.quotas):
        available = [file for file in stratum_of if source_of(file) == source]
        held = sum(group_of(file) in eval_groups for file in available)
        plan = [files[f] for f in available if f in files and files[f].stratum != "scale"]
        dev = sum(line.split == "dev" for line in plan)
        counts[source] = ((dev, len(plan) - dev), (len(available) - held, held))
    chosen: dict[str, Split] = {file: line.split for file, line in files.items()}
    return chosen, {file: line.stratum for file, line in files.items()}, counts


def count_scale_cases(
    cases: Mapping[str, tuple[ScaleCase, Split]], chosen: Mapping[str, Split]
) -> dict[str, tuple[Quota, Quota]]:
    """Per scale case ((files dev, eval) in `chosen`, (available dev, eval)): a frozen set's cases,
    recomputed from the current gold."""
    counts: dict[str, tuple[Quota, Quota]] = {}
    for case in sorted({case for case, _ in cases.values()}):
        files = [(file, split) for file, (c, split) in cases.items() if c == case]
        got = [sum(f in chosen for f, s in files if s == split) for split in ("dev", "eval")]
        available = [sum(s == split for _, s in files) for split in ("dev", "eval")]
        counts[case] = ((got[0], got[1]), (available[0], available[1]))
    return counts

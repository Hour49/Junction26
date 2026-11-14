"""The experiment split (`data/stoa/exp/split.json`): CubiCasa dev images cut into train, val and
test for the experiment tracks (`.agents/briefs/exp-common.md`, 2026-11-14).

Only images whose questions are in the sealed split's `dev.jsonl` take part, minus every golden v2
file (dev and eval), so a model trained or tuned here never saw a golden or eval drawing. Images
are cut by the sealed split's own group key (`families.group_of`), so one group never spans two
parts. Groups are dealt in a seeded hash order (`split.rank`): the first 10% go to test, the next
10% to val, the rest to train, so a rerun gives the same file on every machine.
"""

from collections import Counter
from collections.abc import Iterable, Mapping
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .extraction import Extraction
from .families import group_of
from .split import rank

ExpPart = Literal["train", "val", "test"]
EXP_PARTS: tuple[ExpPart, ...] = ("train", "val", "test")
DEFAULT_EXP_SEED = 20261114
DEFAULT_SHARES: dict[ExpPart, float] = {"train": 0.8, "val": 0.1, "test": 0.1}
EXP_SOURCE = "cubicasa5k"


def assign_parts(
    groups: Iterable[str],
    seed: int = DEFAULT_EXP_SEED,
    shares: Mapping[ExpPart, float] | None = None,
) -> dict[str, ExpPart]:
    """group -> part. Test takes the first round(share x n) groups in seeded order, val the next,
    train the rest; the order doesn't depend on the input order."""
    shares = shares or DEFAULT_SHARES
    ranked = sorted(set(groups), key=lambda group: rank(seed, "exp", group))
    n_test = round(shares["test"] * len(ranked))
    n_val = round(shares["val"] * len(ranked))
    parts: dict[str, ExpPart] = {}
    for index, group in enumerate(ranked):
        parts[group] = "test" if index < n_test else "val" if index < n_test + n_val else "train"
    return parts


class PartTotals(BaseModel):
    """Class totals of one part's dev gold."""

    model_config = ConfigDict(extra="forbid")

    images: int
    groups: int
    questions: int
    questions_sha256: str = Field(description="of <part>_questions.jsonl")
    elements: dict[str, int] = Field(description="element class -> count")
    rooms: dict[str, int] = Field(description="room type -> count")
    plans: int
    plans_per_image: dict[str, int] = Field(description="number of plans -> images")


class ExpPartImages(PartTotals):
    files: list[str] = Field(description="dataset paths (data/cubicasa5k/<name>.png), sorted")


class ExpSplit(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: Literal[1] = 1
    source: str = EXP_SOURCE
    seed: int
    shares: dict[ExpPart, float]
    split_manifest_sha256: str = Field(description="data/stoa/split/manifest.json")
    golden_manifest_sha256: str = Field(description="data/stoa/golden/v2/manifest.json")
    excluded_golden: list[str] = Field(description="dev images left out as golden v2 files")
    parts: dict[ExpPart, ExpPartImages]

    def part_of(self) -> dict[str, ExpPart]:
        """file -> part."""
        return {file: name for name, part in self.parts.items() for file in part.files}


def totals(golds: Iterable[Extraction]) -> tuple[Counter[str], Counter[str], int, Counter[str]]:
    """(elements by class, rooms by type, plans, images by plan count) over gold files."""
    elements: Counter[str] = Counter()
    rooms: Counter[str] = Counter()
    per_image: Counter[str] = Counter()
    plans = 0
    for gold in golds:
        elements.update(element.class_ for element in gold.elements)
        rooms.update(room.type for room in gold.rooms)
        plans += len(gold.plans)
        per_image[str(len(gold.plans))] += 1
    return elements, rooms, plans, per_image


def check_dev_only(
    files: Iterable[str], eval_groups: set[str], golden_files: set[str], golds: Mapping[str, str]
) -> None:
    """Fails when an experiment image is in an eval group, is a golden v2 file, shares a group with
    one, or has gold that is not marked dev. `golds`: file -> its gold's split."""
    golden_groups = {group_of(file) for file in golden_files}
    for file in files:
        group = group_of(file)
        if group in eval_groups:
            raise ValueError(f"{file} is in the sealed eval group {group}")
        if file in golden_files or group in golden_groups:
            raise ValueError(f"{file} is a golden v2 drawing (group {group})")
        if golds.get(file) != "dev":
            raise ValueError(f"{file}: its gold is {golds.get(file)!r}, not a dev file")

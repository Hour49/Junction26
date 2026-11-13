"""Seeded, stratified selection of the golden set and its dev/holdout split.

v0 is provisional: the golden-set spec is written after the reviewers report, so every choice that
spec may change is a parameter (`SelectionParams`). The same questions and params always give the
same selection, on any machine (ranks are sha256 hashes, not `random`).

Splits are made per drawing group (`families.group_of`), stratified by source, before any question
is picked: every question in the dataset belongs to dev or holdout, so tuning on more dev questions
than the golden ones never touches a holdout drawing. Then each cell (by default source x type x
language) gets `per_cell` questions (or all it has), split by `holdout_ratio` where both splits
have questions in the cell, spread round robin over the cell's templates and, while possible, over
different drawings.
"""

import hashlib
import math
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .families import group_of, language_of, source_of, template_of
from .models import GoldenItem, Question, Split

CellKey = Literal["source", "type", "language", "template"]
SPLITS: tuple[Split, ...] = ("dev", "holdout")


class SelectionParams(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    version: str = Field(default="v0", pattern=r"^v\d+$")
    cell_keys: tuple[CellKey, ...] = Field(default=("source", "type", "language"), min_length=1)
    per_cell: int = Field(default=4, ge=1)
    holdout_ratio: float = Field(default=0.5, ge=0.0, le=1.0)
    seed: int = 20261113


class CellCount(BaseModel):
    cell: dict[str, str]
    available: int
    dev: int
    holdout: int


class Manifest(BaseModel):
    """Written next to the golden file: how it was made, and which groups are holdout."""

    params: SelectionParams
    questions_sha256: str
    cells: list[CellCount]
    holdout_groups: list[str] = Field(description="never tune on questions about these")


class Selection(BaseModel):
    items: list[GoldenItem]
    cells: list[CellCount]
    holdout_groups: list[str]


def _rank(seed: int, kind: str, value: object) -> str:
    return hashlib.sha256(f"{seed}:{kind}:{value}".encode()).hexdigest()


def _round_half_up(value: float) -> int:
    return math.floor(value + 0.5)


def holdout_groups(
    groups_by_source: Mapping[str, Iterable[str]], ratio: float, seed: int
) -> set[str]:
    """`ratio` of each source's groups, by seeded rank; at least one group per split when the
    source has two or more and the ratio isn't 0 or 1."""
    chosen: set[str] = set()
    for groups in groups_by_source.values():
        ranked = sorted(set(groups), key=lambda group: _rank(seed, "group", group))
        count = _round_half_up(len(ranked) * ratio)
        if len(ranked) >= 2 and 0.0 < ratio < 1.0:
            count = min(max(count, 1), len(ranked) - 1)
        chosen.update(ranked[:count])
    return chosen


def annotate(rows: Sequence[tuple[int, Question]], params: SelectionParams) -> list[GoldenItem]:
    """Every question with its id, source, language, template, group and split."""
    templates: dict[str, str] = {}
    languages: dict[str, str] = {}
    groups_by_source: dict[str, set[str]] = defaultdict(set)
    for _, question in rows:
        if question.question not in templates:
            template = template_of(question.question)
            templates[question.question] = template
            languages.setdefault(template, language_of(template))
        groups_by_source[source_of(question.path)].add(group_of(question.path))
    holdout = holdout_groups(groups_by_source, params.holdout_ratio, params.seed)
    items: list[GoldenItem] = []
    for line, question in rows:
        template = templates[question.question]
        group = group_of(question.path)
        items.append(
            GoldenItem(
                **question.model_dump(),
                id=line,
                source=source_of(question.path),
                language=languages[template],
                template=template,
                group=group,
                split="holdout" if group in holdout else "dev",
            )
        )
    return items


def _pick(candidates: Sequence[GoldenItem], count: int, seed: int) -> list[GoldenItem]:
    """`count` items, round robin over templates; a drawing group repeats only when no unused one
    is left."""
    by_template: dict[str, list[GoldenItem]] = defaultdict(list)
    for item in sorted(candidates, key=lambda item: _rank(seed, "item", item.id)):
        by_template[item.template].append(item)
    order = sorted(by_template, key=lambda template: _rank(seed, "template", template))
    picked: list[GoldenItem] = []
    taken: set[int] = set()
    used_groups: set[str] = set()
    for repeat_groups in (False, True):
        progress = True
        while progress and len(picked) < count:
            progress = False
            for template in order:
                if len(picked) == count:
                    break
                item = next(
                    (
                        item
                        for item in by_template[template]
                        if item.id not in taken and (repeat_groups or item.group not in used_groups)
                    ),
                    None,
                )
                if item is not None:
                    picked.append(item)
                    taken.add(item.id)
                    used_groups.add(item.group)
                    progress = True
    return picked


def select(rows: Sequence[tuple[int, Question]], params: SelectionParams) -> Selection:
    pool = annotate(rows, params)
    cells: dict[tuple[str, ...], list[GoldenItem]] = defaultdict(list)
    for item in pool:
        cells[tuple(str(getattr(item, key)) for key in params.cell_keys)].append(item)
    holdout_count = _round_half_up(params.per_cell * params.holdout_ratio)
    wanted = {"dev": params.per_cell - holdout_count, "holdout": holdout_count}
    chosen: list[GoldenItem] = []
    counts: list[CellCount] = []
    for key in sorted(cells):
        in_split = {split: [item for item in cells[key] if item.split == split] for split in SPLITS}
        # A split with too few questions in this cell (often one building per language) leaves
        # the rest of its share to the other split, so the cell still gets `per_cell` questions.
        spare = {split: max(0, wanted[split] - len(in_split[split])) for split in SPLITS}
        picked = {
            split: _pick(in_split[split], wanted[split] + spare[other], params.seed)
            for split, other in (("dev", "holdout"), ("holdout", "dev"))
        }
        chosen += picked["dev"] + picked["holdout"]
        counts.append(
            CellCount(
                cell=dict(zip(params.cell_keys, key, strict=True)),
                available=len(cells[key]),
                dev=len(picked["dev"]),
                holdout=len(picked["holdout"]),
            )
        )
    return Selection(
        items=sorted(chosen, key=lambda item: item.id),
        cells=counts,
        holdout_groups=sorted({item.group for item in pool if item.split == "holdout"}),
    )

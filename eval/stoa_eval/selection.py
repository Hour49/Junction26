"""Seeded, stratified selection of the golden set.

The selection is provisional until the golden-set spec, so every choice that spec may change is a
parameter (`SelectionParams`). The same questions, split and params always give the same selection,
on any machine (ranks are sha256 hashes, not `random`).

`holdout` items come only from the sealed eval split's groups (`split.eval_groups`), `dev` items
only from the other 80%. Each cell (by default source x type x language) gets `per_cell` questions
(or all it has), split by `holdout_ratio` where both splits have questions in the cell, spread round
robin over the cell's templates and, while possible, over different drawings.
"""

import math
from collections import defaultdict
from collections.abc import Sequence, Set
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .families import group_of, language_of, source_of, template_of
from .models import GoldenItem, Question, Split
from .split import DEFAULT_EVAL_SHARE, DEFAULT_SEED, rank

CellKey = Literal["source", "type", "language", "template"]
SPLITS: tuple[Split, ...] = ("dev", "holdout")


class SelectionParams(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    version: str = Field(default="v1", pattern=r"^v\d+$")
    cell_keys: tuple[CellKey, ...] = Field(default=("source", "type", "language"), min_length=1)
    per_cell: int = Field(default=4, ge=1)
    holdout_ratio: float = Field(default=DEFAULT_EVAL_SHARE, ge=0.0, le=1.0)
    seed: int = DEFAULT_SEED


class CellCount(BaseModel):
    cell: dict[str, str]
    available: int
    dev: int
    holdout: int


class Manifest(BaseModel):
    """Written next to the golden file: how it was made, and from which split."""

    params: SelectionParams
    questions_sha256: str
    split_manifest_sha256: str = Field(description="the split whose eval groups gave holdout")
    cells: list[CellCount]


class Selection(BaseModel):
    items: list[GoldenItem]
    cells: list[CellCount]


def _round_half_up(value: float) -> int:
    return math.floor(value + 0.5)


def annotate(rows: Sequence[tuple[int, Question]], holdout: Set[str]) -> list[GoldenItem]:
    """Every question with its id, source, language, template, group and split (holdout when its
    group is in `holdout`, the sealed split's eval groups)."""
    templates: dict[str, str] = {}
    languages: dict[str, str] = {}
    for _, question in rows:
        if question.question not in templates:
            template = template_of(question.question)
            templates[question.question] = template
            languages.setdefault(template, language_of(template))
    items: list[GoldenItem] = []
    for line, question in rows:
        template = templates[question.question]
        group = group_of(question.path)
        items.append(
            GoldenItem(
                path=question.path,
                question=question.question,
                answer=question.answer,
                unit=question.unit,
                type=question.type,
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
    for item in sorted(candidates, key=lambda item: rank(seed, "item", item.id)):
        by_template[item.template].append(item)
    order = sorted(by_template, key=lambda template: rank(seed, "template", template))
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


def select(
    rows: Sequence[tuple[int, Question]], params: SelectionParams, holdout: Set[str]
) -> Selection:
    pool = annotate(rows, holdout)
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
    return Selection(items=sorted(chosen, key=lambda item: item.id), cells=counts)

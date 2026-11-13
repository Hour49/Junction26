"""The sealed split: about 20% of the questions go to `eval` and everything we build or tune uses
only the other 80% (`dev`).

Owner, 2026-11-13 20:25: "also keep 20% of the questions not in the dataset so we can use that as
an eval". The split is by drawing group (`families.group_of`), so a drawing in another format, the
floors of one building or the models of one IFC building never straddle it. It is stratified per
source: each source's groups join eval in seeded rank order as long as they fit under the share of
the source's questions, then one more group joins if it lands closer to the share. A source with
two or more groups gets at least one eval group.
The golden set's holdout items come from these eval groups (`selection.select`).
"""

import hashlib
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping

from pydantic import BaseModel, Field

from .families import group_of, source_of
from .models import Question

DEFAULT_SEED = 20261113
DEFAULT_EVAL_SHARE = 0.2
SPLIT_NAMES = ("dev", "eval")


def rank(seed: int, kind: str, value: object) -> str:
    """A seeded order that is the same on every machine and Python version."""
    return hashlib.sha256(f"{seed}:{kind}:{value}".encode()).hexdigest()


def group_sizes(questions: Iterable[Question]) -> dict[str, Counter[str]]:
    """source -> group -> number of questions."""
    sizes: dict[str, Counter[str]] = defaultdict(Counter)
    for question in questions:
        sizes[source_of(question.path)][group_of(question.path)] += 1
    return sizes


def eval_groups(sizes: Mapping[str, Mapping[str, int]], share: float, seed: int) -> set[str]:
    chosen: set[str] = set()
    for groups in sizes.values():
        target = share * sum(groups.values())
        ranked = sorted(groups, key=lambda group: rank(seed, "group", group))
        picked: list[str] = []
        taken = 0
        for group in ranked:
            if taken + groups[group] <= target:
                picked.append(group)
                taken += groups[group]
        inside = set(picked)
        rest = [group for group in ranked if group not in inside]
        if rest:
            closest = min(rest, key=lambda group: abs(taken + groups[group] - target))
            if abs(taken + groups[closest] - target) < abs(taken - target):
                picked.append(closest)
        if not picked and len(ranked) >= 2 and share > 0.0:
            picked.append(min(ranked, key=lambda group: abs(groups[group] - target)))
        chosen.update(picked)
    return chosen


class SplitCount(BaseModel):
    dev_questions: int = 0
    eval_questions: int = 0
    dev_groups: int = 0
    eval_groups: int = 0
    eval_share: float | None = Field(default=None, description="eval questions / questions")


class SplitManifest(BaseModel):
    seed: int
    eval_share_target: float
    questions_sha256: str
    files_sha256: dict[str, str] = Field(description="dev.jsonl and eval.jsonl")
    by_source: dict[str, SplitCount]
    by_source_type: dict[str, SplitCount]
    eval_groups: list[str]


def split_counts(rows: Iterable[tuple[Question, str]]) -> dict[str, dict[str, SplitCount]]:
    """Questions and groups per split, by source and by source/type, from (question, split)."""
    questions: Counter[tuple[str, str, str]] = Counter()
    groups: dict[tuple[str, str, str], set[str]] = defaultdict(set)
    for question, split in rows:
        source = source_of(question.path)
        for level, key in (("source", source), ("source_type", f"{source}/{question.type}")):
            questions[level, key, split] += 1
            groups[level, key, split].add(group_of(question.path))
    counts: dict[str, dict[str, SplitCount]] = {"source": {}, "source_type": {}}
    for level, key in sorted({(level, key) for level, key, _ in questions}):
        count = SplitCount(
            dev_questions=questions[level, key, "dev"],
            eval_questions=questions[level, key, "eval"],
            dev_groups=len(groups[level, key, "dev"]),
            eval_groups=len(groups[level, key, "eval"]),
        )
        count.eval_share = count.eval_questions / (count.dev_questions + count.eval_questions)
        counts[level][key] = count
    return counts

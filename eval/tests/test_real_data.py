"""Checks on the real Stoa questions. The dataset is partner data and never in the repo or CI, so
these skip unless it was fetched (tools/fetch_stoa_data.py full)."""

import pytest

from stoa_eval.baselines import oracle
from stoa_eval.cli import DEFAULT_QUESTIONS
from stoa_eval.families import UNDETERMINED
from stoa_eval.jsonl import read_jsonl
from stoa_eval.models import Question
from stoa_eval.scoring import score
from stoa_eval.selection import SelectionParams, annotate, select
from stoa_eval.split import DEFAULT_EVAL_SHARE, DEFAULT_SEED, eval_groups, group_sizes

pytestmark = pytest.mark.skipif(
    not DEFAULT_QUESTIONS.exists(),
    reason="no dataset: run `python3 tools/fetch_stoa_data.py full` from the repo root",
)


def test_split_and_golden_set_on_the_real_questions() -> None:
    rows = read_jsonl(DEFAULT_QUESTIONS, Question)
    sizes = group_sizes(question for _, question in rows)
    sealed = eval_groups(sizes, DEFAULT_EVAL_SHARE, DEFAULT_SEED)
    for source, groups in sizes.items():
        held = sum(size for group, size in groups.items() if group in sealed)
        if len(groups) >= 2:
            assert held > 0, source
        if len(groups) >= 1000:  # cubicasa5k, swiss_dwellings: many small groups
            assert held / sum(groups.values()) == pytest.approx(0.2, abs=0.005), source
    pool = annotate(rows, sealed)
    assert [item for item in pool if item.language == UNDETERMINED] == []
    selection = select(rows, SelectionParams(), sealed)
    cells = {(item.source, item.type, item.language) for item in pool}
    assert {(item.source, item.type, item.language) for item in selection.items} == cells
    assert 100 <= len(selection.items) <= 200
    assert all((item.split == "holdout") == (item.group in sealed) for item in selection.items)
    assert score(selection.items, oracle(selection.items)).overall.accuracy == 1.0

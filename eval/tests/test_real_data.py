"""Checks on the real Stoa questions. The dataset is partner data and never in the repo or CI, so
these skip unless it was fetched (tools/fetch_stoa_data.py full)."""

import pytest

from stoa_eval.baselines import oracle
from stoa_eval.cli import DEFAULT_GOLDEN, DEFAULT_QUESTIONS, _part1_gold_for
from stoa_eval.evidence_scoring import score_evidence, scored_targets
from stoa_eval.families import UNDETERMINED
from stoa_eval.jsonl import read_jsonl
from stoa_eval.models import GoldenItem, Question
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


@pytest.mark.skipif(not DEFAULT_GOLDEN.exists(), reason="no golden v2: run select-plans")
def test_evidence_targets_agree_with_the_golden_answers() -> None:
    """Every count question's targets number its answer, and every room-area question's target
    rooms sum to it within 2%; the oracle's evidence (one box per target) scores 100%/100%."""
    golden = [item for _, item in read_jsonl(DEFAULT_GOLDEN, GoldenItem)]
    gold = _part1_gold_for(DEFAULT_GOLDEN)
    assert gold is not None
    checked = 0
    for item in golden:
        found = scored_targets(item, gold)
        if isinstance(found, str):
            continue
        subject, targets = found
        if item.type == "count":
            assert len(targets) == item.answer, (item.id, subject.family)
        elif subject.rooms is not None:
            areas = {room.id: room.area_m2 or 0.0 for room in gold[item.path].rooms}
            total = sum(areas[target.id] for target in targets)
            assert total == pytest.approx(item.answer, rel=0.02), (item.id, subject.family)
        else:
            continue
        checked += 1
    assert checked > 2000
    answers = {answer.id: answer for answer in oracle(golden, part1_gold=gold)}
    result = score_evidence(golden, answers, gold)
    assert result.overall.precision.accuracy == result.overall.recall.accuracy == 1.0

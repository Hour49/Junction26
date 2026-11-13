from collections import defaultdict

from stoa_eval.models import Question
from stoa_eval.selection import SelectionParams, annotate, holdout_groups, select
from tests.factories import make_questions


def rows() -> list[tuple[int, Question]]:
    return list(enumerate(make_questions(), 1))


def test_selection_is_deterministic() -> None:
    params = SelectionParams()
    first = select(rows(), params)
    assert select(rows(), params) == first
    other_seed = select(rows(), params.model_copy(update={"seed": 7}))
    assert [item.id for item in other_seed.items] != [item.id for item in first.items]


def test_every_cell_is_represented() -> None:
    params = SelectionParams()
    cells = {(item.source, item.type, item.language) for item in annotate(rows(), params)}
    selection = select(rows(), params)
    assert {(item.source, item.type, item.language) for item in selection.items} == cells
    assert len(selection.cells) == len(cells) == 8


def test_dev_and_holdout_are_disjoint_down_to_the_drawing() -> None:
    selection = select(rows(), SelectionParams(per_cell=6))
    dev = {item.id for item in selection.items if item.split == "dev"}
    holdout = {item.id for item in selection.items if item.split == "holdout"}
    assert dev and holdout and not dev & holdout
    splits_per_group: dict[str, set[str]] = defaultdict(set)
    for item in annotate(rows(), SelectionParams(per_cell=6)):
        splits_per_group[item.group].add(item.split)
    assert all(len(splits) == 1 for splits in splits_per_group.values())
    assert {item.group for item in selection.items if item.split == "holdout"} <= set(
        selection.holdout_groups
    )


def test_cell_counts_follow_per_cell_and_ratio() -> None:
    selection = select(rows(), SelectionParams(per_cell=4, holdout_ratio=0.25))
    counts = {tuple(cell.cell.values()): cell for cell in selection.cells}
    cubicasa_en = counts[("cubicasa5k", "count", "en")]
    assert (cubicasa_en.dev, cubicasa_en.holdout, cubicasa_en.available) == (3, 1, 12)
    assert all(cell.dev + cell.holdout == min(4, cell.available) for cell in selection.cells)


def test_a_cell_in_one_split_takes_its_whole_share_there() -> None:
    plan = "data/habs/only-sheet.pdf"
    habs = [
        Question(
            path=plan,
            question=f"How many doors are on floor {n}?",
            answer=n,
            unit="count",
            type="count",
        )
        for n in range(6)
    ]
    selection = select(list(enumerate(habs, 1)), SelectionParams(per_cell=4, holdout_ratio=0.5))
    [cell] = selection.cells
    assert sorted([cell.dev, cell.holdout]) == [0, 4]
    assert len(selection.items) == 4


def test_picks_spread_over_templates_and_drawings() -> None:
    selection = select(rows(), SelectionParams(per_cell=4, holdout_ratio=0.0))
    cubicasa_en = [i for i in selection.items if i.source == "cubicasa5k" and i.language == "en"]
    assert len(cubicasa_en) == 4
    assert len({item.template for item in cubicasa_en}) == 2  # both English templates
    assert len({item.group for item in cubicasa_en}) == 4  # four different plans


def test_cell_keys_are_a_parameter() -> None:
    selection = select(rows(), SelectionParams(cell_keys=("source",), per_cell=1))
    assert [cell.cell for cell in selection.cells] == [
        {"source": source}
        for source in sorted(
            ["cubicasa5k", "swiss_dwellings", "ifc_models", "ifc_bench", "opening_design"]
        )
    ]


def test_holdout_groups_keep_both_splits_per_source() -> None:
    groups = {"a": ["a/1", "a/2"], "b": ["b/1"], "c": [f"c/{n}" for n in range(10)]}
    chosen = holdout_groups(groups, 0.5, seed=1)
    assert len(chosen & {"a/1", "a/2"}) == 1
    assert len({g for g in chosen if g.startswith("c/")}) == 5
    assert len(holdout_groups(groups, 0.01, seed=1) & {"a/1", "a/2"}) == 1  # at least one
    assert holdout_groups(groups, 0.0, seed=1) == set()
    assert holdout_groups(groups, 1.0, seed=1) == {g for gs in groups.values() for g in gs}

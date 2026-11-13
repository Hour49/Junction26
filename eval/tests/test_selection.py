from stoa_eval.models import Question
from stoa_eval.selection import SelectionParams, annotate, select
from tests.factories import make_questions, sealed_groups


def rows() -> list[tuple[int, Question]]:
    return list(enumerate(make_questions(), 1))


SEALED = sealed_groups(rows())


def test_selection_is_deterministic() -> None:
    params = SelectionParams()
    first = select(rows(), params, SEALED)
    assert select(rows(), params, SEALED) == first
    other_seed = select(rows(), params.model_copy(update={"seed": 7}), SEALED)
    assert [item.id for item in other_seed.items] != [item.id for item in first.items]


def test_every_cell_is_represented() -> None:
    params = SelectionParams()
    cells = {(item.source, item.type, item.language) for item in annotate(rows(), SEALED)}
    selection = select(rows(), params, SEALED)
    assert {(item.source, item.type, item.language) for item in selection.items} == cells
    assert len(selection.cells) == len(cells) == 8


def test_holdout_comes_from_the_eval_groups_and_dev_from_the_rest() -> None:
    selection = select(rows(), SelectionParams(per_cell=6, holdout_ratio=0.5), SEALED)
    dev = [item for item in selection.items if item.split == "dev"]
    holdout = [item for item in selection.items if item.split == "holdout"]
    assert dev and holdout
    assert {item.group for item in holdout} <= SEALED
    assert not {item.group for item in dev} & SEALED
    pool = annotate(rows(), SEALED)
    assert all((item.split == "holdout") == (item.group in SEALED) for item in pool)


def test_cell_counts_follow_per_cell_and_ratio() -> None:
    selection = select(rows(), SelectionParams(per_cell=4, holdout_ratio=0.25), SEALED)
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
    for sealed in (set(), {"habs/only-sheet"}):
        selection = select(list(enumerate(habs, 1)), SelectionParams(per_cell=4), sealed)
        [cell] = selection.cells
        assert (cell.dev, cell.holdout) == ((0, 4) if sealed else (4, 0))


def test_picks_spread_over_templates_and_drawings() -> None:
    selection = select(rows(), SelectionParams(per_cell=4, holdout_ratio=0.0), SEALED)
    cubicasa_en = [i for i in selection.items if i.source == "cubicasa5k" and i.language == "en"]
    assert len(cubicasa_en) == 4
    assert len({item.template for item in cubicasa_en}) == 2  # both English templates
    assert len({item.group for item in cubicasa_en}) == 4  # four different plans


def test_cell_keys_are_a_parameter() -> None:
    selection = select(rows(), SelectionParams(cell_keys=("source",), per_cell=1), SEALED)
    assert [cell.cell for cell in selection.cells] == [
        {"source": source}
        for source in sorted(
            ["cubicasa5k", "swiss_dwellings", "ifc_models", "ifc_bench", "opening_design"]
        )
    ]

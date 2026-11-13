from stoa_eval.baselines import constant, oracle
from stoa_eval.models import AnswerValue, GoldenItem, QuestionType, Split, Unit
from stoa_eval.scoring import score
from stoa_eval.selection import SelectionParams, annotate, select
from tests.factories import make_questions


def row(
    id_: int,
    answer: AnswerValue,
    *,
    split: Split = "dev",
    template: str = "t",
    type_: QuestionType = "count",
    unit: Unit | None = "count",
    source: str = "cubicasa5k",
) -> GoldenItem:
    return GoldenItem(
        id=id_,
        path=f"data/{source}/p{id_}.png",
        question=template,
        answer=answer,
        unit=unit,
        type=type_,
        source=source,
        language="en",
        template=template,
        group=f"{source}/p{id_}",
        split=split,
    )


def test_oracle_scores_everything() -> None:
    rows = list(enumerate(make_questions(), 1))
    golden = select(rows, SelectionParams()).items
    result = score(golden, oracle(golden))
    assert result.overall.accuracy == 1.0
    assert result.overall.n == len(golden) > 0


def test_constant_learns_only_from_dev_outside_the_golden_set() -> None:
    golden = [row(1, 3)]
    pool = [
        row(1, 3),  # the golden question itself: never used
        row(2, 2),
        row(3, 2),
        row(4, 9, split="holdout"),
        row(5, 9, split="holdout"),
        row(6, 9, split="holdout"),
    ]
    [answer] = constant(golden, pool)
    assert (answer.answer, answer.unit, answer.method) == (2, "count", "constant:template")


def test_constant_uses_the_lower_median_for_measures() -> None:
    golden = [row(1, 10.0, type_="area", unit="m2")]
    pool = [
        row(n, value, type_="area", unit="m2")
        for n, value in [(2, 30.0), (3, 10.0), (4, 20.0), (5, 40.0)]
    ]
    [answer] = constant(golden, pool)
    assert (answer.answer, answer.unit) == (20.0, "m2")


def test_constant_falls_back_to_source_and_type_then_gives_up() -> None:
    golden = [row(1, 3, template="rare"), row(2, "x", type_="text", unit=None, source="ifc_bench")]
    pool = [row(3, 5, template="common"), row(4, 5, template="common"), row(5, 1, template="other")]
    first, second = constant(golden, pool)
    assert (first.answer, first.method) == (5, "constant:source-type")
    assert (second.answer, second.method) == (None, "constant:none")


def test_constant_runs_on_a_selection() -> None:
    rows = list(enumerate(make_questions(), 1))
    params = SelectionParams()
    golden = select(rows, params).items
    answers = constant(golden, annotate(rows, params))
    assert [answer.id for answer in answers] == [item.id for item in golden]
    assert score(golden, answers).overall.accuracy is not None

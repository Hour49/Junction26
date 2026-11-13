"""The sealed 80/20 split: by drawing group, about 20% of each source's questions in eval."""

import pytest

from stoa_eval.families import group_of, source_of
from stoa_eval.models import Question
from stoa_eval.split import eval_groups, group_sizes, split_counts


def many_groups() -> list[Question]:
    """Three sources with groups of 1 to 13 questions each."""
    questions: list[Question] = []
    for source, count in (("cubicasa5k", 200), ("swiss_dwellings", 120), ("ifc_models", 30)):
        for group in range(count):
            for n in range(1 + (group * 7) % 13):
                name = f"b{group}_model_plan-{n % 3}" if source == "ifc_models" else f"plan-{group}"
                questions.append(
                    Question(
                        path=f"data/{source}/{name}.pdf",
                        question=f"How many doors are on floor {n}?",
                        answer=n,
                        unit="count",
                        type="count",
                    )
                )
    return questions


def test_each_source_gets_about_its_share_of_questions() -> None:
    questions = many_groups()
    sealed = eval_groups(group_sizes(questions), 0.2, seed=1)
    for source in ("cubicasa5k", "swiss_dwellings", "ifc_models"):
        mine = [q for q in questions if source_of(q.path) == source]
        held = sum(group_of(q.path) in sealed for q in mine)
        assert held / len(mine) == pytest.approx(0.2, abs=0.02), source


def test_split_is_by_group_and_order_free() -> None:
    questions = many_groups()
    sealed = eval_groups(group_sizes(questions), 0.2, seed=1)
    assert eval_groups(group_sizes(reversed(questions)), 0.2, seed=1) == sealed
    assert eval_groups(group_sizes(questions), 0.2, seed=2) != sealed
    plans = {group_of(q.path) for q in questions if "ifc_models" in q.path}
    assert plans == {f"ifc_models/b{n}" for n in range(30)}  # the plans of one model stay together


def test_edge_cases() -> None:
    one = {"habs": {"habs/a": 10}}
    assert eval_groups(one, 0.2, seed=1) == set()  # a single group stays in dev
    two = {"opening_design": {"opening_design/a": 20, "opening_design/b": 44}}
    assert eval_groups(two, 0.2, seed=1) == {"opening_design/a"}  # at least one, the closer size
    halves = {"src": {"src/a": 50, "src/b": 50}}
    assert len(eval_groups(halves, 0.2, seed=1)) == 1  # both overshoot: one is sealed anyway
    assert eval_groups(two, 0.0, seed=1) == set()
    assert eval_groups(two, 1.0, seed=1) == {"opening_design/a", "opening_design/b"}


def test_split_counts() -> None:
    questions = many_groups()[:30]
    labelled = [(q, "eval" if n % 3 == 0 else "dev") for n, q in enumerate(questions)]
    counts = split_counts(labelled)
    cubicasa = counts["source"]["cubicasa5k"]
    assert (cubicasa.dev_questions, cubicasa.eval_questions) == (20, 10)
    assert cubicasa.eval_share == pytest.approx(1 / 3)
    assert counts["source_type"]["cubicasa5k/count"] == cubicasa

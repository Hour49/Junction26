"""The dev prior: built from dev rows only (mode for counts, median for measures, with the share
it gets right), loaded from its local table, and refused when the table is missing."""

import json
from pathlib import Path

import pytest

from app.adapters.answer_prior import SCHEMA, NoPrior, TablePrior, build, main
from app.composition import build_pipeline
from app.core.answering.model import Prior, Query, Unsupported
from app.core.errors import InvalidInputError
from app.settings import Settings


class WordParser:
    """`window` and `room area` questions; anything else is unsupported."""

    def parse(self, text: str) -> Query | Unsupported:
        if text.startswith("windows"):
            return Query(subject="window")
        if text.startswith("area of"):
            return Query(measure="area", subject="room", name=text.removeprefix("area of "))
        return Unsupported(reason="unknown")


def row(question: str, answer: object, unit: str, source: str = "cubicasa5k") -> dict[str, object]:
    return {"path": f"data/{source}/x.png", "question": question, "answer": answer, "unit": unit}


ROWS = [
    *(row("windows?", n, "count") for n in (4, 4, 4, 5, 7, 2)),
    *(
        row(f"area of {r}", a, "m2", "ifc_models")
        for r, a in enumerate((10.0, 10.1, 12.0, 30.0, 9.9))
    ),
    row("windows?", "four", "count"),  # a text answer
    row("doors?", 3, "count"),  # unsupported
    *(row("windows?", 1, "count", "swiss_dwellings") for _ in range(4)),  # fewer than 5 answers
]


def test_build_keeps_the_mode_of_counts_and_the_median_of_measures_per_source_and_family() -> None:
    table = build(ROWS, WordParser())
    assert table["schema"] == SCHEMA
    assert table["priors"] == {
        "cubicasa5k": {"window": {"value": 4, "unit": "count", "confidence": 0.5, "n": 6}},
        "ifc_models": {
            # median 10.1: right for 10.1 and 10.0; 9.9 is 2.02% off it
            "area:room|name=*": {"value": 10.1, "unit": "m2", "confidence": 0.4, "n": 5}
        },
    }


def test_the_table_prior_answers_a_family_it_has_and_none_otherwise(tmp_path: Path) -> None:
    path = tmp_path / "dev.json"
    path.write_text(json.dumps(build(ROWS, WordParser())), encoding="utf-8")
    prior = TablePrior(path)
    assert prior.prior("cubicasa5k", "window") == Prior(value=4, unit="count", confidence=0.5, n=6)
    assert prior.prior("swiss_dwellings", "window") is None
    assert NoPrior().prior("cubicasa5k", "window") is None


def test_a_missing_table_fails_at_startup_saying_how_to_build_it(tmp_path: Path) -> None:
    with pytest.raises(InvalidInputError, match="ANSWER_PRIOR=none"):
        TablePrior(tmp_path / "dev.json")


def test_the_builder_refuses_any_split_but_dev(tmp_path: Path) -> None:
    sealed = tmp_path / "eval.jsonl"
    sealed.write_text("", encoding="utf-8")
    with pytest.raises(InvalidInputError, match="not the dev split"):
        main([str(sealed), "--out", str(tmp_path / "out.json")])
    assert not (tmp_path / "out.json").exists()


def test_settings_pick_no_prior_by_default_and_the_dev_table_by_name(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)  # so a developer's backend/.env can't change the result
    assert isinstance(build_pipeline(Settings(), tmp_path).prior, NoPrior)
    table = tmp_path / "dev.json"
    table.write_text(json.dumps(build(ROWS, WordParser())), encoding="utf-8")
    monkeypatch.setattr("app.composition.DEV_PRIOR", table)
    monkeypatch.setenv("ANSWER_PRIOR", "dev")
    assert isinstance(build_pipeline(Settings(), tmp_path).prior, TablePrior)

"""scripts/fit_label_boxes.py (PR #349, eu-big's fit #14 c6883029882): seeded halves and the
selection rule, no right area (within 10% of gold) lost on either half."""

import importlib.util
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from app.core.drawing.model import Drawing, Page, Scale


def script() -> ModuleType:
    path = Path(__file__).parents[1] / "scripts" / "fit_label_boxes.py"
    spec = importlib.util.spec_from_file_location("fit_label_boxes", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def row(file: str) -> Any:
    page = Page(page=1, width=100, height=100, unit="px")
    return (Drawing(file=file, pages=(page,), scale=Scale(status="no_scale")), [], {})


def test_label_boxes_right_is_10_percent_and_halves_are_seeded_and_disjoint() -> None:
    fit = script()
    assert fit.RIGHT == 0.10
    rows = [row(f"plan-{n}.pdf") for n in range(10)]
    a, b = fit.halves(rows)
    assert len(a) == len(b) == 5 and {r[0].file for r in a}.isdisjoint({r[0].file for r in b})
    assert fit.halves(list(reversed(rows))) == (a, b)  # the order given does not matter


def test_label_boxes_selects_no_right_area_lost_on_either_half(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    fit = script()

    def counts(rows: Any, side: float, cover: float) -> dict[str, int]:
        n = dict.fromkeys(fit.KEYS, 0)
        n["label"] = round(side * 10 + cover * 10)  # wider guards refuse more labels...
        n["right"] = int(side >= 0.9 and rows is halves[1])  # ...but lose a right one on half B
        return n

    halves = fit.halves([row(f"plan-{n}.pdf") for n in range(4)])
    monkeypatch.setattr(fit, "halves", lambda rows: halves)
    monkeypatch.setattr(fit, "counts", counts)
    assert fit.sweep([]) == (0.7, 0.3)  # 0.9 and 1.2 lose a right area on B
    assert "selected: MIN_SIDE_M 0.70 MIN_COVER 0.30" in capsys.readouterr().out

"""stoa_eval gate (E5): calibration, signals, AUROC, Learn-then-Test, Clopper-Pearson, and the
command on a made-up split with a fake backend."""

import json
from pathlib import Path
from typing import Any

import pytest

from stoa_eval import backend, cli
from stoa_eval.gate import (
    Unit,
    binom_cdf,
    calibrated,
    certificate,
    cp_lower,
    failure_auroc,
    family_gates,
    family_keys,
    halves,
    isotonic,
    learn_then_test,
    min_accepted,
    modal_probability,
    risk_coverage,
    signals_of,
)
from tests.test_ab import fake_backend, question, reply
from tests.test_exp_split import dataset, exp_split, run
from tests.test_extraction_scoring import element, extraction

__all__ = ["dataset"]  # the fixture, used by name


def unit(n: int, exact: bool, value: float | None, family: str = "door") -> Unit:
    return Unit(file=f"data/cubicasa5k/p-{n}.png", family=family, exact=exact,
                signals={"top3": value, "pb_mode": value, "agree": value})  # fmt: skip


def test_isotonic_pools_violators_and_ties() -> None:
    steps = isotonic([(0.1, 0), (0.2, 1), (0.3, 0), (0.4, 1), (0.4, 1)])
    assert steps == [(0.1, 0.0), (0.2, 0.5), (0.4, 1.0)]
    assert calibrated(steps, 0.05) == 0.0  # below the first block: the first block
    assert calibrated(steps, 0.35) == 0.5
    assert calibrated(steps, 0.9) == 1.0
    assert isotonic([(0.5, 1), (0.5, 0)]) == [(0.5, 0.5)]


def test_modal_probability() -> None:
    assert modal_probability([]) == 1.0  # nothing detected: the count is 0 for sure
    assert modal_probability([0.9]) == pytest.approx(0.9)
    assert modal_probability([0.5, 0.5]) == pytest.approx(0.5)
    assert modal_probability([0.9, 0.9]) == pytest.approx(0.81)


def test_failure_auroc() -> None:
    separated = [unit(1, True, 0.9), unit(2, True, 0.8), unit(3, False, 0.1)]
    assert failure_auroc(separated, "top3") == 1.0
    tied = [unit(1, True, 0.5), unit(2, False, 0.5)]
    assert failure_auroc(tied, "top3") == 0.5
    unscored = [unit(1, True, 0.1), unit(2, False, None)]  # no value ranks lowest
    assert failure_auroc(unscored, "top3") == 1.0
    assert failure_auroc([unit(1, True, 0.3)], "top3") is None
    assert failure_auroc([unit(1, True, None), unit(2, False, None)], "top3") is None
    assert risk_coverage([unit(1, True, None)], "top3") == []


def test_binomial_and_clopper_pearson() -> None:
    assert binom_cdf(0, 10, 0.5) == pytest.approx(1 / 1024)
    assert binom_cdf(10, 10, 0.3) == 1.0
    assert cp_lower(9, 10) == pytest.approx(0.6058, abs=1e-4)
    assert cp_lower(59, 59) == pytest.approx(0.05 ** (1 / 59), abs=1e-6)
    assert cp_lower(0, 10) == 0.0
    assert cp_lower(0, 0) is None
    assert min_accepted() == 59  # 0.95^59 < 0.05 <= 0.95^58


def test_ltt_takes_the_loosest_threshold_before_the_first_failure() -> None:
    units = [unit(n, True, n / 100) for n in range(100, 0, -1)]  # 100 right answers
    units += [unit(1000 + n, False, 0.005) for n in range(30)]  # 30 wrong, all least sure
    gate = learn_then_test(units, "top3")
    assert gate.threshold == 0.01 and gate.accepted == 100 and gate.exact == 100
    assert all(step.accepted >= 59 for step in gate.steps)  # the strict end is skipped
    assert gate.steps[-1].threshold == 0.005 and gate.steps[-1].p > 0.05


def test_ltt_stops_at_the_first_failure_even_if_looser_passes() -> None:
    units = [unit(n, True, 1.0) for n in range(60)]
    units += [unit(100 + n, False, 0.9) for n in range(10)]  # fails at 0.9 ...
    units += [unit(200 + n, True, 0.8) for n in range(500)]  # ... though 0.8 would pass
    gate = learn_then_test(units, "top3")
    assert gate.threshold == 1.0 and gate.accepted == 60


def test_ltt_shut_when_nothing_passes() -> None:
    units = [unit(n, n % 2 == 0, 0.5) for n in range(100)]
    gate = learn_then_test(units, "top3")
    assert gate.threshold is None and gate.accepted == 0


def test_signals_of_one_answer() -> None:
    scores = [0.9, 0.8, 0.7, 0.1]
    doors = [
        element(f"d{i}", [0.1, 0.1, 0.2, 0.2], attrs={"score": s}) for i, s in enumerate(scores)
    ]
    found = extraction(elements=doors)
    steps = {"*": [(0.0, 0.5)], "door": [(0.0, 0.1), (0.5, 1.0)]}
    got = signals_of(found, "door", steps, agree=True)
    assert got["top3"] == pytest.approx(0.8)
    assert got["pb_mode"] == pytest.approx(0.9)  # three sure doors, one at 0.1: P(3) = 0.9
    assert got["agree"] == 1.0
    assert signals_of(found, "window", steps, agree=None) == {
        "top3": None, "pb_mode": 1.0, "agree": None
    }  # fmt: skip
    assert signals_of(None, "door", steps, agree=False)["pb_mode"] is None  # missing image
    unscored = extraction(elements=[element("d", [0.1, 0.1, 0.2, 0.2])])
    assert signals_of(unscored, "door", steps, agree=None)["pb_mode"] is None
    assert signals_of(found, "plan", steps, agree=None)["pb_mode"] is None
    assert family_keys("shower+bathtub") == ("shower", "bathtub")
    assert family_keys("sauna") == ("sauna_stove", "room:sauna")


def test_risk_coverage_includes_ties() -> None:
    units = [unit(1, True, 0.9), unit(2, True, 0.5), unit(3, False, 0.5), unit(4, False, None)]
    points = {p.target: p for p in risk_coverage(units, "top3")}
    assert points[0.1].accepted == 1 and points[0.1].exact_rate == 1.0
    assert points[0.5].accepted == 3 and points[0.5].coverage == 0.75  # the tie comes along
    assert points[1.0].accepted == 4 and points[1.0].threshold is None


def test_certificate_has_the_plan_as_unit() -> None:
    units = [unit(1, True, 0.9), unit(1, False, 0.9, "window"), unit(2, True, 0.9),
             unit(3, True, 0.1)]  # fmt: skip
    cert = certificate(units, "top3", {"door": 0.5, "window": 0.5}, "test")
    assert (cert.plans, cert.of_plans, cert.exact_plans) == (2, 3, 1)  # plan 1 has a wrong one
    assert cert.opens == pytest.approx(2 / 3)
    assert "the gate opens on 66.7% of plans" in cert.sentence
    assert "of the plans marked sure, at least" in cert.sentence  # the bound is on plans
    assert "have every sure answer exact (2 plans, 95% bound)" in cert.sentence


def test_halves_are_seeded_and_disjoint() -> None:
    files = [f"data/cubicasa5k/p-{n}.png" for n in range(11)]
    first, second = halves(files, seed=1)
    assert (len(first), len(second)) == (5, 6) and not set(first) & set(second)
    assert halves(reversed(files), seed=1) == (first, second)


def scored_arm(dataset: Path, folder: Path) -> None:
    """Every gold file of the made-up split with a score on each door."""
    folder.mkdir(parents=True)
    for path in (dataset / "gold/cubicasa5k").iterdir():
        body: dict[str, Any] = json.loads(path.read_text())
        for n, item in enumerate(body["elements"]):
            item.setdefault("attrs", {})["score"] = 0.5 + 0.1 * n
        (folder / path.name).write_text(json.dumps(body), "utf-8")


def test_gate_command_val_then_certify_test(
    dataset: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(backend, "run", fake_backend)
    exp = dataset / "exp"
    assert exp_split(dataset, exp) == 0
    scored_arm(dataset, exp / "core" / "a")
    scored_arm(dataset, exp / "core" / "b")
    common = ("--exp-dir", exp, "--gold", dataset / "gold")
    arms = ("--arm", exp / "core/a", "--second", exp / "core/b")
    assert run("gate", *arms, *common) == 0
    val = json.loads((exp / "ab/gate-core-a-val.json").read_text())
    assert val["part"] == "val" and val["second"] == "core-b"
    assert set(val["families"]) == {"door", "window"}
    assert "not a certificate" in val["certificate"]["sentence"]
    assert run("gate", *arms, *common, "--part", "test") == 1
    assert "--certify" in capsys.readouterr().err
    assert run("gate", *arms, *common, "--part", "test", "--certify") == 0
    test = json.loads((exp / "ab/gate-core-a-test.json").read_text())
    assert test["signal"] == val["signal"]
    assert {f: g["threshold"] for f, g in test["families"].items()} == {
        f: g["threshold"] for f, g in val["families"].items()
    }
    assert test["certificate"]["sentence"].startswith("test: of the plans marked sure")
    record = json.loads((exp / "test-certified.json").read_text())["runs"]
    assert [(r["command"], r["arm"], r["reason"]) for r in record] == [("gate", "core-a", None)]
    assert run("gate", *arms, *common, "--part", "test", "--certify") == 1  # test is used once
    assert "already run on test" in capsys.readouterr().err
    again = ("--part", "test", "--certify", "--recertify-reason", "scorer fix")
    assert run("gate", *arms, *common, *again) == 0
    record = json.loads((exp / "test-certified.json").read_text())["runs"]
    assert [r["reason"] for r in record] == [None, "scorer fix"]
    assert run("gate", "--arm", exp / "core/a", *common, *again) == 1
    assert "is not the val gate" in capsys.readouterr().err  # tuned with a second arm


def test_a_refused_answer_is_never_sure() -> None:
    file = "data/cubicasa5k/p-1.png"
    qs = [question(1, file, 0), question(2, "data/cubicasa5k/p-2.png", 0)]
    unread = extraction(file="data/cubicasa5k/p-2.png", read=["window"])  # doors refused
    found = {file: extraction(file=file), unread.file: unread}
    units = cli._units(qs, {1: "door", 2: "door"}, {1: reply(1, 0), 2: reply(2, None)}, None,
                       found, {"*": [(0.0, 0.9)]})  # fmt: skip
    assert units[0].signals["pb_mode"] == 1.0 and units[0].exact
    assert units[1].signals == {"top3": None, "pb_mode": None, "agree": None}


def test_family_gates_split_delta_over_families() -> None:
    """65 right answers pass one family's test at delta 0.05 (59 needed) but not with two
    families, where each gets 0.025 and needs 72."""
    door = [unit(n, True, 0.9) for n in range(65)]
    window = [unit(n, True, 0.9, "window") for n in range(65)]
    assert learn_then_test(door, "top3").threshold == 0.9
    gates = family_gates({"door": door, "window": window}, "top3")
    assert gates["door"].threshold is None and gates["window"].threshold is None
    assert min_accepted(delta=0.025) == 72
    assert family_gates({"door": door}, "top3")["door"].threshold == 0.9

"""stoa_eval gate (E5): calibration, signals, AUROC, Learn-then-Test, Clopper-Pearson, and the
command on a made-up split with a fake backend."""

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from stoa_eval import backend, cli
from stoa_eval.gate import (
    G1MAIN,
    SignalFile,
    UnionStep,
    Unit,
    binom_cdf,
    calibrated,
    certificate,
    cp_lower,
    failure_auroc,
    family_gates,
    family_keys,
    g1main_signal,
    halves,
    isotonic,
    learn_then_test,
    load_gate_policy,
    min_accepted,
    modal_probability,
    nothing_found_rates,
    pooled_gates,
    risk_coverage,
    signals_of,
)
from tests.test_ab import fake_backend, question, reply
from tests.test_exp_split import DOORS, WINDOWS, dataset, exp_split, run
from tests.test_extraction_scoring import element, extraction

__all__ = ["dataset"]  # the fixture, used by name


def unit(n: int, exact: bool, value: float | None, family: str = "door") -> Unit:
    return Unit(file=f"data/cubicasa5k/p-{n}.png", family=family, exact=exact,
                signals={"top3": value, "pb_mode": value, "agree": value,
                         "agree_pb": value})  # fmt: skip


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
    assert got["agree_pb"] == pytest.approx(1.9)  # agree first, then pb_mode within it
    assert signals_of(found, "window", steps, agree=None) == {
        "top3": None, "pb_mode": 1.0, "agree": None, "agree_pb": None
    }  # fmt: skip
    assert signals_of(found, "plan", steps, agree=True)["agree_pb"] == 1.0  # plans: agree alone
    assert signals_of(found, "plan", steps, agree=False)["agree_pb"] == 0.0
    assert signals_of(None, "door", steps, agree=False)["pb_mode"] is None  # missing image
    unscored = extraction(elements=[element("d", [0.1, 0.1, 0.2, 0.2])])
    assert signals_of(unscored, "door", steps, agree=None)["pb_mode"] is None
    assert signals_of(found, "plan", steps, agree=None)["pb_mode"] is None
    assert family_keys("shower+bathtub") == ("shower", "bathtub")
    assert family_keys("sauna") == ("sauna_stove", "room:sauna")


def test_an_answer_with_nothing_found_gets_the_family_rate() -> None:
    """An empty count's modal probability is always 1; the gate uses how often an empty answer
    of that family was right on the calibration half instead."""
    doors = [element("d", [0.1, 0.1, 0.2, 0.2], attrs={"score": 0.9})]
    found = extraction(elements=doors)
    steps = {"*": [(0.0, 0.5)], "door": [(0.0, 1.0)]}
    empty = {"window": 0.2}
    assert signals_of(found, "window", steps, agree=None, empty=empty)["pb_mode"] == 0.2
    assert signals_of(found, "toilet", steps, agree=None, empty=empty)["pb_mode"] == 0.5
    assert signals_of(found, "door", steps, agree=None, empty=empty)["pb_mode"] == 1.0
    preds = {f"data/cubicasa5k/p-{n}.png": extraction(file=f"data/cubicasa5k/p-{n}.png",
                                                      elements=doors if n == 3 else [])
             for n in range(4)}  # fmt: skip
    units = [unit(0, True, None, "window"), unit(1, False, None, "window"),
             unit(2, False, None, "window"), unit(3, True, None, "door"),
             unit(9, True, None, "window"), unit(0, True, None, "plan")]  # fmt: skip
    # p-9 has no extraction: not counted; plans have no items: not counted
    assert nothing_found_rates(units, preds) == {"window": pytest.approx(2 / 5)}


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
    assert "chosen on val, not a guarantee" in val["certificate"]["sentence"]
    assert run("gate", *arms, *common, "--part", "test") == 1
    assert "--certify" in capsys.readouterr().err
    assert run("gate", *arms, *common, "--part", "test", "--certify") == 0
    test = json.loads((exp / "ab/gate-core-a-test.json").read_text())
    assert test["signal"] == val["signal"]
    assert test["empty_rates"] == val["empty_rates"] and val["empty_rates"]  # fit on val only
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
    assert units[1].signals == {"top3": None, "pb_mode": None, "agree": None, "agree_pb": None}


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


def test_a_pooled_group_passes_where_its_families_alone_cannot() -> None:
    """65 plans with a right door and a right window: each family alone needs 72 answers at
    delta 0.025; the group, one threshold with the plan as the unit, needs 59 plans."""
    door = [unit(n, True, 0.9) for n in range(65)]
    window = [unit(n, True, 0.9, "window") for n in range(65)]
    by_family = {"door": door, "window": window}
    assert family_gates(by_family, "top3")["door"].threshold is None
    groups, families, _ = pooled_gates(by_family, {"elements": ("door", "window")}, "top3")
    assert list(groups) == ["elements"] and groups["elements"].families == ["door", "window"]
    gate = groups["elements"]
    assert (gate.threshold, gate.plans, gate.accepted, gate.exact) == (0.9, 65, 65, 65)
    assert families["door"].threshold == families["window"].threshold == 0.9
    assert families["window"].accepted == 65


def test_a_pooled_group_has_the_plan_as_unit() -> None:
    """60 plans, one wrong window: 1 error in 120 answers passes, 1 wrong plan in 60 fails."""
    door = [unit(n, True, 0.9) for n in range(60)]
    window = [unit(n, n != 0, 0.9, "window") for n in range(60)]
    answers = learn_then_test(door + window, "top3")
    assert (answers.threshold, answers.accepted, answers.steps[-1].errors) == (0.9, 120, 1)
    groups, _, _ = pooled_gates({"door": door, "window": window}, {"e": ("door", "window")}, "top3")
    assert groups["e"].threshold is None
    assert (groups["e"].steps[0].accepted, groups["e"].steps[0].errors) == (60, 1)


def test_pooled_gates_do_not_split_delta_over_groups() -> None:
    """Val only chooses: each group (the plan family has no group: its own) is held to the 95%
    bound at the full delta, so 65 right plans (59 needed, 72 at delta / 2) open both."""
    door = [unit(n, True, 0.9) for n in range(65)]
    plan = [unit(n, True, 0.9, "plan") for n in range(65)]
    groups = {"elements": ("door", "window")}
    both, families, _ = pooled_gates({"door": door, "plan": plan}, groups, "top3")
    assert set(both) == {"elements", "plan"} and both["plan"].families == ["plan"]
    assert both["elements"].families == ["door"]
    assert both["elements"].threshold == 0.9 and families["plan"].threshold == 0.9


def test_a_pooled_group_takes_the_loosest_threshold_that_meets_the_target() -> None:
    """80 plans at 0.9 hold 1 wrong one (bound 94.2%: short of 95%); 40 more right plans at 0.8
    bring it to 1 in 120 (bound above 95%); 30 wrong plans at 0.5 fail again. A fixed sequence
    would stop at 0.9 and stay shut; the val choice takes 0.8."""
    door = [unit(n, n != 0, 0.9) for n in range(80)]
    door += [unit(100 + n, True, 0.8) for n in range(40)]
    door += [unit(200 + n, False, 0.5) for n in range(30)]
    groups, families, _ = pooled_gates({"door": door}, {"elements": ("door",)}, "top3")
    gate = groups["elements"]
    assert (gate.threshold, gate.accepted, gate.exact) == (0.8, 120, 119)
    assert [(s.threshold, s.accepted, s.errors) for s in gate.steps] == [
        (0.9, 80, 1), (0.8, 120, 1), (0.5, 150, 31)
    ]  # fmt: skip
    assert families["door"].threshold == 0.8
    assert (cp_lower(79, 80) or 0) < 0.95 <= (cp_lower(119, 120) or 0)  # the bound, as stated


def test_groups_are_tightened_until_all_groups_together_meet_the_target() -> None:
    """Doors: 95 plans, 1 wrong (plan 0, the least sure door); plans: 105 plans, 1 wrong (plan 1).
    Each group alone meets 95%, but together 2 wrong of 105 plans don't. Tightening doors past
    the wrong door removes a wrong plan and loses none (plan 0 stays sure through its plan
    answer); shutting plans would lose 10 plans for 1. So doors move to 0.9 and the union passes."""
    door = [unit(n, n != 0, 0.8 if n == 0 else 0.9) for n in range(95)]
    plan = [unit(n, n != 1, 0.9, "plan") for n in range(105)]
    groups = {"elements": ("door",), "plans": ("plan",)}
    gates, families, steps = pooled_gates({"door": door, "plan": plan}, groups, "top3")
    assert (gates["elements"].alone_threshold, gates["elements"].alone_accepted) == (0.8, 95)
    assert (gates["elements"].threshold, gates["elements"].accepted) == (0.9, 94)
    assert gates["plans"].threshold == gates["plans"].alone_threshold == 0.9
    assert [(s.group, s.threshold, s.plans, s.wrong) for s in steps] == [
        ("elements", 0.9, 105, 1)
    ]  # fmt: skip
    assert families["door"].threshold == 0.9
    assert certificate(door + plan, "top3", {"door": 0.8, "plan": 0.9}, "x").exact_plans == 103
    assert (cp_lower(103, 105) or 0) < 0.95 <= (cp_lower(104, 105) or 0)


def signal_file(
    path: Path, name: str, arm: str | None, values: list[tuple[str, str, float | None]]
) -> Path:
    rows = [{"file": file, "family": family, "value": value} for file, family, value in values]
    body = {"schema": "gate_signal_v1", "name": name, "arm": arm, "values": rows}
    path.write_text(json.dumps(body), "utf-8")
    return path


def test_a_signal_file_adds_its_value_per_answer() -> None:
    file, other = "data/cubicasa5k/p-1.png", "data/cubicasa5k/p-2.png"
    qs = [question(1, file, 0), question(2, other, 0), question(3, file, 0, text="windows?")]
    found = {file: extraction(file=file), other: extraction(file=other)}
    verifier = SignalFile.model_validate(
        {"schema": "gate_signal_v1", "name": "verifier", "arm": None,
         "values": [{"file": file, "family": "door", "value": 0.7},
                    {"file": other, "family": "door", "value": 0.9}]}
    )  # fmt: skip
    replies = {1: reply(1, 0), 2: reply(2, None), 3: reply(3, 0)}
    units = cli._units(qs, {1: "door", 2: "door", 3: "window"}, replies, None, found, {},
                       [verifier])  # fmt: skip
    by = {(u.file, u.family): u.signals["verifier"] for u in units}
    assert by == {(file, "door"): 0.7, (other, "door"): None, (file, "window"): None}
    # p-2's door was refused: never sure, whatever the file says; no value for windows


def test_gate_takes_a_signal_file(
    dataset: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(backend, "run", fake_backend)
    exp = dataset / "exp"
    assert exp_split(dataset, exp) == 0
    scored_arm(dataset, exp / "core" / "a")
    rows = [
        json.loads(line)
        for part in ("val", "test")
        for line in (exp / f"{part}_questions.jsonl").read_text().splitlines()
    ]
    values: list[tuple[str, str, float | None]] = [
        (row["path"], "door" if row["question"] == DOORS else "window", float(row["id"] % 2))
        for row in rows
    ]
    verifier = signal_file(dataset / "v.json", "verifier", "core/a", values)
    common = ("--exp-dir", exp, "--gold", dataset / "gold", "--arm", exp / "core/a")
    assert run("gate", *common, "--signal-file", verifier, "--signal", "verifier") == 0
    assert "| verifier |" in capsys.readouterr().out
    val = json.loads((exp / "ab/gate-core-a-val.json").read_text())
    assert val["signal"] == "verifier" and val["signal_files"] == {"verifier": str(verifier)}
    answers = sum(gate["answers"] for gate in val["families"].values())
    assert val["compared"]["verifier"]["scored"] == answers  # every answer has a value
    assert run("gate", *common, "--part", "test", "--certify") == 1
    assert "give its --signal-file" in capsys.readouterr().err
    assert not (exp / "test-certified.json").exists()  # a refused run records nothing
    certify = ("--part", "test", "--certify", "--signal-file", verifier)
    assert run("gate", *common, *certify) == 0
    assert json.loads((exp / "ab/gate-core-a-test.json").read_text())["signal"] == "verifier"


@pytest.mark.parametrize(
    ("name", "arm", "family", "twice", "reason"),
    [
        ("verifier", "core/b", "door", False, "judges core/b's answers, not core/a's"),
        ("verifier", "core/a", "doors", False, "unknown families ['doors']"),
        ("top3", None, "door", False, "is a built-in signal"),
        ("verifier", None, "door", True, "two values for door on"),
    ],
)
def test_gate_refuses_a_bad_signal_file(
    dataset: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    name: str,
    arm: str | None,
    family: str,
    twice: bool,
    reason: str,
) -> None:
    monkeypatch.setattr(backend, "run", fake_backend)
    exp = dataset / "exp"
    assert exp_split(dataset, exp) == 0
    scored_arm(dataset, exp / "core" / "a")
    file = json.loads((exp / "split.json").read_text())["parts"]["val"]["files"][0]
    values: list[tuple[str, str, float | None]] = [(file, family, 0.5)] * (2 if twice else 1)
    bad = signal_file(dataset / "bad.json", name, arm, values)
    common = ("--exp-dir", exp, "--gold", dataset / "gold", "--arm", exp / "core/a")
    assert run("gate", *common, "--signal-file", bad) == 1
    assert reason in capsys.readouterr().err


def test_gate_refuses_an_unknown_signal_name(
    dataset: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(backend, "run", fake_backend)
    exp = dataset / "exp"
    assert exp_split(dataset, exp) == 0
    scored_arm(dataset, exp / "core" / "a")
    common = ("--exp-dir", exp, "--gold", dataset / "gold", "--arm", exp / "core/a")
    assert run("gate", *common, "--signal", "nope") == 1
    assert (
        "--signal nope: not one of ['top3', 'pb_mode', 'agree', 'agree_pb']"
        in capsys.readouterr().err
    )


def test_gate_pools_families_on_val_and_reuses_the_groups_on_test(
    dataset: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(backend, "run", fake_backend)
    exp = dataset / "exp"
    assert exp_split(dataset, exp) == 0
    scored_arm(dataset, exp / "core" / "a")
    common = ("--exp-dir", exp, "--gold", dataset / "gold", "--arm", exp / "core/a")
    loose = ("--delta", "1")  # every threshold passes (the made-up answers are wrong): it opens
    real = cli.pooled_gates
    step = UnionStep(group="elements", threshold=None, plans=0, wrong=0, p=1.0)

    def with_a_step(*args: Any) -> Any:  # delta 1 never tightens: check that steps are kept
        gates, families, _ = real(*args)
        return gates, families, [step]

    monkeypatch.setattr(cli, "pooled_gates", with_a_step)
    assert run("gate", *common, *loose, "--pool") == 0
    out = capsys.readouterr().out
    assert "| elements | door, window |" in out and "tightened" in out
    val = json.loads((exp / "ab/gate-core-a-val.json").read_text())
    assert val["union_steps"] == [step.model_dump()]
    group = val["groups"]["elements"]
    assert list(val["groups"]) == ["elements"] and group["families"] == ["door", "window"]
    assert val["family_delta"] is None  # groups: delta is not split
    assert group["threshold"] is not None and group["accepted"] > 0
    assert {g["threshold"] for g in val["families"].values()} == {group["threshold"]}
    assert run("gate", *common, *loose, "--part", "test", "--certify", "--pool") == 1
    assert "--pool: val only" in capsys.readouterr().err
    # the test run takes the val file's threshold as it is: set one no score reaches
    path = exp / "ab/gate-core-a-val.json"
    val["groups"]["elements"]["threshold"] = 123.0
    for gate in val["families"].values():
        gate["threshold"] = 123.0
    path.write_text(json.dumps(val), "utf-8")
    assert run("gate", *common, *loose, "--part", "test", "--certify") == 0
    test = json.loads((exp / "ab/gate-core-a-test.json").read_text())
    assert test["groups"]["elements"]["threshold"] == 123.0  # reused, not chosen again
    assert test["groups"]["elements"]["accepted"] == 0 and test["certificate"]["plans"] == 0
    assert test["groups"]["elements"]["families"] == ["door", "window"]
    assert test["family_delta"] is None
    assert {g["threshold"] for g in test["families"].values()} == {123.0}
    assert run("gate", *common, *loose, "--part", "test", "--certify") == 1  # test is used once
    assert "already run on test" in capsys.readouterr().err


def test_gate_policy_round_trips_and_refuses_a_missing_split_sha(
    dataset: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(backend, "run", fake_backend)
    exp = dataset / "exp"
    assert exp_split(dataset, exp) == 0
    scored_arm(dataset, exp / "core" / "a")
    common = ("--exp-dir", exp, "--gold", dataset / "gold", "--arm", exp / "core/a")
    assert run("gate", *common, "--delta", "1", "--pool") == 0  # delta 1: the gate opens
    val_path = exp / "ab/gate-core-a-val.json"
    val = json.loads(val_path.read_text())
    sha = hashlib.sha256((exp / "split.json").read_bytes()).hexdigest()
    assert val["split_sha256"] == sha
    val["families"]["window"]["accepted"] = 0  # open, but no val answer was marked sure
    val_path.write_text(json.dumps(val), "utf-8")
    out = exp / "gate.json"
    assert run("gate-policy", "--gate", val_path, "--out", out) == 0
    made = load_gate_policy(out)
    assert made.model_dump(by_alias=True) == json.loads(out.read_text())  # round trip
    assert made.split_sha256 == sha and made.part == "val" and made.certified is False
    assert list(made.families) == ["door"]  # no evidence for window's threshold: no entry
    door = made.families["door"]
    assert (door.signal, door.threshold, door.group) == (
        val["signal"], val["families"]["door"]["threshold"], "elements"
    )  # fmt: skip
    assert door.val.note == "chosen on val, not a guarantee"
    assert door.val.sure == val["families"]["door"]["accepted"]
    body = json.loads(out.read_text())
    del body["split_sha256"]
    out.write_text(json.dumps(body), "utf-8")
    with pytest.raises(ValueError, match="split_sha256"):
        load_gate_policy(out)
    del val["split_sha256"]  # a gate made before the sha was recorded
    val_path.write_text(json.dumps(val), "utf-8")
    assert run("gate-policy", "--gate", val_path, "--out", out) == 1
    assert "no split_sha256" in capsys.readouterr().err


def test_gate_policy_is_certified_only_by_the_same_gates_test_run(
    dataset: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(backend, "run", fake_backend)
    exp = dataset / "exp"
    assert exp_split(dataset, exp) == 0
    scored_arm(dataset, exp / "core" / "a")
    common = ("--exp-dir", exp, "--gold", dataset / "gold", "--arm", exp / "core/a")
    assert run("gate", *common, "--delta", "1", "--pool") == 0
    assert run("gate", *common, "--delta", "1", "--part", "test", "--certify") == 0
    val_path, test_path = exp / "ab/gate-core-a-val.json", exp / "ab/gate-core-a-test.json"
    out = exp / "gate.json"
    assert run("gate-policy", "--gate", val_path, "--certificate", test_path, "--out", out) == 0
    made = load_gate_policy(out)
    test = json.loads(test_path.read_text())
    assert made.test is not None and made.test.certificate.model_dump() == test["certificate"]
    bound = test["certificate"]["lower_bound"]
    assert made.certified is (bound is not None and bound >= test["target"])
    for low in (0.0, None):  # certified follows the test bound, not the run having happened
        test["certificate"]["lower_bound"] = low
        test_path.write_text(json.dumps(test), "utf-8")
        assert run("gate-policy", "--gate", val_path, "--certificate", test_path, "--out", out) == 0
        assert load_gate_policy(out).certified is (low is not None and low >= test["target"])
    test["certificate"]["lower_bound"] = 1.0
    test_path.write_text(json.dumps(test), "utf-8")
    assert run("gate-policy", "--gate", val_path, "--certificate", test_path, "--out", out) == 0
    assert load_gate_policy(out).certified is True
    for family in test["families"].values():  # another threshold: another gate's test run
        family["threshold"] = 123.0
    test_path.write_text(json.dumps(test), "utf-8")
    assert run("gate-policy", "--gate", val_path, "--certificate", test_path, "--out", out) == 1
    assert "not the test run of the gate" in capsys.readouterr().err
    assert run("gate-policy", "--gate", val_path, "--out", out) == 0
    assert load_gate_policy(out).certified is False and load_gate_policy(out).test is None


def test_g1main_is_gemini_s_probability_for_the_answered_count() -> None:
    file, other = "data/cubicasa5k/p-1.png", "data/cubicasa5k/p-2.png"
    dists = {file: {"door": {3: 0.8, 2: 0.2}}}

    def value(answers: list[object], on: str = file, family: str = "door") -> float | None:
        made = g1main_signal({(on, family): answers}, dists)
        assert made.name == G1MAIN and made.arm is None
        return made.values[0].value

    assert value([3]) == 0.8
    assert value([3.0]) == 0.8  # a whole number read as a float is a count
    assert value([3, 2]) == 0.2  # two questions on the image: sure only when both are
    assert value([5]) == 0.0  # a count Gemini gave no probability
    assert value([2.5]) is None  # not a count: no probability (the backend gives none)
    assert value([True]) is None
    assert value([None]) is None  # refused
    assert value([3], on=other) is None  # no reply for the image
    assert value([3], family="window") is None  # no distribution for the family


def test_built_in_signals_have_no_value_for_a_family_another_arm_answers() -> None:
    file = "data/cubicasa5k/p-1.png"
    scored = [element(f"e{n}", [0.1, 0.1, 0.2, 0.2], cls=cls, attrs={"score": 0.9})
              for n, cls in enumerate(["door", "window"])]  # fmt: skip
    found = {file: extraction(file=file, elements=scored)}
    qs = [question(1, file, 1), question(2, file, 1, text=WINDOWS)]
    fams, replies = {1: "door", 2: "window"}, {1: reply(1, 1), 2: reply(2, 1)}
    plain = {u.family: u.signals["top3"] for u in cli._units(qs, fams, replies, None, found, {})}
    assert plain == {"door": 0.9, "window": 0.9}
    units = cli._units(qs, fams, replies, None, found, {}, own={"window"})
    assert {u.family: u.signals["top3"] for u in units} == {"door": 0.9, "window": None}


def g1main_replies(folder: Path, exp: Path, windows: int) -> Path:
    """Gemini's distributions for every val and test image: 0.5 on any door count; on windows
    0.75 for `windows`, 0.25 for 0."""
    files = [
        file
        for part in ("val", "test")
        for file in json.loads((exp / "split.json").read_text())["parts"][part]["files"]
    ]
    folder.mkdir(parents=True)
    dists = {file: {"door": {str(k): 0.5 for k in range(20)},
                    "window": {"0": 0.25, str(windows): 0.75}} for file in files}  # fmt: skip
    (folder / "dists.json").write_text(json.dumps(dists), "utf-8")
    return folder


def test_gate_answers_a_family_from_another_arm_and_reads_g1main(
    dataset: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """core/a finds no windows (answers 0), core/b finds 7 on every image; windows are routed
    to core/b, so the gate sees 7 windows and Gemini's 0.75 for them, and no top3 there."""
    monkeypatch.setattr(backend, "run", fake_backend)
    exp = dataset / "exp"
    assert exp_split(dataset, exp) == 0
    scored_arm(dataset, exp / "core" / "a")
    windows = exp / "ocr" / "b"
    windows.mkdir(parents=True)
    for path in (dataset / "gold/cubicasa5k").iterdir():
        body: dict[str, Any] = json.loads(path.read_text())
        body["elements"] = [element(f"w{n}", [0.1, 0.1, 0.2, 0.2], cls="window") for n in range(7)]
        (windows / path.name).write_text(json.dumps(body), "utf-8")
    replies = g1main_replies(dataset / "g1", exp, 7)
    seen: list[tuple[dict[int, Any], list[SignalFile], set[str]]] = []
    units = cli._units

    def spy(*args: Any, **kwargs: Any) -> list[Unit]:
        given: list[Any] = list(args)
        extra = given[6] if len(given) > 6 else kwargs.get("extra", ())
        own = given[8] if len(given) > 8 else kwargs.get("own", frozenset())
        seen.append(({k: v.answer for k, v in given[2].items()}, list(extra), set(own)))
        return units(*args, **kwargs)

    monkeypatch.setattr(cli, "_units", spy)
    common = ("--exp-dir", exp, "--gold", dataset / "gold", "--arm", exp / "core/a")
    routed = ("--family-arm", f"window={windows}", "--g1main", replies, "--signal", G1MAIN)
    assert run("gate", *common, *routed) == 0
    assert "Answered by another arm: window = ocr/b" in capsys.readouterr().out
    val_qs = [json.loads(line) for line in (exp / "val_questions.jsonl").read_text().splitlines()]
    window_ids = {q["id"] for q in val_qs if q["question"] == WINDOWS}
    answers, extra, own = seen[-1]
    assert {answers[i] for i in window_ids} == {7}  # core/b's windows, not core/a's 0
    assert own == {"window"}
    g1 = {(v.family, v.value) for v in extra[-1].values}
    assert extra[-1].name == G1MAIN and {value for family, value in g1 if family == "window"} == {
        0.75
    }
    gate_path = exp / "ab/gate-core-a+ocr-b-val.json"
    val = json.loads(gate_path.read_text())
    assert val["arm"] == "core-a+ocr-b" and val["family_arms"] == {"window": "ocr/b"}
    assert val["signal"] == G1MAIN and val["signal_files"] == {G1MAIN: str(replies)}
    assert run("gate-policy", "--gate", gate_path, "--out", dataset / "gate.json") == 0
    assert json.loads((dataset / "gate.json").read_text())["family_arms"] == {"window": "ocr/b"}
    certify = ("--part", "test", "--certify")
    assert run("gate", *common, *certify, "--g1main", replies) == 1  # not routed: another gate
    assert "gate-core-a-val.json" in capsys.readouterr().err
    assert run("gate", *common, *certify, "--family-arm", f"window={windows}") == 1
    assert "give its --signal-file" in capsys.readouterr().err  # g1main needed again
    doors = ("--family-arm", f"door={windows}", "--g1main", replies)
    assert run("gate", *common, *certify, *doors) == 1  # same arms, another family routed
    assert "routed {'window': 'ocr/b'}, not {'door': 'ocr/b'}" in capsys.readouterr().err
    assert run("gate", *common, *certify, *routed[:4]) == 0
    test = json.loads((exp / "ab/gate-core-a+ocr-b-test.json").read_text())
    assert test["family_arms"] == {"window": "ocr/b"} and test["signal"] == G1MAIN


@pytest.mark.parametrize(
    ("extra", "reason"),
    [
        (("--family-arm", "room:*=ocr/b"), "--family-arm room:*: no such family asked"),
        (("--family-arm", "window"), "FAMILY=FOLDER"),
        (("--family-arm", "w*=ocr/b", "--family-arm", "window=core/a"), "window is routed twice"),
        (("--family-arm", "window=ocr/b", "--signal-file", "<arm>"), "can't judge a combination"),
        (("--g1main", "<g1>", "--signal-file", "<g1main>"), "both named g1main"),
        (("--swap", "S1536"), "--swap needs --g1main"),
    ],
)
def test_gate_refuses_a_bad_combination(
    dataset: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    extra: tuple[str, ...],
    reason: str,
) -> None:
    monkeypatch.setattr(backend, "run", fake_backend)
    exp = dataset / "exp"
    assert exp_split(dataset, exp) == 0
    scored_arm(dataset, exp / "core" / "a")
    scored_arm(dataset, exp / "ocr" / "b")
    files = {
        "<arm>": signal_file(dataset / "s.json", "verifier", "core/a", []),
        "<g1main>": signal_file(dataset / "g.json", G1MAIN, None, []),
        "<g1>": g1main_replies(dataset / "g1", exp, 7),
    }
    args = [str(files.get(a, exp / a if "=" not in a and "/" in a else a)) for a in extra]
    args = [a.replace("=ocr/b", f"={exp / 'ocr/b'}").replace("=core/a", f"={exp / 'core/a'}")
            for a in args]  # fmt: skip
    common = ("--exp-dir", exp, "--gold", dataset / "gold", "--arm", exp / "core/a")
    assert run("gate", *common, *args) == 1
    assert reason in capsys.readouterr().err
    assert not list((exp / "ab").glob("gate-*.json")) if (exp / "ab").exists() else True


def test_gate_refit_is_one_command_from_a_runtime_config_to_gate_json(
    dataset: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The detector's val output, the runtime's swap (the fake makes every window 3) and no rooms
    arm: the gate sees the swapped answers, g1main judges them, gate.json says how it was set."""
    monkeypatch.setattr(backend, "run", fake_backend)
    exp = dataset / "exp"
    assert exp_split(dataset, exp) == 0
    scored_arm(dataset, exp / "core" / "a")
    replies = g1main_replies(dataset / "g1", exp, 3)
    seen: list[tuple[dict[int, Any], set[str]]] = []
    units = cli._units

    def spy(*args: Any, **kwargs: Any) -> list[Unit]:
        given: list[Any] = list(args)
        own = given[8] if len(given) > 8 else kwargs.get("own", frozenset())
        seen.append(({k: v.answer for k, v in given[2].items()}, set(own)))
        return units(*args, **kwargs)

    monkeypatch.setattr(cli, "_units", spy)
    out = dataset / "gate.json"
    refit = ("gate-refit", "--detector", exp / "core/a", "--rooms", "none", "--g1main", replies,
             "--exp-dir", exp, "--gold", dataset / "gold", "--out", out)  # fmt: skip
    assert run(*refit) == 0
    printed = capsys.readouterr().out
    assert "Answers after the Decisions swap S1536" in printed
    assert "gate.json was no file" in printed and "now core-a+swap-S1536:" in printed
    val_qs = [json.loads(line) for line in (exp / "val_questions.jsonl").read_text().splitlines()]
    windows = {q["id"] for q in val_qs if q["question"] == WINDOWS}
    answers, own = seen[-1]
    assert {answers[i] for i in windows} == {3}  # the swap's answers, not the detector's 0
    assert own == {"door", "window"}  # the detector's built-in signals don't judge swapped answers
    val = json.loads((exp / "ab/gate-core-a+swap-S1536-val.json").read_text())
    assert val["swap"] == "S1536" and val["signal"] == G1MAIN and val["groups"]
    made = json.loads(out.read_text())
    assert made["arm"] == "core-a+swap-S1536" and made["swap"] == "S1536"
    assert made["family_arms"] == {} and made["certified"] is False
    assert run(*refit) == 0
    assert "gate.json was core-a+swap-S1536:" in capsys.readouterr().out
    certify = ("--part", "test", "--certify", "--g1main", replies, "--signal", G1MAIN)
    common = ("--exp-dir", exp, "--gold", dataset / "gold", "--arm", exp / "core/a")
    assert run("gate", *common, *certify) == 1  # no swap: another arm's val gate
    assert "gate-core-a-val.json" in capsys.readouterr().err
    assert run("gate", *common, *certify, "--swap", "S1536") == 0
    assert json.loads((exp / "ab/gate-core-a+swap-S1536-test.json").read_text())["swap"] == "S1536"

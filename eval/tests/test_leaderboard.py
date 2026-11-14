"""stoa_eval leaderboard: finding arms, the family policy, failure judges, the cache, the files."""

import json
from pathlib import Path

import pytest

from stoa_eval import backend, cli
from stoa_eval.ab import ArmResult, Rate
from stoa_eval.leaderboard import (
    TAGS_BEGIN,
    TAGS_END,
    ArmRun,
    PolicyEntry,
    eligible,
    family_judges,
    family_policies,
    family_policy,
    find_arms,
    kept_block,
    oracle_reason,
)
from stoa_eval.models import NumberedQuestion
from tests.test_ab import fake_backend
from tests.test_exp_split import DOORS, dataset, exp_split, run

__all__ = ["dataset"]  # the fixture, used by name


def arm_run(name: str, hits: dict[int, bool], family_rates: dict[str, float], covered: int = 10):
    rates = {f: Rate(hits=0, n=0, rate=r) for f, r in family_rates.items()}
    result = ArmResult(
        name=name, source=name, images=10, missing_images=10 - covered,
        overall=Rate(hits=0, n=0, rate=None), by_family=rates, by_style={},
        by_orientation=None, counts=None, worst=[],
    )  # fmt: skip
    return ArmRun(key=name, name=name, result=result, hits=hits, refused=[], modified="-")


def door_questions() -> list[NumberedQuestion]:
    return [
        NumberedQuestion(
            id=i,
            path=f"data/cubicasa5k/p-{i}.png",
            question=DOORS,
            answer=1,
            unit="count",
            type="count",
        )
        for i in range(1, 41)
    ]


def test_find_arms_reads_content_and_skips_raw_and_results(tmp_path: Path) -> None:
    for folder, body in {
        "core/a": {"schema": "extraction_v1", "file": "data/cubicasa5k/x.png"},
        "core/_raw": {"schema": "extraction_v1"},
        "core/raw": {"file": "x", "detections": []},
        "ab/cache": {"schema": "extraction_v1"},
        "photo/hard/b": {"file": "data/cubicasa5k/x.png", "pages": []},
    }.items():
        (tmp_path / folder).mkdir(parents=True)
        (tmp_path / folder / "x.json").write_text(json.dumps(body))
    assert [p.relative_to(tmp_path).as_posix() for p in find_arms(tmp_path)] == [
        "core/a", "photo/hard/b"
    ]  # fmt: skip


def test_family_policy_needs_an_interval_above_zero() -> None:
    questions = door_questions()
    families = {q.id: "door" for q in questions}
    prior = arm_run("prior", {q.id: q.id % 4 == 0 for q in questions}, {"door": 0.25})
    strong = arm_run("core/a", {q.id: True for q in questions}, {"door": 1.0})
    weak = arm_run("core/b", {q.id: q.id % 4 == 0 or q.id == 1 for q in questions}, {"door": 0.275})
    folders = {"core/a": "data/stoa/exp/core/a", "core/b": "data/stoa/exp/core/b"}
    policy = family_policy(questions, families, [weak, strong], prior, folders, seed=1, reps=500)
    assert policy["door"].source == "data/stoa/exp/core/a"
    assert (policy["door"].ci_low or 0.0) > 0
    alone = family_policy(questions, families, [weak], prior, folders, seed=1, reps=500)
    assert alone["door"].source == "prior"  # 1 more right of 40: the interval reaches 0
    assert alone["window"].source == "prior" and alone["window"].questions == 0


def test_family_policy_names_the_golden_folder_of_its_pick(tmp_path: Path) -> None:
    questions = door_questions()
    families = {q.id: "door" for q in questions}
    prior = arm_run("prior", {q.id: q.id % 4 == 0 for q in questions}, {"door": 0.25})
    strong = arm_run("core/a", {q.id: True for q in questions}, {"door": 1.0})
    folders = {"core/a": "data/stoa/exp/core/a"}
    golden = {"core/a": "data/stoa/exp/core/a-golden"}
    policy = family_policy(questions, families, [strong], prior, folders, 1, 200, golden)
    assert policy["door"].golden == "data/stoa/exp/core/a-golden"
    assert policy["window"].golden is None  # the prior needs no folder
    for name, files in (("core/a-golden", ["x.json"]), ("core/b-golden", []), ("core/c", [])):
        (tmp_path / name).mkdir(parents=True)
        for file in files:
            (tmp_path / name / file).write_text("{}")
    found = cli._golden_folders(tmp_path, ["core/a", "core/b", "core/c"])
    assert found == {"core/a": (tmp_path / "core/a-golden").resolve().as_posix()}  # b: empty


def test_family_judges_skip_unread_families_and_smoke_runs() -> None:
    reads = arm_run("ocr/a", {}, {"door": 0.0, "room:bedroom": 0.7})
    smoke = arm_run("seg/smoke", {}, {"door": 0.9}, covered=2)
    best = arm_run("core/b", {}, {"door": 0.4})
    worse = arm_run("core/a", {}, {"door": 0.3})
    judges = family_judges([reads, smoke, best, worse])
    assert [r.name for r in judges["door"]] == ["core/b"]  # one per track, the best
    assert [r.name for r in judges["room:bedroom"]] == ["ocr/a"]


def test_kept_block() -> None:
    text = f"x\n{TAGS_BEGIN}\nmy tags\n{TAGS_END}\n"
    assert kept_block(text).strip() == "my tags"
    assert kept_block("no markers") == ""


def test_leaderboard_command_caches_and_writes_policy(
    dataset: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    calls: list[str] = []

    def counting(*args: str) -> None:
        calls.append(args[0])
        fake_backend(*args)

    monkeypatch.setattr(backend, "run", counting)
    exp = dataset / "exp"
    assert exp_split(dataset, exp) == 0
    arm = exp / "core" / "copy"
    arm.mkdir(parents=True)
    for path in (dataset / "gold/cubicasa5k").iterdir():
        (arm / path.name).write_text(path.read_text(), "utf-8")
    bad = exp / "ocr" / "bad"
    bad.mkdir(parents=True)
    (bad / "x.json").write_text(json.dumps({"schema": "extraction_v1", "file": "data/x/y.png"}))
    out = dataset / "leaderboard.md"
    argv = ("leaderboard", "--exp-dir", exp, "--gold", dataset / "gold", "--prior",
            dataset / "prior.json", "--out", out, "--reps", 100)  # fmt: skip
    assert run(*argv) == 0
    text = out.read_text()
    assert "| core/copy | 5/5 |" in text
    assert "ocr/bad: not valid extraction_v1" in text
    policy = json.loads((exp / "policy.json").read_text())
    assert policy["part"] == "val" and set(policy["families"]) >= {"door", "window", "plan"}
    assert set(policy["families_any_arm"]["families"]) == set(policy["families"])
    assert "The same rule over the arms that have golden v2 output" in text
    first = calls.count("answer")
    assert first == 3  # prior, gold, core/copy
    out.write_text(text.replace("(failure tags not written yet)", "tags by hand"))
    assert run(*argv) == 0
    assert calls.count("answer") == first  # every arm came from the cache
    assert "tags by hand" in out.read_text()  # the hand-written block is kept


@pytest.mark.parametrize("name", ["cvx/A-oracle", "areas/D2-goldrooms", "region/oracle-gold"])
def test_oracle_arms_are_never_picked(name: str) -> None:
    """Arms that read gold at answer time: "oracle" or "gold" in the path (areas/D2-goldrooms
    answers from the gold rooms, .agents/exp/areas.md)."""
    questions = door_questions()
    families = {q.id: "door" for q in questions}
    prior = arm_run("prior", {q.id: q.id % 4 == 0 for q in questions}, {"door": 0.25})
    oracle = arm_run(name, {q.id: True for q in questions}, {"door": 1.0})
    folders = {name: f"data/stoa/exp/{name}"}
    policy = family_policy(questions, families, [oracle], prior, folders, seed=1, reps=200)
    assert policy["door"].source == "prior"
    assert family_judges([oracle])["door"] == []
    assert eligible(arm_run("detector/C-yolo26s-golden", {}, {}))  # run on golden v2 files


def test_the_shipped_policy_takes_only_arms_with_golden_output() -> None:
    """core/a is best on val but has no golden folder: the pipeline can't run it, so `families`
    takes core/b (golden output, still above the prior); `families_any_arm` keeps core/a."""
    questions = door_questions()
    families = {q.id: "door" for q in questions}
    prior = arm_run("prior", {q.id: q.id % 4 == 0 for q in questions}, {"door": 0.25})
    best = arm_run("core/a", {q.id: True for q in questions}, {"door": 1.0})
    ready = arm_run("core/b", {q.id: q.id % 10 != 0 for q in questions}, {"door": 0.9})
    folders = {"core/a": "data/stoa/exp/core/a", "core/b": "data/stoa/exp/core/b"}
    golden = {"core/b": "data/stoa/exp/core/b-golden"}
    shipped, any_arm = family_policies(
        questions, families, [best, ready], prior, folders, 1, 200, golden
    )
    assert (shipped["door"].arm, shipped["door"].golden) == ("core/b", golden["core/b"])
    assert (any_arm["door"].arm, any_arm["door"].golden) == ("core/a", None)


def test_oracle_reason_from_a_marker_the_deny_list_or_the_name(tmp_path: Path) -> None:
    exp = tmp_path / "exp"
    for name in ("areas/rooms", "cvx/raw/a", "ocr/G2-reg", "ocr/G2", "region/oracle-gold",
                 "detector/C-golden"):  # fmt: skip
        (exp / name).mkdir(parents=True)
    (exp / "areas/rooms/ORACLE").write_text("rooms are\nthe gold rooms\n")
    (exp / "cvx/raw/ORACLE").write_text("gold exemplars")  # a parent marks every arm below it
    (exp / "ORACLE").write_text("the exp dir itself is no arm: not read")
    deny = {"ocr/*-reg": "golden's annotated region (gold)"}

    def why(name: str) -> str | None:
        return oracle_reason(name, exp / name, exp, deny)

    assert why("areas/rooms") == "ORACLE file in areas/rooms: rooms are the gold rooms"
    assert why("cvx/raw/a") == "ORACLE file in cvx/raw: gold exemplars"
    assert why("ocr/G2-reg") == "oracles.json ocr/*-reg: golden's annotated region (gold)"
    assert why("region/oracle-gold") == 'its path says "oracle" or "gold"'
    assert why("ocr/G2") is None and why("detector/C-golden") is None
    assert not eligible(arm_run("ocr/G2-reg", {}, {}).model_copy(update={"oracle": "x"}))


def test_leaderboard_never_picks_a_marked_or_listed_oracle(
    dataset: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Two copies of the gold (the best possible arms): one marked by an ORACLE file, one
    matched by oracles.json. Neither may answer any family."""
    monkeypatch.setattr(backend, "run", fake_backend)
    exp = dataset / "exp"
    assert exp_split(dataset, exp) == 0
    for name in ("areas/rooms", "ocr/G2-reg"):
        (exp / name).mkdir(parents=True)
        for path in (dataset / "gold/cubicasa5k").iterdir():
            (exp / name / path.name).write_text(path.read_text(), "utf-8")
    (exp / "areas/rooms/ORACLE").write_text("rooms are the gold rooms")
    deny = {"schema": "oracle_arms_v1", "arms": {"ocr/*-reg": "gold annotated region"}}
    (exp / "oracles.json").write_text(json.dumps(deny))
    out = dataset / "leaderboard.md"
    argv = ("leaderboard", "--exp-dir", exp, "--gold", dataset / "gold", "--prior",
            dataset / "prior.json", "--out", out, "--reps", 100)  # fmt: skip
    assert run(*argv) == 0
    policy = json.loads((exp / "policy.json").read_text())
    picked = {
        e["arm"] for part in (policy, policy["families_any_arm"]) for e in part["families"].values()
    }
    assert picked == {None}  # the prior everywhere
    assert policy["oracles_never_picked"] == {
        "areas/rooms": "ORACLE file in areas/rooms: rooms are the gold rooms",
        "ocr/G2-reg": "oracles.json ocr/*-reg: gold annotated region",
    }
    summary = json.loads((exp / "ab/leaderboard.json").read_text())
    assert summary["combo"] == "prior" or "areas/rooms" not in summary["combo"]
    assert "ocr/G2-reg" not in summary["combo"] and summary["family_combo"] == {}
    assert "never picked: ORACLE file in areas/rooms" in out.read_text()


def test_policy_json_families_is_the_shipped_pick(
    dataset: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`families` (what ANSWER_POLICY reads) gets the golden-ready pick, `families_any_arm` the
    other; the scorer here answers nothing right, so the two picks are stubbed."""
    monkeypatch.setattr(backend, "run", fake_backend)
    exp = dataset / "exp"
    assert exp_split(dataset, exp) == 0
    arm = exp / "core" / "copy"
    arm.mkdir(parents=True)
    for path in (dataset / "gold/cubicasa5k").iterdir():
        (arm / path.name).write_text(path.read_text(), "utf-8")
    prior = PolicyEntry(source="prior", arm=None, questions=5, val_exact=0.5, prior_exact=0.5,
                        diff=None, ci_low=None, ci_high=None)  # fmt: skip
    picked = prior.model_copy(update={"source": "data/stoa/exp/core/copy", "arm": "core/copy"})
    monkeypatch.setattr(cli, "family_policies", lambda *_: ({"door": prior}, {"door": picked}))
    argv = ("leaderboard", "--exp-dir", exp, "--gold", dataset / "gold", "--prior",
            dataset / "prior.json", "--out", dataset / "lb.md", "--reps", 50)  # fmt: skip
    assert run(*argv) == 0
    policy = json.loads((exp / "policy.json").read_text())
    assert policy["families"]["door"]["source"] == "prior"
    assert policy["families_any_arm"]["families"]["door"]["arm"] == "core/copy"
    summary = json.loads((exp / "ab/leaderboard.json").read_text())
    assert summary["family_combo"] == {} and summary["family_combo_any_arm"] == {
        "door": "core/copy"
    }

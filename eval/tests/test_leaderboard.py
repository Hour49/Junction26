"""stoa_eval leaderboard: finding arms, the family policy, failure judges, the cache, the files."""

import json
from pathlib import Path

import pytest

from stoa_eval import backend
from stoa_eval.ab import ArmResult, Rate
from stoa_eval.leaderboard import (
    TAGS_BEGIN,
    TAGS_END,
    ArmRun,
    family_judges,
    family_policy,
    find_arms,
    kept_block,
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
    first = calls.count("answer")
    assert first == 3  # prior, gold, core/copy
    out.write_text(text.replace("(failure tags not written yet)", "tags by hand"))
    assert run(*argv) == 0
    assert calls.count("answer") == first  # every arm came from the cache
    assert "tags by hand" in out.read_text()  # the hand-written block is kept


def test_oracle_arms_are_never_picked() -> None:
    questions = door_questions()
    families = {q.id: "door" for q in questions}
    prior = arm_run("prior", {q.id: q.id % 4 == 0 for q in questions}, {"door": 0.25})
    oracle = arm_run("cvx/A-oracle", {q.id: True for q in questions}, {"door": 1.0})
    folders = {"cvx/A-oracle": "data/stoa/exp/cvx/A-oracle"}
    policy = family_policy(questions, families, [oracle], prior, folders, seed=1, reps=200)
    assert policy["door"].source == "prior"
    assert family_judges([oracle])["door"] == []

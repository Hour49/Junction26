"""The experiment split: CubiCasa dev images only, golden v2 left out, groups whole, stable."""

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from stoa_eval.cli import main
from stoa_eval.exp_split import EXP_PARTS, ExpSplit, assign_parts, check_dev_only
from stoa_eval.families import group_of
from stoa_eval.models import Question
from tests.factories import write_questions
from tests.test_extraction_scoring import element, extraction

DOORS = "How many doors are shown on this floor plan?"
WINDOWS = "How many windows are shown on this floor plan?"


def run(*argv: object) -> int:
    return main([str(arg) for arg in argv])


def plan_files() -> list[str]:
    """60 single sheets and one project of three sheets (one group)."""
    singles = [f"data/cubicasa5k/plan-{n}.png" for n in range(60)]
    return [*singles, *(f"data/cubicasa5k/proj/sheet-{n}.png" for n in range(3))]


@pytest.fixture
def dataset(tmp_path: Path) -> Path:
    """A sealed split over CubiCasa and swiss questions, gold for every CubiCasa file, and a golden
    v2 that lists one dev and one eval CubiCasa file."""
    rows: list[Question] = []
    for n, file in enumerate(plan_files()):
        for text in (DOORS, WINDOWS):
            rows.append(Question(path=file, question=text, answer=n, unit="count", type="count"))
    swiss = "data/swiss_dwellings/a.pdf"
    rows.append(Question(path=swiss, question=DOORS, answer=1, unit="count", type="count"))
    questions = write_questions(tmp_path / "questions.jsonl", rows)
    assert run("split", "--questions", questions, "--out-dir", tmp_path / "split") == 0
    sealed = set(json.loads((tmp_path / "split/manifest.json").read_text())["eval_groups"])
    gold = tmp_path / "gold/cubicasa5k"
    gold.mkdir(parents=True)
    for n, file in enumerate(plan_files()):
        split = "eval" if group_of(file) in sealed else "dev"
        doors = [element(f"e{i}", [0.1, 0.1, 0.2, 0.2]) for i in range(n % 3)]
        made = extraction(file=file, split=split, elements=doors)
        name = file.removeprefix("data/cubicasa5k/").replace("/", "__")
        (gold / f"{name}.json").write_text(made.model_dump_json(by_alias=True), "utf-8")
    dev = [file for file in plan_files() if group_of(file) not in sealed and "proj" not in file]
    held = [file for file in plan_files() if group_of(file) in sealed]
    part1 = tmp_path / "v2/part1_extraction"
    part1.mkdir(parents=True)
    listed = [{"file": dev[0], "split": "dev"}, {"file": held[0], "split": "eval"}]
    (part1 / "files.jsonl").write_text(
        "".join(
            json.dumps(
                {
                    **row,
                    "source": "cubicasa5k",
                    "truth": "elements",
                    "stratum": "1",
                    "scale_case": None,
                }
            )
            + "\n"
            for row in listed
        ),
        "utf-8",
    )
    (tmp_path / "v2/manifest.json").write_text("{}", "utf-8")
    return tmp_path


def exp_split(dataset: Path, out: Path, *extra: object) -> int:
    return run(
        "exp-split", "--split-dir", dataset / "split", "--golden-dir", dataset / "v2",
        "--gold", dataset / "gold", "--out-dir", out, *extra,
    )  # fmt: skip


def digests(folder: Path) -> dict[str, str]:
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(folder.iterdir())}


def test_parts_are_dev_only_whole_groups_and_stable(dataset: Path) -> None:
    assert exp_split(dataset, dataset / "a") == 0
    assert exp_split(dataset, dataset / "b") == 0
    assert digests(dataset / "a") == digests(dataset / "b")  # a rerun gives the same files
    split = ExpSplit.model_validate_json((dataset / "a/split.json").read_text())
    sealed = set(json.loads((dataset / "split/manifest.json").read_text())["eval_groups"])
    golden = [json.loads(line)["file"] for line in (dataset / "v2/part1_extraction/files.jsonl")
              .read_text().splitlines()]  # fmt: skip
    part_of = split.part_of()
    assert golden[0] in split.excluded_golden
    assert not set(golden) & set(part_of)
    assert not {group_of(file) for file in part_of} & sealed
    assert all(file.startswith("data/cubicasa5k/") for file in part_of)
    groups: dict[str, set[str]] = {}
    for file, part in part_of.items():
        groups.setdefault(group_of(file), set()).add(part)
    assert all(len(parts) == 1 for parts in groups.values())  # no group spans two parts
    proj = {part_of[file] for file in part_of if "/proj/" in file}
    assert len(proj) <= 1
    dev_rows = [json.loads(line) for line in (dataset / "split/dev.jsonl").read_text().splitlines()]
    for name in EXP_PARTS:
        rows = [json.loads(line) for line in (dataset / f"a/{name}_questions.jsonl").open()]
        assert {row["path"] for row in rows} == set(split.parts[name].files)
        assert all(row in dev_rows for row in rows)  # the dev lines, ids included
        assert split.parts[name].questions == len(rows)
        golds: list[dict[str, Any]] = [
            json.loads(p.read_text()) for p in (dataset / "gold/cubicasa5k").iterdir()
        ]
        doors = sum(len(g["elements"]) for g in golds if g["file"] in set(split.parts[name].files))
        assert split.parts[name].elements.get("door", 0) == doors
        assert split.parts[name].plans == split.parts[name].images
    sizes = {name: split.parts[name].groups for name in EXP_PARTS}
    total = sum(sizes.values())
    assert sizes["val"] == round(0.1 * total) and sizes["test"] == round(0.1 * total)


def test_gold_marked_eval_is_refused(dataset: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert exp_split(dataset, dataset / "a") == 0
    file = (
        ExpSplit.model_validate_json((dataset / "a/split.json").read_text()).parts["val"].files[0]
    )
    name = file.removeprefix("data/cubicasa5k/").replace("/", "__")
    path = dataset / "gold/cubicasa5k" / f"{name}.json"
    path.write_text(path.read_text().replace('"split":"dev"', '"split":"eval"'), "utf-8")
    assert exp_split(dataset, dataset / "b") == 1
    assert "not a dev file" in capsys.readouterr().err


def test_assign_parts_is_seeded_and_order_free() -> None:
    groups = [f"cubicasa5k/plan-{n}" for n in range(100)]
    parts = assign_parts(groups, seed=3)
    assert parts == assign_parts(reversed(groups), seed=3)
    assert parts != assign_parts(groups, seed=4)
    counts = {name: sum(part == name for part in parts.values()) for name in EXP_PARTS}
    assert counts == {"train": 80, "val": 10, "test": 10}


def test_check_dev_only_refuses_eval_and_golden() -> None:
    gold = {"data/cubicasa5k/a.png": "dev", "data/cubicasa5k/b.png": "dev"}
    check_dev_only(gold, set(), set(), gold)
    with pytest.raises(ValueError, match="sealed eval"):
        check_dev_only(gold, {"cubicasa5k/a"}, set(), gold)
    with pytest.raises(ValueError, match="golden v2"):
        check_dev_only(gold, set(), {"data/cubicasa5k/b.png"}, gold)
    with pytest.raises(ValueError, match="not a dev file"):
        check_dev_only(gold, set(), set(), {"data/cubicasa5k/a.png": "dev"})

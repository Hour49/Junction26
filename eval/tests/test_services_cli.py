"""`stoa_eval services-gen` and `services-score` with the backend replaced by the hand graph."""

import json
from pathlib import Path
from typing import Any

import pytest

from stoa_eval import backend, cli

from .test_services import _graph


def _fake_backend(*args: str, script: Path = backend.SCRIPT) -> None:
    assert script == backend.SERVICES_SCRIPT
    command = dict(zip(args[1::2], args[2::2], strict=True))
    if "broken" in command["--ifc"]:
        raise ValueError("the backend answerer failed: parse error")
    out = Path(command["--out"])
    out.parent.mkdir(parents=True, exist_ok=True)
    body = _graph().model_dump(by_alias=True) | {"model": Path(command["--ifc"]).stem}
    out.write_text(json.dumps(body), "utf-8")


def _setup(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    monkeypatch.setattr(backend, "run", _fake_backend)
    for stem in ("tower_ventilation", "hub_heating", "tower_broken"):
        (tmp_path / f"{stem}.ifc").write_text("ISO-10303-21;")
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"dev": ["tower"], "heldout": ["hub"]}))
    return manifest, tmp_path / "out"


def test_gen_writes_questions_of_both_splits_and_an_oracle_and_skips_a_broken_model(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    manifest, out = _setup(tmp_path, monkeypatch)
    ifcs = [
        str(tmp_path / f"{s}.ifc") for s in ("tower_ventilation", "hub_heating", "tower_broken")
    ]
    assert cli.main(["services-gen", *ifcs, "--manifest", str(manifest), "--out", str(out)]) == 0
    rows = [json.loads(line) for line in (out / "questions.jsonl").read_text().splitlines()]
    assert {(r["model"], r["split"]) for r in rows} == {
        ("tower_ventilation", "dev"), ("hub_heating", "heldout")
    }  # fmt: skip
    assert len((out / "oracle.jsonl").read_text().splitlines()) == len(rows)
    assert (out / "graphs/tower_ventilation.json").is_file()
    assert "skipped tower_broken" in capsys.readouterr().out


def test_score_records_aggregates_and_keeps_heldout_for_milestones(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest, out = _setup(tmp_path, monkeypatch)
    ifcs = [str(tmp_path / f"{s}.ifc") for s in ("tower_ventilation", "hub_heating")]
    cli.main(["services-gen", *ifcs, "--manifest", str(manifest), "--out", str(out)])
    results = tmp_path / "results"
    q, oracle = str(out / "questions.jsonl"), str(out / "oracle.jsonl")
    common = ["--results", str(results), "--name", "oracle"]
    assert cli.main(["services-score", q, oracle, *common]) == 0
    (record,) = results.glob("*.json")
    body: dict[str, Any] = json.loads(record.read_text())
    assert body["split"] == "dev"
    assert body["report"]["overall"]["rate"] == 1.0
    assert "tower" not in record.read_text() and "AHU" not in record.read_text()
    assert cli.main(["services-score", q, oracle, "--split", "heldout"]) == 1
    assert cli.main(["services-score", q, oracle, "--split", "heldout", "--milestone"]) == 0

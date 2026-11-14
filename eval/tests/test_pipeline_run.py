"""pipeline-run.sh's export: a setting may name a path (`RASTER_COMPONENTS=...rooms=exp:ocr/G4`),
and the export sees the repo's data/ next to its backend/, where the backend's defaults look. Run
on a copy of the script in a throwaway git repo, with a `uv` that stops it after the export."""

import hashlib
import os
import shutil
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "pipeline-run.sh"


def git(repo: Path, *args: str) -> str:
    command = ["git", "-C", str(repo), *args]
    return subprocess.run(command, check=True, capture_output=True, text=True).stdout.strip()


def test_a_setting_may_name_a_path_and_the_export_sees_the_repos_data(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    (repo / "eval").mkdir(parents=True)
    (repo / "backend").mkdir()
    (repo / "data" / "models").mkdir(parents=True)
    shutil.copy(SCRIPT, repo / "eval" / "pipeline-run.sh")
    (repo / "backend" / "app.py").write_text("")
    (repo / "eval" / "results" / "gate").mkdir(parents=True)
    (repo / "eval" / "results" / "gate" / "gate.json").write_text("{}")
    git(repo, "init", "-q")
    git(repo, "add", "eval", "backend")
    git(repo, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "c")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (bin_dir / "uv").write_text("#!/bin/sh\nexit 3\n")  # stops the run after the export
    (bin_dir / "uv").chmod(0o755)
    env = {**os.environ, "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}"}

    done = subprocess.run(
        ["bash", str(repo / "eval" / "pipeline-run.sh"), "HEAD", "ANSWER_PRIOR=dev",
         "RASTER_COMPONENTS=elements=region:C,plans=region:C,rooms=exp:ocr/G4-golden"],
        env=env, capture_output=True, text=True,
    )  # fmt: skip
    assert "not NAME=VALUE" not in done.stderr
    (work,) = (repo / "data" / "stoa" / "runs").iterdir()
    link = work / "export" / "data"
    assert link.is_symlink() and link.resolve() == (repo / "data").resolve()
    assert (work / "export" / "backend" / "app.py").is_file()
    # GATE_POLICY=../eval/results/gate/... (tools/qa-env.sh) resolves in the export too
    assert (work / "export" / "eval" / "results" / "gate" / "gate.json").is_file()

    refused = subprocess.run(
        ["bash", str(repo / "eval" / "pipeline-run.sh"), "HEAD", "no-equals-sign"],
        env=env, capture_output=True, text=True,
    )  # fmt: skip
    assert refused.returncode == 2 and "not NAME=VALUE" in refused.stderr


RECORD = Path(__file__).resolve().parents[1] / "pipeline-record.sh"
RAW = "elements=region:C,plans=region:C,rooms=exp:ocr/G4-golden"


def recorded(tmp_path: Path, settings: list[str], *args: str, note: str = "") -> list[str]:
    """pipeline-record.sh on a run folder, with a `uv` that writes down what it was asked."""
    work = tmp_path / "work"
    (work / "out").mkdir(parents=True)
    (work / "settings.txt").write_text("".join(f"{line}\n" for line in settings))
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    calls = tmp_path / "calls"
    (bin_dir / "uv").write_text(f'#!/bin/sh\nprintf "%s\\n" "$@" "--" >> {calls}\n')
    (bin_dir / "uv").chmod(0o755)
    env = {**os.environ, "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}"}
    if note:
        env["PIPELINE_NOTE"] = note
    done = subprocess.run(
        ["bash", str(RECORD), str(work), "abc1234", *args],
        env=env, capture_output=True, text=True,
    )  # fmt: skip
    assert done.returncode == 0, done.stderr
    return calls.read_text().splitlines()


def test_a_setting_the_public_record_refuses_is_kept_as_its_hash(tmp_path: Path) -> None:
    calls = recorded(
        tmp_path,
        ["answer_prior=dev", f"raster_components={RAW}", "region_model_dir=../data/models/r"],
        "ANSWER_PRIOR=dev",
        f"RASTER_COMPONENTS={RAW}",
        note="Rooms are precomputed.",
    )
    digest = hashlib.sha256(RAW.encode()).hexdigest()[:12]
    settings = [calls[n + 1] for n, arg in enumerate(calls) if arg == "--setting"]
    assert (
        settings
        == 2
        * [  # score-extraction and score, the same settings
            "answer_prior=dev",
            f"raster_components=sha256:{digest}",
            f"region_model_dir=sha256:{hashlib.sha256(b'../data/models/r').hexdigest()[:12]}",
        ]
    )
    notes = [calls[n + 1] for n, arg in enumerate(calls) if arg == "--note"]
    assert notes == 2 * [f"given: ANSWER_PRIOR=dev RASTER_COMPONENTS={RAW}. Rooms are precomputed."]
    assert calls.count("--commit") == 2 and "abc1234" in calls


def test_a_note_with_an_absolute_or_home_path_is_refused(tmp_path: Path) -> None:
    for given in ("CREDIT_DATASET=/home/<user>/data", "X=~/data"):
        with pytest.raises(AssertionError, match="path"):
            recorded(tmp_path / given[:1], ["x=1"], given)

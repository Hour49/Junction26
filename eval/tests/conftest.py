"""Shared fixtures; the made-up data lives in tests/factories.py."""

from pathlib import Path

import pytest

from stoa_eval import cli
from tests.factories import make_questions, write_questions


@pytest.fixture(autouse=True)
def history_in_tmp(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Every run is recorded by default: keep tests out of the tracked eval/results/runs/ and the
    real data/stoa/golden/runs/."""
    monkeypatch.setattr(cli, "RESULTS", tmp_path / "default-results")
    monkeypatch.setattr(cli, "RUNS_DIR", tmp_path / "default-runs")
    return tmp_path / "default-results"


@pytest.fixture
def questions_file(tmp_path: Path) -> Path:
    return write_questions(tmp_path / "questions.jsonl", make_questions())

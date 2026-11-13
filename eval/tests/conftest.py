"""Shared fixtures; the made-up data lives in tests/factories.py."""

from pathlib import Path

import pytest

from tests.factories import make_questions, write_questions


@pytest.fixture
def questions_file(tmp_path: Path) -> Path:
    return write_questions(tmp_path / "questions.jsonl", make_questions())

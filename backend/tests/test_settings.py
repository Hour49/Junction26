from pathlib import Path

import pytest
from pydantic import ValidationError

from app.settings import Settings

ENV_EXAMPLE = Path(__file__).parent.parent / ".env.example"


def test_env_example_lists_exactly_the_settings() -> None:
    lines = [line.strip() for line in ENV_EXAMPLE.read_text().splitlines()]
    keys = {line.split("=", 1)[0] for line in lines if line and not line.startswith("#")}
    assert keys == {name.upper() for name in Settings.model_fields}


def test_valid_value_is_accepted(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    assert Settings().log_level == "DEBUG"


def test_invalid_value_fails_at_startup_naming_the_variable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("LOG_LEVEL", "LOUD")
    with pytest.raises(ValidationError, match="log_level"):
        Settings()

"""The composition root: settings pick the adapter of each port, and a wrong name fails at
startup naming the variable."""

from pathlib import Path
from typing import get_args

import pytest
from pydantic import ValidationError

from app.adapters.hello import HelloExtractor, HelloParser, HelloSecondCounter
from app.composition import build_pipeline
from app.core.pipeline.model import Route
from app.settings import Settings


def test_default_settings_wire_the_hello_world_adapters(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)  # so a developer's backend/.env can't change the result
    pipeline = build_pipeline(Settings(), tmp_path)
    assert set(pipeline.extractors) == set(get_args(Route))
    assert all(isinstance(found, HelloExtractor) for found in pipeline.extractors.values())
    assert isinstance(pipeline.second_counter, HelloSecondCounter)
    assert isinstance(pipeline.parser, HelloParser)
    assert pipeline.clock() <= pipeline.clock()


@pytest.mark.parametrize("variable", ["EXTRACTOR_VECTOR", "SECOND_COUNTER", "QUESTION_PARSER"])
def test_an_unknown_adapter_name_fails_naming_the_variable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, variable: str
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv(variable, "magic")
    with pytest.raises(ValidationError, match=variable.lower()):
        Settings()

"""The composition root: settings pick the adapter of each port, and a wrong name fails at
startup naming the variable."""

from pathlib import Path
from typing import get_args

import pytest
from pydantic import ValidationError

from app.adapters.hello import HelloExtractor, HelloSecondCounter
from app.adapters.question_templates import TemplateParser
from app.adapters.vector_pdf import PdfSecondCounter, PdfVectorExtractor
from app.composition import build_pipeline
from app.core.pipeline.model import Route
from app.settings import Settings


def test_default_settings_wire_the_pdf_reader_on_the_vector_route_and_hello_elsewhere(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)  # so a developer's backend/.env can't change the result
    pipeline = build_pipeline(Settings(), tmp_path)
    assert set(pipeline.extractors) == set(get_args(Route))
    assert isinstance(pipeline.extractors["vector"], PdfVectorExtractor)
    assert all(
        isinstance(found, HelloExtractor)
        for route, found in pipeline.extractors.items()
        if route != "vector"
    )
    assert isinstance(pipeline.second_counter, PdfSecondCounter)
    assert isinstance(pipeline.parser, TemplateParser)
    assert pipeline.clock() <= pipeline.clock()


def test_the_hello_extractor_stays_selectable_on_the_vector_route(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("EXTRACTOR_VECTOR", "hello")
    assert isinstance(build_pipeline(Settings(), tmp_path).extractors["vector"], HelloExtractor)


def test_the_hello_second_counter_stays_selectable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SECOND_COUNTER", "hello")
    assert isinstance(build_pipeline(Settings(), tmp_path).second_counter, HelloSecondCounter)


@pytest.mark.parametrize("variable", ["EXTRACTOR_VECTOR", "SECOND_COUNTER", "QUESTION_PARSER"])
def test_an_unknown_adapter_name_fails_naming_the_variable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, variable: str
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv(variable, "magic")
    with pytest.raises(ValidationError, match=variable.lower()):
        Settings()

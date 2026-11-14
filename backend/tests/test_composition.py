"""The composition root: settings pick the adapter of each port, and a wrong name fails at
startup naming the variable."""

from pathlib import Path
from typing import get_args

import pytest
from pydantic import ValidationError

from app.adapters.dataset_files import DatasetSheetModels
from app.adapters.hello import HelloExtractor, HelloSecondCounter, HelloSourceFinder
from app.adapters.ifc_model import IfcModelExtractor, IfcSecondCounter
from app.adapters.pdf_tables import PdfTables
from app.adapters.pdf_tables.schedule_check import ScheduleTagCounter
from app.adapters.question_templates import TemplateParser
from app.adapters.vector_pdf import PdfSecondCounter, PdfVectorExtractor
from app.composition import build_pipeline
from app.core.pipeline.model import Route
from app.settings import Settings


def test_default_settings_wire_the_real_readers_and_hello_on_the_cad_and_raster_routes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)  # so a developer's backend/.env can't change the result
    pipeline = build_pipeline(Settings(), tmp_path)
    assert set(pipeline.extractors) == set(get_args(Route))
    vector = pipeline.extractors["vector"]  # with the schedules (TABLES=pdf) read around it
    assert isinstance(vector, PdfTables)
    assert isinstance(vector._inner, PdfVectorExtractor)  # pyright: ignore[reportPrivateUsage]
    assert isinstance(pipeline.extractors["bim"], IfcModelExtractor)
    assert isinstance(pipeline.extractors["cad"], HelloExtractor)
    assert isinstance(pipeline.extractors["raster"], HelloExtractor)
    counter = pipeline.second_counter  # with the door schedule vs plan tags check around it
    assert isinstance(counter, ScheduleTagCounter)
    assert isinstance(counter._inner, IfcSecondCounter)  # pyright: ignore[reportPrivateUsage]
    # The model route reads models, so a plan sheet is paired with the model next to it.
    assert isinstance(pipeline.finder, DatasetSheetModels)
    assert isinstance(pipeline.parser, TemplateParser)
    assert pipeline.clock() <= pipeline.clock()


def test_without_the_ifc_reader_no_sheet_is_paired_with_a_model(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("EXTRACTOR_BIM", "hello")
    monkeypatch.setenv("TABLES", "off")  # the vector reader itself, without the schedules
    pipeline = build_pipeline(Settings(), tmp_path)
    assert isinstance(pipeline.extractors["bim"], HelloExtractor)
    # Pairing follows the extractor alone: the second counter is still the ifc one.
    assert isinstance(pipeline.finder, HelloSourceFinder)
    assert isinstance(pipeline.second_counter, IfcSecondCounter)
    assert isinstance(pipeline.extractors["vector"], PdfVectorExtractor)  # the others stay


def test_the_pdf_second_counter_stays_selectable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SECOND_COUNTER", "pdf")
    monkeypatch.setenv("TABLES", "off")  # the counter itself, without the schedule check
    pipeline = build_pipeline(Settings(), tmp_path)
    assert isinstance(pipeline.second_counter, PdfSecondCounter)
    assert isinstance(pipeline.finder, DatasetSheetModels)


def test_the_hello_extractor_stays_selectable_on_the_vector_route(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("EXTRACTOR_VECTOR", "hello")
    monkeypatch.setenv("TABLES", "off")  # the vector reader itself, without the schedules
    assert isinstance(build_pipeline(Settings(), tmp_path).extractors["vector"], HelloExtractor)


def test_the_hello_second_counter_stays_selectable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SECOND_COUNTER", "hello")
    monkeypatch.setenv("TABLES", "off")  # the counter itself, without the schedule check
    assert isinstance(build_pipeline(Settings(), tmp_path).second_counter, HelloSecondCounter)


@pytest.mark.parametrize("variable", ["EXTRACTOR_VECTOR", "SECOND_COUNTER", "QUESTION_PARSER"])
def test_an_unknown_adapter_name_fails_naming_the_variable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, variable: str
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv(variable, "magic")
    with pytest.raises(ValidationError, match=variable.lower()):
        Settings()

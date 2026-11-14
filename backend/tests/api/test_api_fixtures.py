"""The contract's examples: every file in tests/fixtures/api_v1/ is valid for its response or
request model and lists every field, and docs/API.md quotes each one as it is. The frontend uses
the same files as mock data. Regenerate them with tests/api/make_fixtures.py."""

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from pydantic import BaseModel, TypeAdapter

from app.api.ask import AnswerView, AskRequest
from app.api.drawings import DrawingView
from app.api.info import Info
from app.api.projects import ProjectList, ProjectReview, Started
from app.api.takeoff import SignOffRequest, Takeoff
from app.api.views import ErrorBody, ProjectTrace, ProjectView, TraceView
from app.core.review.model import Edit

FIXTURES = Path(__file__).parents[1] / "fixtures" / "api_v1"
DOC = Path(__file__).parents[3] / "docs" / "API.md"
MODELS: dict[str, type[BaseModel] | TypeAdapter[Any]] = {
    "info": Info,
    "project_started": Started,
    "project": ProjectView,
    "project_list": ProjectList,
    "trace": TraceView,
    "project_trace": ProjectTrace,
    "project_review": ProjectReview,
    "drawing": DrawingView,
    "ask_request": AskRequest,
    "answer": AnswerView,
    "answer_confidence": AnswerView,
    "answer_refused": AnswerView,
    "answer_area": AnswerView,
    "answer_model": AnswerView,
    "answer_conflict": AnswerView,
    "answer_signed": AnswerView,
    "answer_schedule": AnswerView,
    "takeoff_edited": Takeoff,
    "error_not_allowed": ErrorBody,
    "trace_set_aside": TraceView,
    "project_running": ProjectView,
    "project_failed": ProjectView,
    "takeoff": Takeoff,
    "review_requests": TypeAdapter(list[Edit]),
    "signoff_request": SignOffRequest,
    "error": ErrorBody,
}
QUOTE = re.compile(r"<!-- fixture: (\w+)\.json -->\n```json\n(.*?)```\n", re.DOTALL)


def test_every_fixture_has_a_model_and_every_model_a_fixture() -> None:
    assert {path.stem for path in FIXTURES.glob("*.json")} == set(MODELS)


@pytest.mark.parametrize("name", sorted(MODELS))
def test_a_fixture_is_valid_and_complete_for_its_model(name: str) -> None:
    body = json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))
    model = MODELS[name]
    if isinstance(model, TypeAdapter):
        for item in model.validate_python(body):
            assert item.model_dump(mode="json", exclude_unset=True) in body
        return
    parsed = model.model_validate(body)  # an unknown field fails here: the models forbid them
    assert parsed.model_dump(mode="json", by_alias=True, exclude_unset=True) == body


def test_the_doc_quotes_every_fixture_as_it_is() -> None:
    quoted = QUOTE.findall(DOC.read_text(encoding="utf-8"))
    assert sorted(name for name, _ in quoted) == sorted(MODELS)
    for name, block in quoted:
        assert block == (FIXTURES / f"{name}.json").read_text(encoding="utf-8"), name


# make_fixtures.responses() as JSON, in a fresh interpreter (the hash seed is per process)
RESPONSES = (
    "import json, logging, sys; logging.disable(logging.INFO); sys.path.insert(0, 'tests/api');"
    "import make_fixtures; print(json.dumps(make_fixtures.responses()))"
)


@pytest.fixture(scope="module")
def runs() -> list[str]:
    """Two runs under different hash seeds (dict and set order) and clocks."""
    backend = Path(__file__).parents[2]
    return [
        subprocess.run(
            [sys.executable, "-c", RESPONSES],
            cwd=backend,
            env={**os.environ, "PYTHONHASHSEED": seed},
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        for seed in ("1", "2")
    ]


def test_make_fixtures_gives_the_same_files_on_every_run(runs: list[str]) -> None:
    """A regenerated fixture's diff is a real change."""
    assert json.loads(runs[0]) == json.loads(runs[1])
    assert runs[0] == runs[1]


def test_the_fixtures_are_what_make_fixtures_gives_today(runs: list[str]) -> None:
    """A fixture left stale after the API or the pipeline changed fails here: rerun
    tests/api/make_fixtures.py --doc."""
    made = json.loads(runs[0])
    assert sorted(made) == sorted(MODELS)
    for name, value in made.items():
        on_disk = json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))
        assert on_disk == value, f"{name}.json is stale"

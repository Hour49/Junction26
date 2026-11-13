"""Shared test setup.

Tests marked `live` call a real outside service: they cost money and flake, so they are skipped
unless RUN_LIVE_TESTS=1 is set, and CI never sets it. Everything else runs offline against fakes.
"""

import os
from pathlib import Path

import pytest
from fastapi import FastAPI

from app.main import create_app
from app.settings import Settings

LIVE_FLAG = "RUN_LIVE_TESTS"


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    if os.environ.get(LIVE_FLAG) == "1":
        return
    skip = pytest.mark.skip(reason=f"live test: set {LIVE_FLAG}=1 to call the real service")
    for item in items:
        if "live" in item.keywords:
            item.add_marker(skip)


@pytest.fixture
def app(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> FastAPI:
    monkeypatch.chdir(tmp_path)  # so a developer's backend/.env can't change test results
    return create_app(Settings())

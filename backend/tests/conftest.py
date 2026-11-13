"""Shared test setup.

Tests marked `live` call a real outside service: they cost money and flake, so they are skipped
unless RUN_LIVE_TESTS=1 is set, and CI never sets it. Everything else runs offline against fakes.
"""

import io
import os
from collections.abc import Callable
from pathlib import Path

import pypdfium2
import pytest
from fastapi import FastAPI
from PIL import Image

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


@pytest.fixture
def make_png() -> Callable[[int, int], bytes]:
    """A blank PNG of the given width and height in pixels: synthetic, never partner data."""

    def make(width: int, height: int) -> bytes:
        buffer = io.BytesIO()
        Image.new("RGB", (width, height), "white").save(buffer, "PNG")
        return buffer.getvalue()

    return make


@pytest.fixture
def make_pdf() -> Callable[..., bytes]:
    """A PDF with one blank page per (width, height) in points."""

    def make(*sizes: tuple[float, float]) -> bytes:
        document = pypdfium2.PdfDocument.new()
        try:
            for width, height in sizes:
                document.new_page(width, height)
            buffer = io.BytesIO()
            document.save(buffer)
        finally:
            document.close()
        return buffer.getvalue()

    return make

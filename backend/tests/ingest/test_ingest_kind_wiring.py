"""DECISIONS_KIND in build_ingest: off by default (no call, the plain probe), and when on, the
sheet-kind signal's line is in the identify trace and part of the reuse key. Offline: the
reader is replaced, no key is used."""

import io
from pathlib import Path

import pytest
from PIL import Image

import app.composition as composition
from app.adapters.decisions_kind import KindUnavailable
from app.composition import build_ingest
from app.settings import Settings


def drawing_png() -> bytes:
    image = Image.new("RGB", (400, 300), "white")
    image.paste((0, 0, 0), (50, 50, 350, 60))
    buffer = io.BytesIO()
    image.save(buffer, "PNG")
    return buffer.getvalue()


class Down:
    """A sheet-kind reader whose service is down."""

    calls = 0

    def __init__(self, *args: object) -> None:
        pass

    def read(self, data: bytes) -> KindUnavailable:
        Down.calls += 1
        return KindUnavailable("kind signal not available: HTTP 503")


def identify(settings: Settings, root: Path) -> tuple[str, str, dict[str, str]]:
    ingest = build_ingest(settings, root, background=False)
    status = ingest.status(ingest.start("plan.png", drawing_png()))
    (file,) = status.files
    stage = next(s for s in ingest.trace(status.id, file.id).stages if s.stage == "identify")
    ingest.close()
    return str(file.kind), stage.did, status.readers


def test_the_sheet_kind_signal_is_off_by_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(composition, "KindReader", Down)
    Down.calls = 0
    settings = Settings(_env_file=None)  # pyright: ignore[reportCallIssue]
    assert settings.decisions_kind is False
    kind, did, readers = identify(settings, tmp_path / "projects")
    assert (kind, Down.calls, readers["decisions_kind"]) == ("png_plan", 0, "False")
    assert "kind signal" not in did


def test_when_on_an_outage_keeps_the_probe_s_kind_and_says_so(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(composition, "KindReader", Down)
    Down.calls = 0
    settings = Settings(
        _env_file=None,  # pyright: ignore[reportCallIssue]
        decisions_kind=True,
        gemini_api_key="test-key",  # pyright: ignore[reportArgumentType]
    )
    kind, did, readers = identify(settings, tmp_path / "projects")
    assert (kind, Down.calls, readers["decisions_kind"]) == ("png_plan", 1, "True")
    assert did.endswith("; kind signal not available: HTTP 503")

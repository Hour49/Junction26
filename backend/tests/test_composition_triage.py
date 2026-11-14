"""TRIAGE_CLASSIFIER=siglip wiring (app/composition.py `_triage`): it builds the SigLIP2 classifier,
with the sheet-kind reader only when DECISIONS_KIND is on; the default stays off and the probe is
built as before; a missing model fails at start naming the variable."""

from pathlib import Path
from typing import Any

import pytest

from app.adapters.archive import FileProbe
from app.adapters.decisions.client import DecisionsClient
from app.adapters.decisions_kind import KindReader
from app.adapters.decisions_kind.probe import KindProbe
from app.adapters.triage.rules import RulesClassifier
from app.adapters.triage.siglip import MODEL_DIR, SiglipClassifier
from app.composition import _probe, _triage  # pyright: ignore[reportPrivateUsage]
from app.core.errors import InvalidInputError, NotFoundError
from app.settings import Settings


@pytest.fixture
def loaded(monkeypatch: pytest.MonkeyPatch) -> list[Any]:
    """Replaces the model load (the folder is local only); records the kind reader it was given."""
    kinds: list[Any] = []

    def from_folder(folder: Path = MODEL_DIR, kind: Any = None) -> object:
        kinds.append(kind)
        return "siglip"

    monkeypatch.setattr(SiglipClassifier, "from_folder", from_folder)
    return kinds


def test_off_by_default_no_triage_and_the_probe_is_the_plain_one(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, loaded: list[Any]
) -> None:
    monkeypatch.chdir(tmp_path)  # so a developer's backend/.env can't change the result
    settings = Settings()
    assert settings.triage_classifier == "off"
    assert _triage(settings) is None
    assert type(_probe(settings)) is FileProbe
    assert _triage(settings.model_copy(update={"decisions_kind": True})) is None
    assert loaded == []  # off never loads the model


def test_siglip_without_decisions_kind_reads_no_kind_signal(loaded: list[Any]) -> None:
    steps = _triage(Settings(triage_classifier="siglip"))
    assert steps is not None
    assert steps.classifier == "siglip"
    assert steps.name == "classifier=siglip, describer=off, judge=off"
    assert loaded == [None]


def test_siglip_with_decisions_kind_gets_the_probes_reader_and_cache(
    tmp_path: Path, loaded: list[Any]
) -> None:
    settings = Settings(
        triage_classifier="siglip",
        decisions_kind=True,
        gemini_api_key="g",  # pyright: ignore[reportArgumentType]
        decisions_cache_dir=tmp_path / "decisions",
    )
    steps = _triage(settings)
    assert steps is not None and steps.classifier == "siglip"
    (kind,) = loaded
    assert isinstance(kind, KindReader)
    assert isinstance(kind._decider, DecisionsClient)  # pyright: ignore[reportPrivateUsage]
    probe = _probe(settings)
    assert isinstance(probe, KindProbe)
    # one cache folder, so the classifier's read of an upload the probe asked about is a cache hit
    assert probe._reader._cache == kind._cache == tmp_path / "decisions"  # pyright: ignore[reportPrivateUsage]


def test_the_rules_classifier_is_unchanged(loaded: list[Any]) -> None:
    steps = _triage(Settings(triage_classifier="rules", triage_judge="rules"))
    assert steps is not None and isinstance(steps.classifier, RulesClassifier)
    assert loaded == []


def test_a_missing_model_fails_at_start_naming_the_variable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def missing(folder: Path = MODEL_DIR, kind: Any = None) -> SiglipClassifier:
        raise NotFoundError(f"{folder}/manifest.json is missing")

    monkeypatch.setattr(SiglipClassifier, "from_folder", missing)
    with pytest.raises(InvalidInputError, match=r"TRIAGE_CLASSIFIER=siglip: .*manifest\.json"):
        _triage(Settings(triage_classifier="siglip"))


@pytest.mark.skipif(not (MODEL_DIR / "manifest.json").is_file(), reason="local model absent")
def test_with_the_local_model_the_real_classifier_is_built() -> None:
    steps = _triage(Settings(triage_classifier="siglip"))
    assert steps is not None and isinstance(steps.classifier, SiglipClassifier)

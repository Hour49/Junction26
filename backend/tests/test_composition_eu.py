"""EU provider per Gemini step (ROOMS_PROVIDER, DECISIONS_PROVIDER, KIND_PROVIDER): "eu" builds
the open-model adapter behind the same port, the default stays Gemini, and no key fails at start."""

import pytest

from app.adapters.decisions.client import DecisionsClient
from app.adapters.decisions_kind.probe import KindProbe
from app.adapters.openvlm.decider import OpenVlmDecider
from app.adapters.openvlm.rooms import OpenVlmRoomExtractor
from app.adapters.raster_ocr.gemini import GeminiRoomExtractor
from app.composition import (  # pyright: ignore[reportPrivateUsage]
    _gemini_rooms,
    _probe,
    decisions_reader,
)
from app.core.errors import InvalidInputError
from app.settings import Settings

KEYS = {"gemini_api_key": "g", "eu_vlm_api_key": "e"}


class Files:
    def read(self, path: str) -> bytes:
        return b""


def test_each_step_uses_gemini_unless_set_to_eu() -> None:
    gemini = Settings(**KEYS, decisions_kind=True)  # pyright: ignore[reportArgumentType]
    assert isinstance(decisions_reader(gemini)._decider, DecisionsClient)  # pyright: ignore[reportPrivateUsage]
    assert isinstance(_gemini_rooms(gemini, Files()), GeminiRoomExtractor)
    eu = Settings(**KEYS, decisions_kind=True, rooms_provider="eu", decisions_provider="eu",  # pyright: ignore[reportArgumentType]
                  kind_provider="eu")  # fmt: skip
    decider = decisions_reader(eu)._decider  # pyright: ignore[reportPrivateUsage]
    assert isinstance(decider, OpenVlmDecider) and decider.model.endswith("-joint")
    assert isinstance(_gemini_rooms(eu, Files()), OpenVlmRoomExtractor)
    probe = _probe(eu)
    assert isinstance(probe, KindProbe)
    assert isinstance(probe._reader._decider, OpenVlmDecider)  # pyright: ignore[reportPrivateUsage]


def test_an_eu_step_without_the_key_fails_at_start() -> None:
    with pytest.raises(InvalidInputError, match="EU_VLM_API_KEY"):
        decisions_reader(Settings(decisions_provider="eu"))

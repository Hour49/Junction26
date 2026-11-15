"""Sheet.discipline: read from the sheet-kind reply's kind, title and number, with no new call.
A display hint only: the decision and confidence are the reply's as before. A fake reply."""

import io
import json
import urllib.request
from pathlib import Path
from typing import cast, get_args

import pytest
from pydantic import SecretStr
from test_sheet_kind import CUT, PLAN, PNG_PROBED, form, png, reply

from app.adapters.raster_ocr.gemini import GeminiError
from app.adapters.triage.sheet_kind import (
    CONTRACTS,
    DISCIPLINE,
    PROMPT,
    PROMPT_SHA,
    RULES,
    SCHEMA,
    VERSION,
    Contract,
    SheetKindClassifier,
    SheetReply,
    form_of,
    request_body,
    sheet_of,
)
from app.composition import _sheet_kind_reader  # pyright: ignore[reportPrivateUsage]
from app.core.discipline import sheet_discipline
from app.core.ifc_facts import Discipline
from app.core.ingest.model import Classified
from app.settings import Settings

MAIN_SHA = "707beba5467d3b42d3ecdc02612e23030994334433c4f84d0bb5569f0b4da166"  # sheet-kind-2


@pytest.mark.parametrize(
    ("found", "discipline"),
    [
        (form("architectural_floor_plan", True, True, 0.97), "architecture"),
        (form("structural_plan", False, False, 0.9, sheet_number="S-201"), "structural"),
        # the title names a service the kind does not: the title wins
        (form("architectural_floor_plan", True, True, 0.9, title="HEATING PLAN"), "heating"),
        (form("mep_plan", False, True, 0.98, title="VENTILATION LAYOUT"), "ventilation"),
        # an MEP plan whose title names no service (a level only) says nothing
        (form("mep_plan", False, True, 0.98, title="LEVEL 2", sheet_number="M-101A"), None),
        # "piping" is a weak word: plumbing or heating, so on an MEP plan it names no service
        (form("mep_plan", False, True, 0.98, title="PIPING PLAN", sheet_number="M-101A"), None),
        (form("schedule_or_text", False, False, 0.95), None),
    ],
)
def test_the_sheet_discipline_comes_from_the_reply(found: dict, discipline: str | None) -> None:
    sheet = sheet_of(SheetReply(found, 0.0, "fake", "fake"), png(), CUT)
    assert sheet.discipline == discipline
    assert sheet.confidence == found["confidence"]


# --- SHEET_DISCIPLINE=gemini: the reply's own field (prompt sheet-kind-3), cross-checked ---------


def test_the_default_asks_and_caches_exactly_as_before() -> None:
    """SHEET_DISCIPLINE=rules (the default) is sheet-kind-2 byte for byte: the same prompt, schema
    and hash, so the demo's cached replies and the golden run do not move."""
    assert Settings(_env_file=None).sheet_discipline == "rules"  # pyright: ignore[reportCallIssue]
    assert CONTRACTS["rules"] is RULES
    assert (RULES.version, RULES.prompt, RULES.schema) == (VERSION, PROMPT, SCHEMA)
    assert RULES.sha == PROMPT_SHA == MAIN_SHA
    body = request_body(b"\xff\xd8jpeg")
    assert body["contents"][0]["parts"][1]["text"] == PROMPT
    assert body["generationConfig"]["responseSchema"] is SCHEMA
    assert "discipline" not in SCHEMA["properties"] and "discipline" not in PROMPT


def test_the_gemini_contract_is_the_measured_one() -> None:
    # the prompt and schema of the A/B (.agents/exp/pics-pic-cls.md, runs 1 and 2)
    assert CONTRACTS["gemini"] is DISCIPLINE
    assert DISCIPLINE.sha == "3d6f4c28280ed915617668ae51afa4d914875ecbc8409d4ce3df59d2c95297ba"
    assert DISCIPLINE.version == "sheet-kind-3"
    field = DISCIPLINE.schema["properties"]["discipline"]
    assert field == {"type": "STRING", "enum": list(get_args(Discipline))}
    for key in ("required", "propertyOrdering"):
        names = DISCIPLINE.schema[key]
        assert names[names.index("sheet_kind") + 1] == "discipline"
        assert [n for n in names if n != "discipline"] == SCHEMA[key]
    for name in get_args(Discipline):
        assert f"{name} (" in DISCIPLINE.prompt  # each discipline has its one-line definition
    assert DISCIPLINE.prompt.startswith(PROMPT.split("- discipline")[0].split("- sheet_kind")[0])


@pytest.mark.parametrize("discipline", [None, "hvac"])
def test_a_reply_without_a_known_discipline_is_not_the_gemini_form(
    discipline: str | None,
) -> None:
    bad = form("mep_plan", False, True, 0.98)
    if discipline is not None:
        bad["discipline"] = discipline
    with pytest.raises(GeminiError):
        form_of(reply(bad), DISCIPLINE)
    if discipline is None:
        assert form_of(reply(bad)) == bad  # the default contract asks no discipline


@pytest.mark.parametrize(
    ("found", "discipline"),
    [
        # the model's field, not the kind: a floor-plan-looking sheet with ducts drawn over it
        # ("Store Expansion Floor Plan", an M-2 sheet; the title names no service)
        (PLAN | {"title": "Store Expansion Floor Plan", "discipline": "ventilation"},
         "ventilation"),
        (form("mep_plan", False, True, 0.98, title="LEVEL 2", discipline="heating"), "heating"),
        (form("structural_plan", False, False, 0.9, sheet_number="S-201", discipline="structural"),
         "structural"),
        # the title or number names another discipline than the model: unsure
        (form("mep_plan", False, True, 0.98, title="HEATING PLAN", discipline="plumbing"), None),
        (PLAN | {"sheet_number": "E-101", "discipline": "architecture"}, None),
        # a weak word ("PIPING") or a service room never vetoes the model
        (form("mep_plan", False, True, 0.98, title="PIPING PLAN", discipline="heating"), "heating"),
        (PLAN | {"title": "ELECTRICAL ROOM LAYOUT", "discipline": "architecture"}, "architecture"),
        (form("schedule_or_text", False, False, 0.95, discipline="other"), "other"),
    ],
)  # fmt: skip
def test_with_gemini_the_sheet_discipline_is_the_models_cross_checked(
    found: dict, discipline: str | None
) -> None:
    sheet = sheet_of(SheetReply(found, 0.0, "fake", "fake", DISCIPLINE), png(), CUT)
    assert sheet.discipline == discipline
    assert sheet.decision == sheet_of(SheetReply(found, 0.0, "f", "f"), png(), CUT).decision


def test_a_title_naming_two_services_vetoes_only_a_third() -> None:
    assert sheet_discipline("ventilation", "HEATING AND VENTILATION PLAN", None) == "ventilation"
    assert sheet_discipline("plumbing", "HEATING AND VENTILATION PLAN", None) is None
    assert sheet_discipline("plumbing", None, None) == "plumbing"


@pytest.mark.parametrize(("setting", "contract"), [("rules", RULES), ("gemini", DISCIPLINE)])
def test_the_setting_picks_what_is_asked_and_cached(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, setting: str, contract: Contract
) -> None:
    sent: list[dict] = []
    answer = form("mep_plan", False, True, 0.98, title="LEVEL 2", discipline="heating")

    def urlopen(request: urllib.request.Request, timeout: float) -> io.BytesIO:
        sent.append(json.loads(cast(bytes, request.data)))
        return io.BytesIO(json.dumps(reply(answer)).encode())

    monkeypatch.setattr(urllib.request, "urlopen", urlopen)
    settings = Settings(
        _env_file=None,  # pyright: ignore[reportCallIssue]
        gemini_api_key=SecretStr("test-key-not-real"),
        sheet_kind_cache_dir=tmp_path,
        sheet_discipline=setting,  # pyright: ignore[reportArgumentType]
    )
    reader = _sheet_kind_reader(settings)
    found = SheetKindClassifier(None, reader, CUT).classify(png(), PNG_PROBED)
    assert isinstance(found, Classified) and found.sheet is not None
    (body,) = sent
    assert body["contents"][0]["parts"][1]["text"] == contract.prompt
    assert body["generationConfig"]["responseSchema"] == contract.schema
    (cached,) = tmp_path.glob("*.json")
    assert f"-{contract.sha[:12]}-" in cached.name
    # the prompt version is in the cache file's name, not the trace's words (9b03c2f1, QA R4)
    assert found.method == "Gemini sheet kind"
    # rules: an MEP plan titled by its level names no service; gemini: the model's heating
    assert found.sheet.discipline == (None if setting == "rules" else "heating")

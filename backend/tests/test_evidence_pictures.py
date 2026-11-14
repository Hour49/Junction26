"""The evidence step for a picture (decision 0012 sources v2, report 7.2-7.3): the kind rule as
amended, the record's `why`, and the real adapters' cache and spend guard (faked models, no
network)."""

import json
import urllib.request
from pathlib import Path
from typing import Any

import pytest
from evidence_fakes import FakeKinds, picture_kind
from pydantic import SecretStr
from test_sheet_kind import CUT, PIPING, FakeModel, png, reply
from test_triage_describer import FakeModel as FakeDescribeModel
from test_triage_describer import answer, form
from triage_fakes import FakeDescriber

from app.adapters.evidence.pictures import SheetKindPictures
from app.adapters.triage.gemini_describer import GeminiDescriber
from app.adapters.triage.sheet_kind import GeminiSheetKindClient, SheetKindReader
from app.composition import build_ingest, uses_keys
from app.core.evidence.pictures import FLOOR_PLAN, NO_DESCRIBER, picture_evidence
from app.core.ingest.model import ProjectStatus, SheetKindName
from app.core.spend import SpendGuard
from app.settings import Settings

IMAGE = b"\x89PNG a picture"
DESCRIBER = FakeDescriber({IMAGE: ("the north elevation of a house", ("A203",))}, usd=0.03)


@pytest.mark.parametrize(
    ("kind", "plan_on_sheet", "source"),
    [
        ("architectural_floor_plan", True, False),
        ("architectural_floor_plan", False, False),  # a floor plan sheet, whatever else it says
        ("multi_view_sheet", True, False),  # plan beside elevations: the page is the unit
        ("multi_view_sheet", False, True),
        ("site_plan_or_map", True, True),  # the house's floor inside its lot (A000): amended
        ("elevation", False, True),
        ("mep_plan", True, True),
        ("schedule_or_text", False, True),
    ],
)
def test_the_kind_rule_as_amended(kind: SheetKindName, plan_on_sheet: bool, source: bool) -> None:
    kinds = FakeKinds({IMAGE: picture_kind(kind, plan_on_sheet)})
    found = picture_evidence(IMAGE, kinds, DESCRIBER)
    assert found.indexed is source
    assert (found.how, found.kind) == (("described", kind) if source else (None, None))
    assert found.sheet is not None and found.sheet.kind == kind
    if not source:
        assert (found.why, found.description, found.cost_usd) == (FLOOR_PLAN, None, 0.012)


def test_a_source_is_described_and_says_why_with_both_calls_costed() -> None:
    found = picture_evidence(IMAGE, FakeKinds({IMAGE: picture_kind("elevation", False)}), DESCRIBER)
    assert found.description is not None
    assert found.description.subject == "the north elevation of a house"
    assert found.why == "not a floor plan: elevation (Gemini sheet kind, fake kind)"
    assert found.cost_usd == pytest.approx(0.042)


def test_a_failed_kind_call_is_not_a_source_and_says_why() -> None:
    found = picture_evidence(IMAGE, FakeKinds({}), DESCRIBER)
    assert (found.indexed, found.sheet, found.cost_usd) == (False, None, 0.0)
    assert found.why == "the kind call failed: the sheet-kind model could not answer: timed out"


def test_no_describer_is_not_a_source_and_says_so() -> None:
    found = picture_evidence(IMAGE, FakeKinds({IMAGE: picture_kind("section", False)}), None)
    assert (found.indexed, found.why, found.cost_usd) == (False, NO_DESCRIBER, 0.012)


def test_a_refused_description_is_not_a_source_and_gives_the_describers_note() -> None:
    kinds = FakeKinds({IMAGE: picture_kind("section", False)})
    found = picture_evidence(IMAGE, kinds, FakeDescriber({}))
    assert (found.indexed, found.why) == (False, "not described: the model refused")


def test_a_spent_budget_is_not_a_source_and_sends_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sent: list[int] = []

    def urlopen(request: urllib.request.Request, timeout: float) -> Any:
        sent.append(1)
        raise AssertionError("nothing is sent once the budget is spent")

    monkeypatch.setattr(urllib.request, "urlopen", urlopen)
    client = GeminiSheetKindClient("test-key-not-real", 5.0, budget=SpendGuard(0))
    kinds = SheetKindPictures(SheetKindReader(client, tmp_path), CUT)
    found = picture_evidence(png(), kinds, DESCRIBER)
    assert found.indexed is False and "Gemini budget used up" in found.why
    assert found.why.startswith("the kind call failed: ")
    assert sent == []


def test_a_cached_kind_reply_and_description_cost_nothing_and_ask_no_model(
    tmp_path: Path,
) -> None:
    image = png()
    kind_model = FakeModel(reply(PIPING))
    describe_model = FakeDescribeModel(answer(form()), answer(form()))
    kinds = SheetKindPictures(SheetKindReader(kind_model, tmp_path / "kind"), CUT)
    describer = GeminiDescriber(describe_model, tmp_path / "describe")
    first = picture_evidence(image, kinds, describer)
    assert first.indexed and first.cost_usd > 0
    again = picture_evidence(image, kinds, describer)
    assert (kind_model.calls, len(describe_model.asked)) == (1, 1)
    assert again.cost_usd == 0
    assert again.description is not None and first.description is not None
    assert again.description.subject == first.description.subject
    assert json.dumps(again.sheet.model_dump() if again.sheet else None) == json.dumps(
        first.sheet.model_dump() if first.sheet else None
    )


def test_the_scope_is_wired_named_in_the_reuse_key_only_when_on_and_counts_as_keys(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def urlopen(request: urllib.request.Request, timeout: float) -> Any:
        raise OSError("no network in tests")

    monkeypatch.setattr(urllib.request, "urlopen", urlopen)
    key = SecretStr("test-key-not-real")

    def ingested(**on: Any) -> ProjectStatus:
        settings = Settings(_env_file=None, gemini_api_key=key, **on)  # pyright: ignore[reportCallIssue]
        ingest = build_ingest(settings, tmp_path / "projects", background=False)
        status = ingest.wait(ingest.start("photo.png", png()))
        ingest.close()
        return status

    off = ingested()
    assert "evidence_scope" not in off.readers  # the default keeps the keys it had before
    assert off.files[0].evidence is None
    assert not uses_keys(Settings(_env_file=None))  # pyright: ignore[reportCallIssue]
    on = ingested(evidence_scope="all_non_plan")
    assert on.readers["evidence_scope"] == "all_non_plan"
    found = on.files[0].evidence
    assert found is not None and not found.indexed
    assert found.why.startswith("the kind call failed: the sheet-kind model could not answer")
    assert uses_keys(Settings(_env_file=None, evidence_scope="all_non_plan"))  # pyright: ignore[reportCallIssue]

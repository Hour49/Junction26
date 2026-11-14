"""Sheet.discipline: read from the sheet-kind reply's kind, title and number, with no new call.
A display hint only: the decision and confidence are the reply's as before. A fake reply."""

import pytest
from test_sheet_kind import CUT, form, png

from app.adapters.triage.sheet_kind import SheetReply, sheet_of


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

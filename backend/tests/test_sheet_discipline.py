"""Sheet.discipline: the sheet-kind reply's own `discipline` field (sheet-kind-3), cross-checked
against the title and sheet number it read, with no new call. They disagree by a strong word or
code: unsure (None). The decision and confidence are the reply's as before. A fake reply."""

import pytest
from test_sheet_kind import CUT, form, png

from app.adapters.triage.sheet_kind import SheetReply, sheet_of
from app.core.discipline import sheet_discipline


@pytest.mark.parametrize(
    ("found", "discipline"),
    [
        (form("architectural_floor_plan", True, True, 0.97), "architecture"),
        # the model's field, not the kind: a floor-plan-looking sheet with ducts drawn over it
        # ("Store Expansion Floor Plan", an M-2 sheet; the title names no service)
        (
            form(
                "architectural_floor_plan",
                True,
                True,
                0.9,
                title="Store Expansion Floor Plan",
                discipline="ventilation",
            ),
            "ventilation",
        ),
        # an MEP plan whose title names a level only: the model still names the service
        (
            form("mep_plan", False, True, 0.98, title="LEVEL 2", discipline="heating"),
            "heating",
        ),
        # title and number agree with the model
        (
            form(
                "structural_plan", False, False, 0.9, sheet_number="S-201", discipline="structural"
            ),
            "structural",
        ),
        # the title names another service than the model: unsure
        (
            form("mep_plan", False, True, 0.98, title="HEATING PLAN", discipline="plumbing"),
            None,
        ),
        (
            form("architectural_floor_plan", True, True, 0.9, sheet_number="E-101"),
            None,  # an electrical sheet number on what the model calls architecture
        ),
        # a weak word ("PIPING") or a service room never vetoes the model
        (
            form("mep_plan", False, True, 0.98, title="PIPING PLAN", discipline="heating"),
            "heating",
        ),
        (
            form("architectural_floor_plan", True, True, 0.9, title="ELECTRICAL ROOM LAYOUT"),
            "architecture",
        ),
        (form("schedule_or_text", False, False, 0.95), "other"),
    ],
)
def test_the_sheet_discipline_is_the_models_cross_checked(
    found: dict, discipline: str | None
) -> None:
    sheet = sheet_of(SheetReply(found, 0.0, "fake", "fake"), png(), CUT)
    assert sheet.discipline == discipline
    assert sheet.confidence == found["confidence"]


def test_a_title_naming_two_services_vetoes_only_a_third() -> None:
    assert sheet_discipline("ventilation", "HEATING AND VENTILATION PLAN", None) == "ventilation"
    assert sheet_discipline("plumbing", "HEATING AND VENTILATION PLAN", None) is None
    assert sheet_discipline("plumbing", None, None) == "plumbing"

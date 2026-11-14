import pytest
from pydantic import ValidationError

from app.core.ifc_facts import Fact, FactSheet, Spot


def _fact(**changes: object) -> Fact:
    given: dict[str, object] = {
        "topic": "space.net_floor_area",
        "subject": "101",
        "value": 12.5,
        "unit": "m2",
        "storey": "Level 1",
        "discipline": "architecture",
        "source": "Qto_SpaceBaseQuantities.NetFloorArea",
    }
    return Fact.model_validate(given | changes)


def test_a_fact_sheet_round_trips_through_json() -> None:
    sheet = FactSheet(
        model="m", disciplines=["architecture"], facts=[_fact(), _fact(value="Brick", unit=None)]
    )
    assert FactSheet.model_validate_json(sheet.model_dump_json()) == sheet
    assert sheet.facts[0].system is None


def test_a_fact_is_frozen() -> None:
    with pytest.raises(ValidationError):
        _fact().value = 3  # type: ignore[misc]


@pytest.mark.parametrize("changes", [{"discipline": "cooking"}, {"colour": "red"}])
def test_an_unknown_discipline_or_field_is_refused(changes: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        _fact(**changes)


def test_a_fact_has_no_spots_unless_given_and_keeps_them_through_json() -> None:
    assert _fact().spots == ()
    spot = Spot(page=1, box=(0.1, 0.2, 0.15, 0.25), reader="vlm")
    fact = _fact(spots=(spot,))
    assert Fact.model_validate_json(fact.model_dump_json()).spots == (spot,)

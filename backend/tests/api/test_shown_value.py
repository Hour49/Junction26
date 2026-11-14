"""The value the screen shows (`shown_value`): an area that is an estimate in whole m² (r8 BM fix 3:
"181.11 m²" claimed a precision a ±24% estimate does not have); a measured area as it is."""

from app.adapters.answer_prior import NoPrior
from app.adapters.question_templates import TemplateParser
from app.api.ask import shown_value
from app.core.drawing.model import Drawing, Page, Room, Scale
from app.core.review.ask import ask
from app.core.review.model import ReviewState

PAGE = Page(page=1, width=100, height=100, unit="pt")
KITCHEN = Room(id="r1", type="kitchen", page=1, box=(0.1, 0.1, 0.2, 0.2), area_m2=12.34)


def shown(drawing: Drawing) -> object:
    found = ask("What is the area of the kitchen?", drawing, parser=TemplateParser(),
                clock=lambda: 0.0, prior=NoPrior(), state=ReviewState())  # fmt: skip
    assert found.refusal is None and found.answer.answer == 12.34  # the scorer's line as measured
    return shown_value(found)


def test_an_estimated_area_shows_in_whole_square_metres_a_measured_one_as_it_is() -> None:
    estimated = KITCHEN.model_copy(
        update={"area_status": "estimated", "area_source": "geometry_x_estimate",
                "area_uncertainty": 0.24}
    )  # fmt: skip
    scale = Scale(status="estimated", m_per_unit=0.01, uncertainty=0.12, source="doors")
    assert shown(Drawing(file="x.png", pages=(PAGE,), scale=scale, rooms=(estimated,))) == 12
    scaled = Scale(status="scaled", m_per_unit=0.01)
    assert shown(Drawing(file="x.png", pages=(PAGE,), scale=scaled, rooms=(KITCHEN,))) == 12.34

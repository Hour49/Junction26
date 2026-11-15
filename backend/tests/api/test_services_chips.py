"""R1 services-second S3 (2026-11-15): on a sheet triage is sure is a services plan, a refusal
offered floor-plan questions ("How many halls are there?", net floor area) as what it can
answer. A services sheet offers no floor-plan chips."""

from app.core.drawing.model import Room
from tests.api.test_review_core import BOX_A, BOX_B, SERVICES_FLAG, asked_flagged, photo


def test_a_refusal_on_a_services_plan_offers_no_floor_plan_questions() -> None:
    drawing = photo(
        Room(id="r1", type="hall", page=1, box=BOX_A),
        Room(id="r2", type="storage", page=1, box=BOX_B),
    )
    on_plan = asked_flagged("How many radiators are there?", drawing, (), raster=True)
    assert on_plan.refusal is not None and on_plan.refusal.can_answer  # floor-plan chips
    services = asked_flagged(
        "How many radiators are there?", drawing, (SERVICES_FLAG,), raster=True,
        no_symbols=SERVICES_FLAG,
    )  # fmt: skip
    assert services.refusal is not None and not services.refusal.can_answer

"""R1 services-second S3 (2026-11-15): on a sheet triage is sure is a services plan, a refusal
offered floor-plan questions ("How many halls are there?", net floor area) as what it can
answer, and the drawing's own suggestions (the drawing Ask's chips and the project chat's
starters) were floor-plan ones too. A services sheet offers no floor-plan chips."""

from pathlib import Path

from test_api_sheet_kind import PIPING_PNG, PLAN_PNG, files_of, seeded
from test_api_triage import project
from test_review_core import BOX_A, BOX_B, SERVICES_FLAG, asked_flagged, photo

from app.core.drawing.model import Room
from app.settings import Settings


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


def test_a_services_plan_suggests_no_floor_plan_questions(
    settings: Settings, tmp_path: Path
) -> None:
    client = seeded(settings, tmp_path, sheet_kind_set_aside=False)
    found = project(client, {"piping.png": PIPING_PNG, "plan.png": PLAN_PNG})
    files = files_of(found)

    def suggested(path: str) -> list[str]:
        drawing_id = files[path]["drawing_id"]
        body = client.get(f"/api/drawings/{drawing_id}", params={"project": found["id"]}).json()
        return [suggestion["question"] for suggestion in body["suggestions"]]

    assert "How many doors are there?" in suggested("plan.png")  # a floor plan keeps its chips
    assert suggested("piping.png") == []  # sure services plan (mep_plan, 0.98)


def test_a_services_refusal_points_to_no_empty_list() -> None:
    """review-697 S1: with no chips, "Try one of these instead." pointed at nothing."""
    drawing = photo(
        Room(id="r1", type="hall", page=1, box=BOX_A),
        Room(id="r2", type="storage", page=1, box=BOX_B),
    )
    for question in ("How many toilets are in the hall?", "What colour is the plan?"):
        on_plan = asked_flagged(question, drawing, (), raster=True)
        assert on_plan.refusal is not None and "one of these" in on_plan.refusal.text
        services = asked_flagged(
            question, drawing, (SERVICES_FLAG,), raster=True, no_symbols=SERVICES_FLAG
        )
        assert services.refusal is not None and not services.refusal.can_answer
        assert "one of these" not in services.refusal.text, services.refusal.text
        assert services.refusal.text.endswith("."), services.refusal.text

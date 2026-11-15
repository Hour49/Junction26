"""The picture lane's fact sheets reach a plan edit's services follow-up (services-follow.md
Pictures; discipline-pictures.md): `service_tools.follower` gives `ServiceFollower` the project's
sheets the lane kept (`PictureSheets`, by a drawing's page file) while DISCIPLINE_PICTURES is on."""

from pathlib import Path
from types import SimpleNamespace
from typing import Any, Literal

from test_service_tools_pictures import PLAN, project
from test_services_picture_follow import WALL, heating

from app.adapters.discipline_pictures.lane import PictureSheets
from app.adapters.service_tools import follower
from app.core.plan_edit.model import Proposal
from app.settings import Settings


def followed(tmp_path: Path, mode: Literal["off", "template"]) -> Any:
    cache = tmp_path / "pictures"
    PictureSheets(None, cache).put("sheet", heating())  # the plan file's sha256
    settings = Settings(discipline_pictures=mode, discipline_pictures_cache_dir=cache)
    pipeline = project()
    pipeline.settings = settings
    app = SimpleNamespace(state=SimpleNamespace())
    proposal = Proposal(proposal_id="p1", drawing_id=PLAN, page=1, removed=(WALL,))
    services, _ = follower(app, pipeline).run(proposal)
    return {d.discipline: d.status for d in services.disciplines}


def test_a_project_with_a_picture_services_sheet_gets_its_picture_lane(tmp_path: Path) -> None:
    assert followed(tmp_path, "template")["heating"] == "checked"


def test_off_the_follower_reads_no_picture_sheet(tmp_path: Path) -> None:
    assert followed(tmp_path, "off")["heating"] == "no_model"

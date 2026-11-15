"""The picture lane's fact sheets reach a plan edit's services follow-up (services-follow.md
Pictures; discipline-pictures.md): `service_tools.follower` gives `ServiceFollower` the project's
sheets the lane kept (`PictureSheets`, by a drawing's page file) while DISCIPLINE_PICTURES is on."""

from pathlib import Path
from types import SimpleNamespace
from typing import Any, Literal

from test_service_tools_pictures import PLAN, project
from test_services_picture_follow import WALL, heating

from app.adapters.discipline_pictures.lane import PictureFactSheet, PictureSheets
from app.adapters.service_tools import follower
from app.core.plan_edit.model import Proposal
from app.settings import Settings


def followed(tmp_path: Path, mode: Literal["off", "template"]) -> Any:
    cache = tmp_path / "pictures"
    PictureSheets(None, cache).put(
        "sheet", PictureFactSheet.model_validate(heating().model_dump())
    )  # the plan file's sha256
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


def walled(mode: Literal["off", "template"]) -> Any:
    """The follower of a project with the plan PDF and a heating picture (PNG) of drawing d2."""
    import cv2

    from app.core.ingest.model import FileStatus
    from tests.test_picture_sheet_walls import with_schedule
    from tests.test_picture_walls import sheet

    pipeline = project()
    status = pipeline.ingest.status(None)
    picture = FileStatus(id="f2", path="heating.png", size=1, sha256="pic", kind="png_plan",
                         state="ready", group="plan", route="raster", drawing_id="d2")  # fmt: skip
    status = status.model_copy(update={"files": (*status.files, picture)})
    png = cv2.imencode(".png", with_schedule(sheet()))[1].tobytes()
    uploads = {"f1": b"%PDF-1.7 not a picture", "f2": png}
    pipeline.ingest.status = lambda _: status
    pipeline.ingest.upload_bytes = lambda _, file_id: uploads[file_id]
    pipeline.settings = Settings(discipline_pictures=mode)
    return follower(SimpleNamespace(state=SimpleNamespace()), pipeline)


def test_on_the_follower_reads_a_picture_s_walls_from_its_upload() -> None:
    from app.core.services.picture_follow import Sheet

    made = walled("template")
    assert made.sheet_walls is not None
    got = made.sheet_walls(Sheet(drawing_id="d2", page=1))
    assert not isinstance(got, str), got
    parts, size = got
    assert size == (1000.0, 700.0) and len(parts) >= 2  # the whole page and the plan view
    pdf = made.sheet_walls(Sheet(drawing_id=PLAN, page=1))
    assert pdf == "the services sheet is no picture file: its walls are not read"
    assert walled("off").sheet_walls is None

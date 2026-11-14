"""Response models shared by several routes (docs/API.md). Every route returns a pydantic model,
so /openapi.json describes every response; unknown fields are refused so a fixture that drifts
from the code fails its test (tests/api/test_api_fixtures.py)."""

from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.composition import second_counter_of
from app.core.drawing.model import Page
from app.core.ingest.model import DrawingInfo, FileState, Normalised, ProjectStatus
from app.core.pipeline.model import Route


class View(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ErrorBody(View):
    """Every error: one sentence, a code, and FastAPI's list for a request that fails validation."""

    detail: str
    code: str
    errors: list[dict[str, object]] | None = None


class PageView(View):
    page: int
    width: float
    height: float
    unit: Literal["px", "pt"]
    url: str
    normalised: Normalised | None  # how an image sheet was made upright; None for a PDF page


def page_views(
    drawing_id: str, pages: tuple[Page, ...], normalised: Normalised | None
) -> list[PageView]:
    return [
        PageView(
            page=page.page,
            width=page.width,
            height=page.height,
            unit=page.unit,
            url=f"/api/drawings/{drawing_id}/pages/{page.page}.png",
            normalised=normalised,
        )
        for page in pages
    ]


class Reader(View):
    """How a drawing was read: its route, the file it was read from and that route's reader."""

    route: Route | None
    source: str | None
    extractor: str | None
    second_counter: str
    question_parser: str


def reader_of(info: DrawingInfo, twice: bool, names: dict[str, str]) -> Reader:
    """`names`: composition.readers(settings), the adapter of each route and port. `twice`: the
    second counter measured what is shown (a drawing: anything on it, stage 8 wrote its
    conflicts; an answer: the answered quantity); else it is named "none"."""
    return Reader(
        route=info.route,
        source=info.source,
        extractor=None if info.route is None else names[info.route],
        second_counter=second_counter_of(names, info.route) if twice else "none",
        question_parser=names["question_parser"],
    )


class Rendering(View):
    drawing_id: str
    file: str


class DrawingEntry(View):
    """One drawing of a project: one per group of renderings of the same plan."""

    drawing_id: str
    group: str
    file: str
    kind: str | None
    route: Route | None
    source: str | None
    state: FileState
    other_renderings: list[Rendering]


class ProjectView(ProjectStatus):
    """Ingest's project status, plus the project's drawings, one per plan."""

    drawings: tuple[DrawingEntry, ...]

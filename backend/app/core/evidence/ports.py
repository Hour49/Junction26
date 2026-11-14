"""What the evidence index needs from outside, as Protocols (app/adapters/evidence has them)."""

from typing import Protocol

from app.core.ingest.model import ProjectStatus, Sheet, Unavailable
from app.core.model import Frozen


class EvidenceIndex(Protocol):
    """A project's evidence index, kept in step with its saved status: `update` re-indexes the
    sources whose content changed, drops the ones gone and refreshes every verdict. Ingest calls it
    after a project is judged and after a person's overrule; it must not fail ingest."""

    def update(self, status: ProjectStatus) -> None: ...


class PictureKind(Frozen):
    """The sheet-kind model's reply for one picture, as the evidence step reads it."""

    sheet: Sheet
    floor_plan_on_sheet: bool  # the model's own answer, before any cut
    usd: float  # 0 from the cache
    said: str  # "gemini-4-carbon, sheet-kind-2" (+ ", cached")


class PictureKinds(Protocol):
    """What a picture is: the sheet-kind reader of SHEET_KIND, used for the index only (the same
    reply and cache file when both are on). `Unavailable`: the call failed, or the budget is
    spent."""

    def kind(self, image: bytes) -> PictureKind | Unavailable: ...

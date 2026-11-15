"""What the evidence index needs from outside, as Protocols (app/adapters/evidence has them)."""

from typing import Protocol

from app.core.evidence.file_sources import TextSource
from app.core.ingest.model import ContentKind, ProjectStatus, Sheet, Unavailable
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
    said: str  # the method in words: "Gemini sheet kind" (+ " (cached reply)")


class PictureKinds(Protocol):
    """What a picture is: the sheet-kind reader of SHEET_KIND, used for the index only (the same
    reply and cache file when both are on). `Unavailable`: the call failed, or the budget is
    spent."""

    def kind(self, image: bytes) -> PictureKind | Unavailable: ...


class FileTexts(Protocol):
    """A file's own text as a `text` source (decision 0012 sources v2, 7.4): a text document's
    pages with text, or a drawn or scanned PDF's text pages (never its drawn pages, which are
    pictures or files of their own). None: nothing to index. The same bytes give the same text,
    so the index reads it again from the stored file instead of keeping it in the status."""

    def text(self, path: str, kind: ContentKind, data: bytes) -> TextSource | None: ...

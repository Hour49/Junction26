"""`SheetKindPictures`: the evidence step's kind call (decision 0012 sources v2) through the
sheet-kind reader of SHEET_KIND (app/adapters/triage/sheet_kind.py): the same prompt, model, cache
file and spend-guard label, so a file is paid for once whichever step asks first."""

from app.adapters.triage.sheet_kind import SheetKindReader, sheet_of
from app.core.evidence.ports import PictureKind
from app.core.ingest.model import Unavailable


class SheetKindPictures:
    def __init__(self, reader: SheetKindReader, cut: float) -> None:
        self._reader, self._cut = reader, cut  # the cut only fills `Sheet.decision`

    def kind(self, image: bytes) -> PictureKind | Unavailable:
        found = self._reader.read(image)
        if isinstance(found, Unavailable):
            return found
        return PictureKind(
            sheet=sheet_of(found, image, self._cut),
            floor_plan_on_sheet=bool(found.form["floor_plan_on_sheet"]),
            usd=found.usd,
            said=found.said,
        )

"""A fake of the evidence step's kind call (decision 0012 sources v2): replies keyed by a file's
bytes, for the evidence and ingest tests."""

from collections.abc import Mapping
from dataclasses import dataclass, field

from app.core.evidence.ports import PictureKind
from app.core.ingest.model import Sheet, SheetKindName, Unavailable


def picture_kind(kind: SheetKindName, plan_on_sheet: bool, usd: float = 0.012) -> PictureKind:
    sheet = Sheet(
        kind=kind,
        kind_words=kind.replace("_", " "),
        decision="read" if kind == "architectural_floor_plan" else "set_aside",
        takeoff_possible=plan_on_sheet,
        confidence=0.95,
        title=None,
        sheet_number=None,
        printed_scale=None,
        advanced=False,
        advanced_why=None,
        seen="a sheet",
        model="fake sheet kind",
    )
    return PictureKind(sheet=sheet, floor_plan_on_sheet=plan_on_sheet, usd=usd, said="fake kind")


@dataclass
class FakeKinds:
    """`replies`: per file's bytes, the kind reply; any other file: the call failed. `asked`
    counts the calls."""

    replies: Mapping[bytes, PictureKind]
    asked: list[bytes] = field(default_factory=list[bytes])

    def kind(self, image: bytes) -> PictureKind | Unavailable:
        self.asked.append(image)
        found = self.replies.get(image)
        if found is None:
            return Unavailable(note="the sheet-kind model could not answer: timed out")
        return found

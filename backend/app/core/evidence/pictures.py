"""The evidence step for a picture (decision 0012 sources v2): one image the models can look at
(a PNG or JPEG, a scanned or drawn PDF page) that today's triage did not set aside. The sheet-kind
model is asked what it is; a picture that is not a floor plan sheet is described and becomes a
source. A floor plan, a failed call or no describer leaves it out, with the reason in `why`.

This only adds descriptions: the file is read as a plan or set aside exactly as it would be with
the step off (describing for the index is decoupled from setting aside, so no plan is lost)."""

from collections.abc import Callable
from dataclasses import dataclass

from app.core.evidence.ports import FileTexts, PictureKinds
from app.core.ingest.model import (
    Classified,
    ContentKind,
    FileEvidence,
    FileStatus,
    Unavailable,
)
from app.core.ingest.ports import Describer
from app.core.pipeline.identify import sniff

# The probe kinds that are pictures; a PNG or JPEG the probe calls `unknown` is one too
PICTURE_KINDS: frozenset[ContentKind] = frozenset(
    {"png_plan", "jpeg_plan", "photo_plan", "photo", "pdf_scan", "pdf_vector"}
)
IMAGE_FORMATS = frozenset({"png", "jpeg"})
NOT_DRAWING = frozenset({"not_a_drawing", "schedule_or_text"})  # described as not_drawing
FLOOR_PLAN = "a floor plan: it is read, so it is not in the evidence index"
NO_DESCRIBER = "not described: no description model is set up"


@dataclass(frozen=True)
class EvidenceSteps:
    """EVIDENCE_SCOPE=all_non_plan as composition built it: the kind call, the describer (None:
    pictures are not described and say so) and the reader of a file's own text."""

    kinds: PictureKinds
    describer: Describer | None
    texts: FileTexts


def is_picture(file: FileStatus, read: Callable[[], bytes]) -> bool:
    """Whether the evidence step asks about the file: a picture that triage did not set aside
    (a set-aside file keeps today's path: its triage description is the source). `read` gives
    the upload's bytes, read only for a file the probe could not name."""
    if file.triage is not None and file.triage.class_ != "floor_plan":
        return False
    if file.kind in PICTURE_KINDS:
        return True
    return file.kind == "unknown" and sniff(read()) in IMAGE_FORMATS


def picture_evidence(
    image: bytes, kinds: PictureKinds, describer: Describer | None
) -> FileEvidence:
    """Whether the picture is a source (rule 7.2 as amended): every sheet except a floor plan
    sheet and a several-views sheet with a floor plan on it, so a site plan that also draws the
    house's floor is one. No confidence cut: a plan wrongly called no plan is still read, only
    also described."""
    found = kinds.kind(image)
    if isinstance(found, Unavailable):
        return FileEvidence(indexed=False, why=f"the kind call failed: {found.note}")
    sheet = found.sheet
    if sheet.kind == "architectural_floor_plan" or (
        sheet.kind == "multi_view_sheet" and found.floor_plan_on_sheet
    ):
        return FileEvidence(indexed=False, why=FLOOR_PLAN, sheet=sheet, cost_usd=found.usd)
    if describer is None:
        return FileEvidence(indexed=False, why=NO_DESCRIBER, sheet=sheet, cost_usd=found.usd)
    classified = Classified.model_validate(
        {
            "class": "not_drawing" if sheet.kind in NOT_DRAWING else "other_drawing",
            "p_plan": 1 - sheet.confidence,
            "method": found.said,
            "cost_usd": found.usd,
            "sheet": sheet,
        }
    )
    described = describer.describe(image, classified)
    if isinstance(described, Unavailable):
        why = f"not described: {described.note}"
        return FileEvidence(indexed=False, why=why, sheet=sheet, cost_usd=found.usd)
    return FileEvidence(
        indexed=True,
        how="described",
        kind=sheet.kind,
        why=f"not a floor plan: {sheet.kind_words} ({found.said})",
        sheet=sheet,
        description=described,
        cost_usd=found.usd + described.cost_usd,
    )

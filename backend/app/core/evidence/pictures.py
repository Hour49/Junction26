"""The evidence step for a picture (decision 0012 sources v2): one image the models can look at
(a PNG or JPEG, a scanned or drawn PDF page) that today's triage did not set aside. The sheet-kind
model is asked what it is; a picture with no floor plan on it is described and becomes a source.
A floor plan, a failed call or no describer leaves it out, with the reason in `why`.

This only adds descriptions: the file is read as a plan or set aside exactly as it would be with
the step off (describing for the index is decoupled from setting aside, so no plan is lost)."""

from app.core.evidence.ports import PictureKinds
from app.core.ingest.model import (
    Classified,
    ContentKind,
    FileEvidence,
    Unavailable,
)
from app.core.ingest.ports import Describer

# The probe kinds that are pictures; a PNG or JPEG the probe calls `unknown` is one too
PICTURE_KINDS: frozenset[ContentKind] = frozenset(
    {"png_plan", "jpeg_plan", "photo_plan", "photo", "pdf_scan", "pdf_vector"}
)
NOT_DRAWING = frozenset({"not_a_drawing", "schedule_or_text"})  # described as not_drawing
FLOOR_PLAN = "a floor plan: it is read, so it is not in the evidence index"
NO_DESCRIBER = "not described: no description model is set up"


def picture_evidence(
    image: bytes, kinds: PictureKinds, describer: Describer | None
) -> FileEvidence:
    """Whether the picture is a source: the sheet-kind reply says no floor plan on the sheet and
    a kind other than architectural_floor_plan (no confidence cut: a plan wrongly called no plan
    is still read, only also described)."""
    found = kinds.kind(image)
    if isinstance(found, Unavailable):
        return FileEvidence(indexed=False, why=f"the kind call failed: {found.note}")
    sheet = found.sheet
    if found.floor_plan_on_sheet or sheet.kind == "architectural_floor_plan":
        return FileEvidence(indexed=False, why=FLOOR_PLAN, sheet=sheet, cost_usd=found.usd)
    if describer is None:
        return FileEvidence(indexed=False, why=NO_DESCRIBER, sheet=sheet, cost_usd=found.usd)
    classified = Classified.model_validate(
        {
            "class": "not_drawing" if sheet.kind in NOT_DRAWING else "other_drawing",
            "p_plan": 1 - sheet.confidence,
            "method": f"Gemini sheet kind ({found.said})",
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
        why=f"not a floor plan: {sheet.kind_words} (Gemini sheet kind, {found.said})",
        sheet=sheet,
        description=described,
        cost_usd=found.usd + described.cost_usd,
    )

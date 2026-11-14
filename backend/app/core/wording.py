"""Words for the text a person reads in a trace or a reason (not for any machine field): a count
with its noun in the right number, a content kind and a scale status in plain words."""

from app.core.drawing.model import ConflictQuantity, ScaleStatus

KIND_WORDS = {
    "pdf_vector": "drawn PDF",
    "pdf_scan": "scanned PDF",
    "png_plan": "PNG drawing",
    "jpeg_plan": "JPEG drawing",
    "photo_plan": "photo of a drawing",
    "ifc": "IFC model",
    "dxf": "DXF drawing",
    "svg": "SVG drawing",
    "pdf_text": "text PDF",
    "text": "text file",
    "photo": "photo",
    "pdf_encrypted": "locked PDF",
    "dwg": "DWG file",
    "office": "Office file",
    "archive": "archive inside an archive",
    "unknown": "unknown file type",
}
SCALE_WORDS: dict[ScaleStatus, str] = {
    "scaled": "scale read from the sheet",
    "no_scale": "no scale on the sheet",
    "not_to_scale": "sheet says it is not to scale",
    "estimated": "scale estimated",
}

CONFLICT_WORDS: dict[ConflictQuantity, str] = {
    "room_area": "room areas",
    "apartment_area": "apartment areas",
    "floor_area": "floor area",
    "room_count": "room count",
    "element_count": "element counts",
    "scale": "scale",
    "storey_count": "storey count",
    "other": "other quantities",
}


def count(n: int, one: str, many: str | None = None) -> str:
    """ "1 conflict", "2 conflicts": `many` when the plural is no `one` + "s" ("quantities")."""
    return f"{n} {one if n == 1 else many or one + 's'}"


def kind_words(kind: str) -> str:
    return KIND_WORDS.get(kind, kind)

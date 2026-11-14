"""How a source is cut into passages, as decision 0012 fixes it (rag's pre-registered settings,
ported from prototypes/rag/retrieve.py): one summary passage (the kind in words, the subject and
the short text; not the judge's why, which is reasoning about the file, not its content), then
`detail` cut at sentence ends and `visible_text` cut at line ends, packed into passages of at
most `PASSAGE_CHARS` characters; a longer piece is cut. Numbering: summary is one passage; the
others count from 1."""

import re

from app.core.evidence.model import EvidenceSource, PartName, Passage

PASSAGE_CHARS = 500
SENTENCE_END = re.compile(r"(?<=[.!?])\s+")
KIND_WORDS = {
    "multi_view_sheet": "sheet with several views",
    "site_plan_or_map": "site plan or map",
    "elevation": "elevation",
    "section": "section",
    "detail": "detail drawing",
    "perspective_or_axonometric": "perspective or axonometric view",
    "engineering_non_building": "engineering drawing, not a building",
    "cover_or_text_sheet": "cover or text sheet",
    "photograph": "photograph",
    "not_architecture": "not architecture",
    "other": "other",
    "artwork": "artwork",
    "text_page": "text page",
    "object": "object",
    "music": "sheet music",
    "map": "map",
    "drawing": "drawing",
    # sources v2 (decision 0012): the sheet kinds the ones above lack, in #251's words
    "mep_plan": "piping, plumbing, ventilation or electrical plan",
    "structural_plan": "structural plan (foundation, slab, framing or reinforcement)",
    "roof_or_ceiling_plan": "roof plan or ceiling plan",
    "schedule_or_text": "schedule, table or text sheet",
    "not_a_drawing": "not a drawing",
    # text and listed sources
    "text_document": "text document",
    "text_file": "text file",
    "text_pages": "text pages of a drawing file",  # a drawn or scanned PDF's own text pages
    "not_read": "file that was not read",  # a refused entry, or one identify could not read
    "dwg": "DWG drawing, not converted",
    "office": "office document",
    "ifc": "building model (IFC)",
    "archive": "archive, not unpacked",
    "pdf_encrypted": "encrypted PDF",
    "unknown": "file of unknown type",
}


def pack(pieces: list[str], joiner: str, size: int = PASSAGE_CHARS) -> list[str]:
    """Pieces joined greedily into passages of at most `size` characters; a longer piece is cut."""
    found: list[str] = []
    current = ""
    for piece in pieces:
        piece = piece.strip()
        while len(piece) > size:
            if current:
                found.append(current)
                current = ""
            found.append(piece[:size])
            piece = piece[size:].strip()
        if not piece:
            continue
        if current and len(current) + len(joiner) + len(piece) > size:
            found.append(current)
            current = piece
        else:
            current = f"{current}{joiner}{piece}" if current else piece
    if current:
        found.append(current)
    return found


def passages(source: EvidenceSource) -> list[Passage]:
    described = source.description
    label = KIND_WORDS.get(source.kind, "")
    said = (f"{label}." if label else "", f"{described.subject}.", described.text)
    summary = " ".join(part for part in said if part)
    found = [Passage(part="summary", n=1, text=summary)]
    parts: tuple[tuple[PartName, list[str]], ...] = (
        ("detail", pack(SENTENCE_END.split(described.detail), " ")),
        ("visible_text", pack(described.visible_text.splitlines(), "\n")),
    )
    for part, texts in parts:
        found += [Passage(part=part, n=n, text=text) for n, text in enumerate(texts, start=1)]
    return found

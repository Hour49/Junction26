"""The evidence index's `text` and `listed` sources (rag's contract 7.1, 7.4 and the 7.7 tests for
tables-fix's part): page texts from real PDFs, the drawn-page rule, the 200,000 character cut, the
contact cut and the listed passage."""

import io

import pypdfium2
from pdf_sheets import SheetPdf, rect

from app.adapters.evidence.file_text import pdf_pages, text_file
from app.core.evidence.chunks import PASSAGE_CHARS
from app.core.evidence.file_sources import (
    TEXT_CHARS,
    PageText,
    listed_piece,
    name_words,
    text_source,
)

LINE = "The contractor keeps the site fenced and lit at night during the works."  # 72 chars


def text_page(label: str, lines: int = 6) -> SheetPdf:
    """A page of plain text, no drawing: the probe calls it a text page."""
    sheet = SheetPdf()
    for at in range(lines):
        sheet.text(f"{label} {LINE}", 20, 30 + 12 * at, size=8)
    return sheet


def drawn_page() -> SheetPdf:
    """A page with 30 path objects and a few characters: the probe calls it drawn."""
    sheet = SheetPdf()
    for at in range(30):
        sheet.path(rect(10 + at * 15, 50, 20 + at * 15, 300))
    sheet.text("A101", 500, 380)
    return sheet


def joined(*sheets: SheetPdf) -> bytes:
    """One PDF whose pages are the given sheets, in order."""
    document = pypdfium2.PdfDocument.new()
    for sheet in sheets:
        document.import_pages(pypdfium2.PdfDocument(sheet.pdf()))
    out = io.BytesIO()
    document.save(out)
    return out.getvalue()


def test_a_three_page_text_pdf_gives_text_passages_from_pages_one_to_three() -> None:
    pages = pdf_pages(joined(text_page("Page one."), text_page("Page two."), text_page("Page 3.")))
    assert [(page.number, page.drawn) for page in pages] == [(1, False), (2, False), (3, False)]
    found = text_source("specs/Work_spec-2026.pdf", "text document", pages, whole=True)
    assert found is not None
    assert (found.pages, found.cut) == (3, False)
    summary, *texts = found.pieces
    assert (summary.part, summary.n, summary.page) == ("summary", 1, 1)
    assert summary.text.startswith("text document. Work spec 2026. Page one. The contractor")
    assert len(summary.text) <= len("text document. Work spec 2026. ") + 300
    assert [(piece.part, piece.n) for piece in texts] == [
        ("text", n) for n in range(1, len(texts) + 1)
    ]
    assert {piece.page for piece in texts} == {1, 2, 3}
    assert all(len(piece.text) <= PASSAGE_CHARS for piece in texts)
    by_page = {n: "\n".join(p.text for p in texts if p.page == n) for n in (1, 2, 3)}
    assert "Page two." in by_page[2] and "Page two." not in by_page[1] + by_page[3]
    assert found.chars == sum(len(text) for text in by_page.values())  # passages hold it all


def test_a_text_page_inside_a_drawn_pdf_is_a_source_and_the_drawing_is_not() -> None:
    pages = pdf_pages(joined(drawn_page(), text_page("General notes.")))
    assert [(page.number, page.drawn) for page in pages] == [(1, True), (2, False)]
    found = text_source("set/house.pdf", "text document", pages, whole=False)
    assert found is not None and found.pages == 1
    assert {piece.page for piece in found.pieces if piece.part == "text"} == {2}
    assert not any("A101" in piece.text for piece in found.pieces)


def test_a_short_text_page_inside_a_drawn_pdf_is_not_a_source() -> None:
    pages = pdf_pages(joined(drawn_page(), text_page("Short.", lines=2)))  # under 200 characters
    assert len(pages[1].text.strip()) < 200
    assert text_source("set/house.pdf", "text document", pages, whole=False) is None
    assert text_source("set/house.pdf", "text document", [], whole=True) is None


def test_the_file_is_cut_at_two_hundred_thousand_characters_at_a_line_end() -> None:
    line = "x" * 99
    page = "\n".join([line] * 1500)  # 150,000 characters with the line ends
    pages = [PageText(number=n, text=page, drawn=False) for n in (1, 2)]
    found = text_source("big.txt", "text file", pages, whole=True)
    assert found is not None
    assert found.cut and found.chars <= TEXT_CHARS
    assert found.chars > TEXT_CHARS - 100  # cut at the last line that fits, not a page earlier
    texts = [piece for piece in found.pieces if piece.part == "text"]
    assert {piece.page for piece in texts} == {1, 2}
    assert all(piece.text.split("\n")[-1] == line for piece in texts)  # whole lines only
    small = text_source("small.txt", "text file", pages[:1], whole=True)
    assert small is not None and not small.cut


def test_a_phone_number_and_an_email_are_in_no_passage() -> None:
    text = (
        "Site manager: Matti Virtanen\nPuh. 040 123 4567\nmatti.virtanen@example.fi\nGate code 4411"
    )
    (page,) = text_file(text.encode())
    found = text_source("contacts.txt", "text file", [page], whole=True)
    assert found is not None
    every = "\n".join(piece.text for piece in found.pieces)
    assert "040 123 4567" not in every and "@" not in every
    assert "Gate code 4411" in every and "Matti Virtanen" in every


def test_a_text_file_is_one_page_in_utf8_or_latin1() -> None:
    assert text_file("Kylpyhuone 4,5 m²".encode()) == [
        PageText(number=1, text="Kylpyhuone 4,5 m²", drawn=False)
    ]
    assert text_file("Kylpyhuone ä".encode("latin-1"))[0].text == "Kylpyhuone ä"
    assert text_file(b"\xef\xbb\xbfBOM")[0].text == "BOM"


def test_a_pdf_that_does_not_open_has_no_pages() -> None:
    assert pdf_pages(b"%PDF-1.7 not really") == []


def test_a_dwg_is_listed_by_name_and_its_passage_says_it_is_not_read() -> None:
    piece = listed_piece(
        "cad/House_A-101.dwg", "DWG drawing, not converted", "a DWG file, needs converting first."
    )
    assert (piece.part, piece.n, piece.page) == ("summary", 1, 1)
    assert piece.text == (
        "DWG drawing, not converted. House A 101. Its content is not read: a DWG file, needs "
        "converting first."
    )


def test_name_words() -> None:
    assert name_words("a/b/Work_spec-2026.final.pdf") == "Work spec 2026.final"
    assert name_words("notes.txt") == "notes"
    assert name_words("x\\y\\IFC_model.ifc") == "IFC model"

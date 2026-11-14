"""The evidence index's `text` and `listed` sources (rag's contract 7.1, 7.4 and the 7.7 tests for
tables-fix's part): page texts from real PDFs, the drawn-page rule, the 200,000 character cut, the
contact cut and the listed passage."""

import io

import pypdfium2
import pytest
from pdf_sheets import SheetPdf, rect

from app.adapters.archive.probe import (
    MAX_PAGES,
    _PageNotLoadedError,  # pyright: ignore[reportPrivateUsage]
)
from app.adapters.evidence import file_text
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


# --- codecheck's review of #259 (.agents/qa/r9/review-259.md) ----------------------------------


def test_contacts_in_the_file_name_are_in_no_passage() -> None:
    """M1: the file name goes through the contact rule too, in the summary and the listed one."""
    name = "offers/Offer_Matti_Virtanen_matti.virtanen@example-firm.fi.txt"
    (page,) = text_file(b"Asiakas: Matti Virtanen\nTarjous 12 kpl")
    found = text_source(name, "text file", [page], whole=True)
    assert found is not None
    listed = listed_piece("cad/House_matti@example.fi.dwg", "DWG drawing", "no reader")
    every = "\n".join([*(piece.text for piece in found.pieces), listed.text])
    assert "@" not in every and "example" not in every
    assert found.pieces[0].text.startswith("text file. Offer Matti Virtanen. Asiakas")
    assert listed.text == "DWG drawing. House. Its content is not read: no reader."


def test_a_first_line_longer_than_the_cap_is_cut_hard_at_a_word_end() -> None:
    """S1: a text layer with no line ends: the cap cuts the line, not the whole file."""
    found = text_source("long.pdf", "text document", [PageText(1, "word " * 50_000, False)], True)
    assert found is not None and found.cut and found.pages == 1
    assert TEXT_CHARS - 5 <= found.chars <= TEXT_CHARS
    texts = [piece.text for piece in found.pieces if piece.part == "text"]
    assert texts and all(text.split()[-1] == "word" for text in texts)
    assert found.pieces[0].text.startswith("text document. long. word word")
    # no space at all: cut at the cap itself (short runs: contacts.py's e-mail rule is slow on one
    # long run of word characters)
    flat = PageText(1, "abcdefghi," * 25_000, False)
    spaceless = text_source("x.pdf", "text document", [flat], True)
    assert spaceless is not None and spaceless.chars == TEXT_CHARS


def test_a_home_address_loses_its_house_number_and_postal_code() -> None:
    """S2: raw text follows decision 0010 as descriptions do: a street address keeps its street
    and town, not its house number or postal code; numbers that are not an address stay."""
    text = (
        "Asiakas: Matti Virtanen\nOsoite: Esimerkkitie 12 B 4, 00100 Helsinki\n"
        "Leveränsadress: Storgatan 5, 65100 Vasa\nAnschrift: Hauptstraße 21a, 10115 Berlin\n"
        "Site: 14 Baker Street, London\n604 Wilson Avenue | Menomonie, WI 54751-1234\n"
        "Huone 12 m2, korkeus 2600 mm, 10000 kg\n"
        "Mannerheimintie kulma"
    )
    found = text_source("Esimerkkitie_12.txt", "text file", text_file(text.encode()), True)
    assert found is not None
    every = "\n".join(piece.text for piece in found.pieces)
    for gone in (
        "12 B 4",
        "00100",
        "Storgatan 5",
        "65100",
        "21a",
        "10115",
        "14 Baker",
        "604",
        "54751",
    ):
        assert gone not in every, gone
    for kept in ("Osoite: Esimerkkitie, Helsinki", "Storgatan, Vasa", "Hauptstraße, Berlin",
                 "Site: Baker Street, London", "Wilson Avenue | Menomonie, WI\n",
                 "Huone 12 m2, korkeus 2600 mm, 10000 kg", "Mannerheimintie kulma",
                 "text file. Esimerkkitie."):  # fmt: skip
        assert kept in every, kept


def test_a_long_drawn_page_is_not_a_source() -> None:
    """S3 (F2): a drawn page with a title block of notes (200+ characters) is still drawn."""
    sheet = drawn_page()
    for at in range(6):
        sheet.text(f"Note {at}. {LINE}", 20, 320 + 10 * at, size=6)
    pages = pdf_pages(joined(sheet, text_page("General notes.")))
    assert pages[0].drawn and len(pages[0].text.strip()) >= 200
    found = text_source("set/house.pdf", "text document", pages, whole=False)
    assert found is not None and {piece.page for piece in found.pieces[1:]} == {2}
    assert not any("Note 0." in piece.text for piece in found.pieces)


def test_pages_past_the_cap_and_pages_that_do_not_load_are_left_out(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """S3 (F11, F12): the probe's page cap (MAX_PAGES + 1), and a page that doesn't load is
    skipped, not raised."""
    pages = pdf_pages(joined(*(text_page(f"Page {n}.", lines=1) for n in range(MAX_PAGES + 3))))
    assert [page.number for page in pages] == list(range(1, MAX_PAGES + 2))
    real = file_text._page  # pyright: ignore[reportPrivateUsage]

    def page(document: pypdfium2.PdfDocument, number: int) -> pypdfium2.PdfPage:
        if number == 2:
            raise _PageNotLoadedError(2, pypdfium2.PdfiumError("broken"))
        return real(document, number)

    monkeypatch.setattr(file_text, "_page", page)
    found = pdf_pages(joined(text_page("One."), text_page("Two."), text_page("Three.")))
    assert [page.number for page in found] == [1, 3]


def test_crlf_and_blank_lines_are_not_kept_and_the_summary_ends_at_a_word() -> None:
    """S3 (F13, F14) and N2 (F7): pdfium's line ends, a lone CR, blank lines (not counted), a
    301-character first line."""
    first = ("abcd " * 61)[:301]
    text = f"{first}\r\n\r\n  \r\nMiddle.\rEnd."
    found = text_source("a.txt", "text file", [PageText(1, text, False)], True)
    assert found is not None
    texts = "\n".join(piece.text for piece in found.pieces if piece.part == "text")
    assert "\r" not in texts and texts.endswith("\nMiddle.\nEnd.")
    assert found.chars == len(first.rstrip()) + len("\nMiddle.\nEnd.")
    assert found.pieces[0].text == "text file. a. " + " ".join(["abcd"] * 60)


def test_a_utf16_text_file_with_a_bom_is_decoded() -> None:
    """N3: a Windows "Unicode" .txt (UTF-16 with its BOM), either byte order."""
    for data in ("Kylpyhuone 4,5 m²".encode("utf-16"), b"\xfe\xff" + "Sauna".encode("utf-16-be")):
        (page,) = text_file(data)
        assert "\x00" not in page.text and page.text in ("Kylpyhuone 4,5 m²", "Sauna")

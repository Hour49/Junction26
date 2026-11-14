"""The text of a file for the evidence index's `text` sources (app/core/evidence/file_sources.py):
a PDF's text layer page by page, with whether the probe counts the page as drawn (its own rule,
`archive/probe.py` `_page_kind`), up to the probe's page cap; a text file as one page. Nothing is
OCR'd. A PDF that does not open gives no pages; a page that does not load is left out."""

import pypdfium2

from app.adapters.archive.probe import (
    MAX_PAGES,
    _page,  # pyright: ignore[reportPrivateUsage]
    _page_kind,  # pyright: ignore[reportPrivateUsage]
    _PageNotLoadedError,  # pyright: ignore[reportPrivateUsage]
)
from app.adapters.pdfium_lock import PDFIUM
from app.core.evidence.file_sources import PageText


def pdf_pages(data: bytes) -> list[PageText]:
    """Every page up to the probe's cap (MAX_PAGES + 1), in order."""
    with PDFIUM:  # pdfium is not thread-safe (app/adapters/pdfium_lock.py)
        try:
            document = pypdfium2.PdfDocument(data)
        except pypdfium2.PdfiumError:
            return []
        try:
            count = len(document)
            found: list[PageText] = []
            for number in range(1, min(count, MAX_PAGES + 1) + 1):
                try:
                    page = _page(document, number)
                    drawn = _page_kind(page, f"page {number} of {count}")[2]
                    text = page.get_textpage().get_text_range()
                except (_PageNotLoadedError, pypdfium2.PdfiumError):
                    continue
                found.append(PageText(number=number, text=text, drawn=drawn))
            return found
        finally:
            document.close()


def text_file(data: bytes) -> list[PageText]:
    """A text file as one page: UTF-8 (a BOM dropped), else Latin-1, which decodes any bytes."""
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = data.decode("latin-1")
    return [PageText(number=1, text=text, drawn=False)]

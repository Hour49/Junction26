"""The evidence index's sources that no model reads (rag's contract, .agents/exp/rag-evidence.md
7.1 and 7.4; the interface agreed in .agents/exp/rag-evidence-build.md, "BB interface"):

- `text`: a text document (`pdf_text`, `text`) is searched by its own text, every page that has
  some; a drawn or scanned PDF by its own text pages too, those the probe does not count as drawn
  and that hold `TEXT_PAGE_CHARS` characters or more. Phone numbers and e-mail addresses are taken
  out first (`without_contacts`, as descriptions are), then the file is cut at `TEXT_CHARS`, at a
  page or line end. One summary passage, then `text-1..n`, each page packed at line ends into
  passages of at most `PASSAGE_CHARS`, never across a page.
- `listed`: a file nothing reads (DWG, office, archive, encrypted PDF, unknown, refused, IFC) is
  one summary passage that names it and says why its content is not read.

Pure: the caller reads the bytes (app/adapters/evidence/file_text.py) and decides which files and
pages to give, and the kind words."""

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Literal

from app.core.contacts import without_contacts
from app.core.evidence.chunks import PASSAGE_CHARS, pack

TEXT_CHARS = 200_000  # per file, cut at a page or line end
TEXT_PAGE_CHARS = 200  # a text page inside a drawn PDF counts from this many characters
SUMMARY_CHARS = 300  # of the text, in the summary passage


@dataclass(frozen=True)
class PageText:
    """One page's text as read (app/adapters/evidence/file_text.py)."""

    number: int  # 1-based PDF page (1 for a text file)
    text: str  # the page's text layer, as is
    drawn: bool  # what the probe counts as drawn; False for a text file


@dataclass(frozen=True)
class Piece:
    """One passage of a `text` or `listed` source, before it is a `Passage`."""

    part: Literal["summary", "text"]
    n: int  # 1 for the summary; text-1..n
    page: int  # the PDF page it comes from (1 for the summary and a text file)
    text: str


@dataclass(frozen=True)
class TextSource:
    pieces: list[Piece]  # summary first, then text-1..n (never across a page)
    pages: int  # pages that gave text
    chars: int  # characters indexed, after the cut
    cut: bool  # True when TEXT_CHARS cut it


def name_words(path: str) -> str:
    """The file name without folders and extension, `_` and `-` as spaces: the source's subject."""
    stem = PurePosixPath(path.replace("\\", "/")).stem
    return " ".join(stem.replace("_", " ").replace("-", " ").split())


def text_source(
    path: str, kind_words: str, pages: Sequence[PageText], whole: bool
) -> TextSource | None:
    """The `text` source of a file, from its pages in order. `whole` (pdf_text, text): every page
    with text; else (a drawn or scanned PDF) only the pages not drawn with at least
    TEXT_PAGE_CHARS characters. None when no page qualifies."""
    kept: list[tuple[int, str]] = []
    for page in pages:
        if not whole and (page.drawn or len(page.text.strip()) < TEXT_PAGE_CHARS):
            continue
        text = without_contacts(_lines(page.text)).strip()
        if text:
            kept.append((page.number, text))
    if not kept:
        return None
    kept, cut = _capped(kept)
    whole_text = "\n".join(text for _, text in kept)
    summary = f"{kind_words}. {name_words(path)}. {_first(whole_text)}"
    pieces = [Piece(part="summary", n=1, page=1, text=summary)]
    for number, text in kept:
        for passage in pack(text.split("\n"), "\n", PASSAGE_CHARS):
            pieces.append(Piece(part="text", n=len(pieces), page=number, text=passage))
    chars = sum(len(text) for _, text in kept)
    return TextSource(pieces=pieces, pages=len(kept), chars=chars, cut=cut)


def listed_piece(path: str, kind_words: str, reason: str) -> Piece:
    """The one passage of a file whose content is not read."""
    why = reason.strip().rstrip(".")
    text = f"{kind_words}. {name_words(path)}. Its content is not read: {why}."
    return Piece(part="summary", n=1, page=1, text=text)


def _lines(text: str) -> str:
    """Line ends as `\\n` (pdfium gives `\\r\\n`), no blank-only lines."""
    lines = (line.rstrip() for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"))
    return "\n".join(line for line in lines if line.strip())


def _capped(pages: list[tuple[int, str]]) -> tuple[list[tuple[int, str]], bool]:
    """The pages cut to TEXT_CHARS characters in all, at a page end or else a line end."""
    kept: list[tuple[int, str]] = []
    left = TEXT_CHARS
    for number, text in pages:
        if len(text) <= left:
            kept.append((number, text))
            left -= len(text)
            continue
        lines: list[str] = []
        for line in text.split("\n"):
            if len(line) > left - (1 if lines else 0):
                break
            left -= len(line) + (1 if lines else 0)
            lines.append(line)
        if lines:
            kept.append((number, "\n".join(lines)))
        return kept, True
    return kept, False


def _first(text: str) -> str:
    """The first SUMMARY_CHARS characters on one line, cut at a word end when there is one."""
    flat = " ".join(text.split())
    if len(flat) <= SUMMARY_CHARS:
        return flat
    cut = flat[:SUMMARY_CHARS]
    space = cut.rfind(" ")
    return cut[:space] if space > 0 else cut

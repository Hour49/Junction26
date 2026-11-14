"""The evidence index's sources that no model reads (rag's contract, .agents/exp/rag-evidence.md
7.1 and 7.4; the interface agreed in .agents/exp/rag-evidence-build.md, "BB interface"):

- `text`: a text document (`pdf_text`, `text`) is searched by its own text, every page that has
  some; a drawn or scanned PDF by its own text pages too, those the probe does not count as drawn
  and that hold `TEXT_PAGE_CHARS` characters or more. Phone numbers and e-mail addresses are taken
  out first (`without_contacts`, as descriptions are), and a street address loses its house
  number and postal code (`without_addresses`: decision 0010, as the describer writes a home
  address), then the file is cut at `TEXT_CHARS`, at a page or line end (a line longer than what
  is left is cut at a word end). One summary passage, then `text-1..n`, each page packed at line
  ends into passages of at most `PASSAGE_CHARS`, never across a page.
- `listed`: a file nothing reads (DWG, office, archive, encrypted PDF, unknown, refused, IFC) is
  one summary passage that names it and says why its content is not read.

The file name in a passage goes through the same contact and address rules as the text.

Pure: the caller reads the bytes (app/adapters/evidence/file_text.py) and decides which files and
pages to give, and the kind words."""

import re
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Literal

from app.core.contacts import without_contacts
from app.core.evidence.chunks import PASSAGE_CHARS, pack

TEXT_CHARS = 200_000  # per file, cut at a page or line end
TEXT_PAGE_CHARS = 200  # a text page inside a drawn PDF counts from this many characters
SUMMARY_CHARS = 300  # of the text, in the summary passage

# A street address in fi, sv, de or en (decision 0010: a home address keeps its street and town,
# not its house number or postal code). A regex can't tell a home from a firm, so every street
# address found is cut the same way; a number that does not follow a street word stays.
_STREET = (
    r"[A-ZÅÄÖÜ][\w-]*(?:tie|katu|kuja|polku|kaari|väylä|raitti|rinne|ranta|tori|aukio|vägen|"
    r"gatan|gränd|stigen|straße|strasse|gasse|allee)"
)
# German -platz and -weg are everyday compounds (Parkplatz 12, Fluchtweg 2: codecheck r9), so
# they count as a street only with a postal code and town right after the number
_STREET_IF_POSTAL = r"[A-ZÅÄÖÜ][\w-]*(?:platz|weg)"
_HOUSE = (  # 12, 12a, 12 B 4, 12-14, 12 as 4
    r"\d{1,4}(?:[ \t]?[a-zA-Z]\b)?(?:[ \t]*[-\u2013][ \t]*\d{1,4})?"
    r"(?:[ \t]+(?:as[ \t]+)?\d{1,3})?\b"
)
# a postal code (fi/de/fr 5 digits, CH/AT 4, sv "114 51") before a town: not before a 2-3 letter
# all-caps word such as CHF, EUR or MM
_CODE = r"(?:(?:[A-Z]{1,2}-)?\d{4,5}|\d{3}[ \t]\d{2})"
_TOWN = r"(?=[ \t]+(?![A-Z]{2,3}\b)[A-ZÅÄÖÜ])"
_STREET_NUMBER = re.compile(
    rf"\b({_STREET})[ \t]+{_HOUSE}"
    rf"|\b({_STREET_IF_POSTAL})[ \t]+{_HOUSE}(?=,?[ \t]*{_CODE}{_TOWN})"
)
# "14 Baker Street", "1021 HIGH ST", "220 W 5th Ave.": a number, one to three capitalised (or
# all-caps) words or an ordinal, then a street word or its abbreviation, in any case
_ENGLISH_STREET = re.compile(
    r"\b\d{1,5}[a-zA-Z]?[ \t]+"
    r"((?:(?:[A-Z][A-Za-z']*|\d{1,3}(?:st|nd|rd|th|ST|ND|RD|TH))[ \t]+){1,3}"
    r"(?i:street|st|road|rd|avenue|ave|lane|ln|drive|dr|boulevard|blvd|way|highway|hwy|"
    r"parkway|pkwy|court|place|square|crescent|close|terrace)\b\.?)"
    r"(?![ \t]+[a-z])"  # "15 Min Drive from the station", "2 Fire Exit Way signs" are not one
)
_ZIP = re.compile(r"\b([A-Z]{2})[ \t]+\d{5}(?:-\d{4})?\b")  # "WI 54751": a US state and ZIP
_POSTAL_CODE = re.compile(rf"(,?[ \t]*){_CODE}{_TOWN}")


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
    """The file name without folders and extension, `_` and `-` as spaces: the source's subject,
    with its contacts and house numbers taken out as the text's are."""
    stem = PurePosixPath(path.replace("\\", "/")).stem
    scrubbed = without_addresses(without_contacts(" ".join(stem.replace("_", " ").split())))
    return " ".join(scrubbed.replace("-", " ").split())


def without_addresses(text: str) -> str:
    """`text` with each street address's house number taken out, and only on a line that has one,
    a postal code before a town name ("Esimerkkitie 12 B 4, 00100 Helsinki" -> "Esimerkkitie,
    Helsinki"; "Bahnhofstrasse 12, CH-8001 Zürich" -> "Bahnhofstrasse, Zürich"). Line by line, as
    `without_contacts`."""
    out: list[str] = []
    for line in text.split("\n"):
        found = _STREET_NUMBER.sub(lambda match: match.group(1) or match.group(2), line)
        found = _ENGLISH_STREET.sub(r"\1", found)
        if found != line:
            found = _POSTAL_CODE.sub(lambda match: ", " if "," in match.group(1) else " ", found)
            found = _ZIP.sub(r"\1", found)
            found = re.sub(r"[ \t]*,[ \t]*,", ",", re.sub(r"[ \t]{2,}", " ", found)).strip()
        out.append(found)
    return "\n".join(out)


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
        text = without_addresses(without_contacts(_lines(page.text))).strip()
        if text:
            kept.append((page.number, text))
    kept, cut = _capped(kept)
    if not kept:
        return None
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
    """The pages cut to TEXT_CHARS characters in all, at a page end or else a line end; a line
    longer than what is left, with nothing before it on its page, is cut at a word end."""
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
                if not lines and (part := _word_cut(line, left)):
                    lines.append(part)
                break
            left -= len(line) + (1 if lines else 0)
            lines.append(line)
        if lines:
            kept.append((number, "\n".join(lines)))
        return kept, True
    return kept, False


def _first(text: str) -> str:
    """The first SUMMARY_CHARS characters on one line, cut at a word end when there is one."""
    return _word_cut(" ".join(text.split()), SUMMARY_CHARS)


def _word_cut(text: str, chars: int) -> str:
    """`text` cut to `chars` characters, at a word end when there is one."""
    if len(text) <= chars:
        return text
    cut = text[:chars]
    space = cut.rfind(" ")
    return (cut[:space] if space > 0 else cut).rstrip()

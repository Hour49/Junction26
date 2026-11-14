"""Pure parts of an evidence search (decision 0012, contract v1): passage ids, a ranking of
passages as a ranking of files, a query's words, the ones a passage holds, and its snippet."""

import re
from collections.abc import Iterable, Sequence

from app.core.evidence.model import PartName, Passage

ID = re.compile(r"(f[0-9]{1,6})(?:-(summary)|-(detail|visible_text)-([1-9][0-9]{0,3}))?")
SNIPPET = 300
WORD = re.compile(r"[^\W_]{2,}")  # a word: two letters or digits or more
# words too common to say why a passage matched (English, the descriptions' language)
COMMON = frozenset(
    [
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "by",
        "for",
        "from",
        "has",
        "have",
        "in",
        "is",
        "it",
        "its",
        "of",
        "on",
        "or",
        "that",
        "the",
        "there",
        "this",
        "to",
        "was",
        "what",
        "which",
        "with",
        "any",
        "some",
    ]
)


def passage_id(file_id: str, passage: Passage) -> str:
    """`f7-summary`, `f7-detail-2`, `f7-visible_text-1`."""
    if passage.part == "summary":
        return f"{file_id}-summary"
    return f"{file_id}-{passage.part}-{passage.n}"


def parsed(found: str) -> tuple[str, PartName, int] | None:
    """A passage id, or a file id (its summary), as (file id, part, n); None for anything else."""
    match = ID.fullmatch(found.strip())
    if match is None:
        return None
    if match[3] is not None:
        part: PartName = "detail" if match[3] == "detail" else "visible_text"
        return match[1], part, int(match[4])
    return match[1], "summary", 1


def file_of(found: str) -> str:
    return found.split("-", 1)[0]


def first_per_file(ranking: Iterable[str], limit: int) -> list[tuple[str, str]]:
    """A ranking of passage ids as the first `limit` files, each with its best passage."""
    best: dict[str, str] = {}
    for found in ranking:
        if len(best) == limit:
            break
        best.setdefault(file_of(found), found)
    return list(best.items())


def words(text: str) -> list[str]:
    return list(dict.fromkeys(WORD.findall(text.lower())))


def terms(query: str, text: str) -> tuple[str, ...]:
    """The query's words (common ones left out) that the passage holds as words."""
    held = set(words(text))
    return tuple(word for word in words(query) if word in held and word not in COMMON)


def snippet(text: str, found: Sequence[str], size: int = SNIPPET) -> str:
    """At most `size` characters of `text`, from a little before the first matched word when
    there is one, cut at word ends, with "..." where text is left out."""
    text = " ".join(text.split())
    if len(text) <= size:
        return text
    starts = [
        match.start()
        for word in found
        if (match := re.search(rf"\b{re.escape(word)}\b", text, re.IGNORECASE)) is not None
    ]
    start = max(0, min(starts) - size // 3) if starts else 0
    if start > 0:
        start = text.find(" ", start) + 1 or start
    lead = "..." if start > 0 else ""
    room = size - len(lead)
    if start + room >= len(text):
        return lead + text[start:]
    piece = text[start : start + room - 3]
    if " " in piece:
        piece = piece[: piece.rfind(" ")]
    return lead + piece + "..."

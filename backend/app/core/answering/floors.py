"""Floors named in words ("on the second floor", "1st floor", "floor 2", "Level 1"), in a
question and in a drawing's storey names, read as a floor number so the two can be matched: a
question's "first floor" is the storey printed FIRST FLOOR, "1st Floor" or "Level 1", whatever
the spelling. Only the number is compared; which floor a number means (ground floor or the one
above it) is the drawing's own word, never guessed (fable-rooms r10 items 10 and 11)."""

import re
from collections.abc import Sequence

ORDINALS = {
    "ground": 0, "first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5, "sixth": 6,
    "seventh": 7, "eighth": 8, "ninth": 9, "tenth": 10,
}  # fmt: skip
_LEVEL = r"(?:floor|storey|story|level)"
FLOOR = re.compile(
    rf"\b(?:(?P<word>{'|'.join(ORDINALS)})|(?P<nth>\d+)(?:st|nd|rd|th)\.?)[ -]+{_LEVEL}\b"
    # the sign stays: "Level -1" is a basement, not floor 1 (review-352 B1); a hyphen glued
    # between the word and the number ("LEVEL-1") may be either, so it names no floor (N5)
    rf"|\b{_LEVEL}(?:(?P<glued>-)|\s*)(?P<num>(?:(?<=\s)-|\u2212)?\d+)\b(?![.,]\d)",
    re.IGNORECASE,
)
# the floor with the words that put a question on it ("on the second floor")
FLOOR_AT = re.compile(
    rf"(?:\b(?:on|in|at|of|for)\s+(?:the\s+)?)?(?:{FLOOR.pattern})", re.IGNORECASE
)


# Words that make a text name several floors ("2nd~5th Floor Plan", "GROUND & FIRST FLOOR PLANS",
# "LEVEL 1 & 2", "1-2") or only part of one ("Enlarged First Floor Plan (West)", "1st Floor Plan -
# Option 2"): such a caption or title names no storey (review-352 B2)
SEVERAL = re.compile(r"[&~\uff5e,/+]|\b(?:and|to|through|thru)\b|\d\s*-\s*\d", re.IGNORECASE)
PART = re.compile(
    r"\b(?:enlarged|partial|part|option|alternative|alternate|alt|scheme|typical|detail)\b",
    re.IGNORECASE,
)


def floor_number(match: re.Match[str]) -> int:
    if word := match.group("word"):
        return ORDINALS[word.casefold()]
    return int((match.group("nth") or match.group("num")).replace("\u2212", "-"))


def glued(match: re.Match[str]) -> bool:
    """ "LEVEL-1": level 1 or level -1, the text can't tell (review-352 N5)."""
    return match.group("glued") is not None


def glued_floors(text: str | None) -> set[int]:
    """Both readings of each glued floor in `text` ("LEVEL-1": 1 and -1)."""
    found = (floor_number(match) for match in FLOOR.finditer(text or "") if glued(match))
    return {sign * number for number in found for sign in (1, -1)}


def floor_of(text: str | None) -> int | None:
    """The floor number a storey name names, None when it names none, or several (two numbers,
    a list or a range: SEVERAL)."""
    if SEVERAL.search(text or "") or glued_floors(text):
        return None
    found = {floor_number(match) for match in FLOOR.finditer(text or "")}
    return found.pop() if len(found) == 1 else None


def floor_name(text: str | None) -> str | None:
    """The floor as printed ("FIRST FLOOR" of "FIRST FLOOR PLAN"), when a plan's caption or a
    sheet's title names exactly one whole floor: not several, not an enlarged, partial or option
    plan of one (PART)."""
    if floor_of(text) is None or PART.search(text or ""):
        return None
    match = FLOOR.search(text or "")
    return None if match is None else match.group()


# A floor named by a word, not a number ("the attic floor", "the loft", "the upper floor"), and
# the storey names that are that floor: "How many rooms are on the attic floor?" counted the whole
# FZK-Haus model (7) and its Erdgeschoss plan (6), as "attic" named no floor (samples-curate
# 2026-11-15). Such a floor is the one storey of that name, else none: never the whole sheet.
STOREY_WORD = re.compile(
    rf"\b(?P<storey_word>attic|loft|upper|basement|cellar)(?:\s+{_LEVEL})?\b", re.IGNORECASE
)
STOREY_WORD_AT = re.compile(
    rf"(?:\b(?:on|in|at|of|for)\s+(?:the\s+)?)?(?:{STOREY_WORD.pattern})", re.IGNORECASE
)
_ATTIC = r"dachgeschoss|\bdg\b|attic|loft"
_BASEMENT = r"basement|cellar|keller|untergeschoss|\bug\b"
_WORD_STOREYS = {
    "attic": _ATTIC, "loft": _ATTIC, "upper": r"obergeschoss|\bog\b|upper",
    "basement": _BASEMENT, "cellar": _BASEMENT,
}  # fmt: skip


def word_storeys(word: re.Match[str], storeys: Sequence[str]) -> list[str]:
    """The storeys (by name) a STOREY_WORD match names: "attic" is Dachgeschoss or DG."""
    pattern = _WORD_STOREYS[word.group("storey_word").casefold()]
    return [storey for storey in storeys if re.search(pattern, storey, re.IGNORECASE)]

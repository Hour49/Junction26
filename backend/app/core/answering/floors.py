"""Floors named in words ("on the second floor", "1st floor", "floor 2", "Level 1"), in a
question and in a drawing's storey names, read as a floor number so the two can be matched: a
question's "first floor" is the storey printed FIRST FLOOR, "1st Floor" or "Level 1", whatever
the spelling. Only the number is compared; which floor a number means (ground floor or the one
above it) is the drawing's own word, never guessed (fable-rooms r10 items 10 and 11)."""

import re

ORDINALS = {
    "ground": 0, "first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5, "sixth": 6,
    "seventh": 7, "eighth": 8, "ninth": 9, "tenth": 10,
}  # fmt: skip
_LEVEL = r"(?:floor|storey|story|level)"
FLOOR = re.compile(
    rf"\b(?:(?P<word>{'|'.join(ORDINALS)})|(?P<nth>\d+)(?:st|nd|rd|th)\.?)[ -]+{_LEVEL}\b"
    rf"|\b{_LEVEL}[ -]*(?P<num>\d+)\b(?![.,]\d)",
    re.IGNORECASE,
)
# the floor with the words that put a question on it ("on the second floor")
FLOOR_AT = re.compile(
    rf"(?:\b(?:on|in|at|of|for)\s+(?:the\s+)?)?(?:{FLOOR.pattern})", re.IGNORECASE
)


def floor_number(match: re.Match[str]) -> int:
    if word := match.group("word"):
        return ORDINALS[word.casefold()]
    return int(match.group("nth") or match.group("num"))


def floor_of(text: str | None) -> int | None:
    """The floor number the text names, None when it names none or two different ones."""
    found = {floor_number(match) for match in FLOOR.finditer(text or "")}
    return found.pop() if len(found) == 1 else None


def floor_name(text: str | None) -> str | None:
    """The floor as printed ("FIRST FLOOR" of "FIRST FLOOR PLAN"), when the text names one."""
    if floor_of(text) is None:
        return None
    match = FLOOR.search(text or "")
    return None if match is None else match.group()

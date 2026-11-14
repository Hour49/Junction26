"""Contact data taken out of text the app shows or indexes (decision 0010 section 8; orchestrator,
2026-11-14: "drop every phone number and e-mail address from visible_text and detail with a tested
regex, firm or private"): every e-mail address and phone number found. Pure text rules, so the
describer (app/adapters/triage/gemini_describer.py) and the evidence index (app/core/evidence) use
the same one. A national number with no label, no "+" or "00" and no area-code dash (0401234567) is
not caught: it cannot be told from a row of dimensions."""

import re

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
# a phone or fax label (fi, sv, de, en, fr), "T." and "P." with their dot and a space (T.01.1930
# is a date), and what may follow it
_LABEL = (
    r"(?:\b(?:puh(?:elin)?|matkapuh(?:elin)?|t[eé]l(?:efon|ephone|éphone|efax)?|phone|ph|fax|"
    r"faksi|telefax|gsm|mob(?:il|ile)?|tfn|tlf)\b\.?|\b[tp]\.(?=[ \t]))"
    r"[ \t]*(?:n[or]o?\.?[ \t]*)?:?[ \t]*"
)
_NUMBER = r"\+?\(?\d[\d \t()/.-]*\d"
_LABELLED = re.compile(_LABEL + _NUMBER, re.IGNORECASE)
_LABEL_AT_END = re.compile(_LABEL + "$", re.IGNORECASE)  # its number on the next line
_NUMBER_AT_START = re.compile(r"^[ \t]*" + _NUMBER)
# a country code after "+" or "00", an area code, then groups of 2-4 digits
_GROUPS = r"\d{1,3}[ \t.-]?\(?\d{1,4}\)?(?:[ \t.-]?\d{2,4}){1,5}"
_PLUS = re.compile(r"(?<![\w+])\+" + _GROUPS)
_DOUBLE_ZERO = re.compile(r"(?<![\w+])00" + _GROUPS)
# "09-123 4567", "019-123456": a 0 area code, a dash, one or two groups, nothing numeric after
_AREA_CODE = re.compile(
    r"(?<![\w.,/+-])0\d{1,3}-[ \t]?(?:\d{5,7}|\d{3,4}[ \t]\d{2,4})(?![\w/-]|[.,]\d|[ \t]+\d)"
)
# "(555) 123-4567", "555-123-4567"
_NORTH_AMERICAN = re.compile(
    r"(?<![\w.,/+-])(?:\(\d{3}\)[ \t]?|\d{3}-)\d{3}-\d{4}(?![\w/-]|[.,]\d)"
)
CONTACTS: tuple[tuple[re.Pattern[str], int], ...] = (
    (_EMAIL, 0),
    (_LABELLED, 5),  # "PUH 651088", "Tel. (09) 123 456", "T. 09 123 4567"
    (_PLUS, 8),  # "+358 9 123 4567", never a level such as "+108.65"
    (_DOUBLE_ZERO, 10),  # "0049 30 1234567", never a postal code such as "00130"
    (_AREA_CODE, 7),
    (_NORTH_AMERICAN, 10),
)


def without_contacts(text: str) -> str:
    """`text` with every e-mail address and phone number found taken out, also a number whose
    label ends the line above it. A line left empty goes; the rest of a line stays. A national
    number with no label, no "+" or "00" and no area-code dash is not caught: it cannot be told
    from a row of dimensions."""
    lines = text.split("\n")
    kept = list(lines)
    for at in range(len(kept) - 1):
        label = _LABEL_AT_END.search(kept[at])
        number = _NUMBER_AT_START.match(kept[at + 1])
        if label and number and _digits(number.group(0)) >= 5:
            kept[at], kept[at + 1] = kept[at][: label.start()], kept[at + 1][number.end() :]
    out: list[str] = []
    for line, now in zip(lines, kept, strict=True):
        for pattern, digits in CONTACTS:
            now = pattern.sub(lambda found, n=digits: _drop(found, n), now)
        if now != line:
            now = re.sub(r"[ \t]{2,}", " ", now).strip()
            if not now:
                continue
        out.append(now)
    return "\n".join(out)


def _digits(text: str) -> int:
    return sum(char.isdigit() for char in text)


def _drop(found: re.Match[str], digits: int) -> str:
    said = found.group(0)
    return "" if _digits(said) >= digits else said

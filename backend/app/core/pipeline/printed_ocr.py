"""PRINTED_OCR_CHECK: a second reader of the printed digits the Carbon reader gave.

The numbers that decide a raster sheet's answers come from Carbon (Gemini) reading the sheet: its
printed scale text ("3/32\\" = 1'-0\\"") and its printed facts ("48 DORMS", "26,562 SF"). A misread
fraction is a neighbouring scale and a lost decimal separator is 10x, and nothing else reads those
digits. An OCR engine (PP-OCR, app/adapters/raster_ocr/tiles.py) reads the same places again and
this module compares the two, per value:

- confirmed: OCR reads Carbon's number there (any reading of a separator: "6,095" is 6095 or
  6.095);
- disagrees: OCR reads a comparable number there and none matches. Comparable is the same count
  of digits: a stray "4" beside "914" is a fragment, not a reading, while "12.40" against "1,240"
  is the lost-separator slip;
- not found: anything else. It changes nothing.

Where. A printed fact has Carbon's box: OCR's tokens whose centre lies in it. The scale text has no
box anywhere in Carbon's reply, so the whole sheet's tokens are searched for scale texts; it
disagrees only when OCR finds exactly one scale text of the same family (metric 1:n or imperial)
and it is another ratio: a sheet also prints its details' scales, so two or more is not found.

What a disagreement does (`checked`). The value can no longer decide silently: a printed count
gets a second stage-8 value with OCR's reading (method `annotation`, beside Carbon's
`printed_total` and the drawing's count), so no rule settles the count and a person sees both; an
area or other fact gets a note; a scale text is withheld (as `with_printed` does with a ratio it
cannot use) and the estimate from the doors stays. When nothing disagrees the sheet is unchanged.
Thresholds were set on T2 (us_daf dorm p003, 20 facts: every number read right, stray tokens "4
SF", "二"); the measured run is in the PR (task 7, accuracy round 2026-11-15).
"""

import re
from collections.abc import Sequence
from typing import Literal

from pydantic import Field

from app.core.drawing.model import Box
from app.core.model import Frozen
from app.core.pipeline.model import Measurement
from app.core.pipeline.printed import (
    PrintedFact,
    PrintedSheet,
    fact_measurements,
    imperial_scales,
    ratio_of,
)

Outcome = Literal["confirmed", "disagrees", "not_found"]
RATIO_TOLERANCE = 0.005  # two ratios this close are one scale (float noise, never a slip)


class OcrToken(Frozen):
    """One text box the OCR engine read: its text and its box in page fractions."""

    text: str
    box: Box
    page: int = Field(default=1, ge=1)
    score: float = 1.0


class Confirmation(Frozen):
    """What OCR said about one Carbon value: `printed` as Carbon gave it, `read` OCR's reading
    when it disagrees, `index` the fact's place in `printed_facts`."""

    kind: Literal["scale_text", "fact"]
    printed: str
    outcome: Outcome
    read: str | None = None
    index: int | None = None


class Number(Frozen):
    """A number as printed, its digits, and every value its separators can mean."""

    text: str
    digits: str
    values: frozenset[float]


# O for 0 and l, I, | for 1 next to a digit: the recogniser's usual slips on digits
_ZERO = re.compile(r"(?<=\d)[Oo]|[Oo](?=\d)")
_ONE = re.compile(r"(?<=\d)[lI|]|[lI|](?=\d)")
# a number: digits joined by a comma or point, or by a space before a group of three ("26 562")
_NUMBER = re.compile(r"(?<![\d.,])\d+(?:[,.]\d+|[ \u00a0\u202f]\d{3}(?!\d))*")


def numbers_in(text: str) -> list[Number]:
    """Every number `text` prints. "6,095" is 6095 or 6.095 (a three-digit group can be either),
    "12,45" only 12.45, "1.240,5" 1240.5, "26 562" 26562."""
    plain = _ONE.sub("1", _ZERO.sub("0", text))
    return [n for m in _NUMBER.finditer(plain) if (n := _number(m.group(0))) is not None]


def _number(text: str) -> Number | None:
    parts = re.split(r"[ ,.\u00a0\u202f]", text)
    digits = "".join(parts)
    values: set[float] = set()
    if all(len(p) == 3 for p in parts[1:]):
        values.add(float(digits))  # one number, or every group of three: thousands
    if (
        len(parts) >= 2
        and all(len(p) == 3 for p in parts[1:-1])
        and text[-len(parts[-1]) - 1] in ",."
    ):
        values.add(float("".join(parts[:-1]) + "." + parts[-1]))  # the last separator: decimal
    return Number(text=text, digits=digits, values=frozenset(values)) if values else None


def confirm_printed(printed: PrintedSheet, tokens: Sequence[OcrToken]) -> list[Confirmation]:
    """What OCR's `tokens` say about each of Carbon's printed values: each fact with a box, and
    the scale text when it states a ratio. A fact without a box is not checked."""
    out: list[Confirmation] = []
    if ratio_of(printed.printed_scale) is not None and printed.printed_scale is not None:
        out.append(_scale(printed.printed_scale, tokens))
    for index, fact in enumerate(printed.printed_facts):
        if fact.box is not None:
            out.append(_fact(index, fact, fact.box, tokens))
    return out


def _fact(index: int, fact: PrintedFact, box: Box, tokens: Sequence[OcrToken]) -> Confirmation:
    said = numbers_in(fact.text)
    # Carbon's number: the one its text prints at its value, else (a converted unit, ft2 to m2)
    # its longest one
    carbon = next((n for n in said if fact.value in n.values), None) or max(
        said, key=lambda n: len(n.digits), default=None
    )
    if carbon is None:
        return Confirmation(kind="fact", printed=fact.text, outcome="not_found", index=index)
    there = [
        n for t in tokens if t.page == fact.page and _inside(t.box, box) for n in numbers_in(t.text)
    ]
    if any(carbon.values & n.values for n in there):
        return Confirmation(kind="fact", printed=fact.text, outcome="confirmed", index=index)
    other = next((n for n in there if len(n.digits) == len(carbon.digits)), None)
    if other is None:
        return Confirmation(kind="fact", printed=fact.text, outcome="not_found", index=index)
    return Confirmation(
        kind="fact", printed=fact.text, outcome="disagrees", read=other.text, index=index
    )


def _inside(token: Box, box: Box) -> bool:
    x, y = (token[0] + token[2]) / 2, (token[1] + token[3]) / 2
    return box[0] <= x <= box[2] and box[1] <= y <= box[3]


def _scales(text: str) -> list[tuple[float, str, bool]]:
    """The scale texts a token prints: (ratio, as printed, imperial)."""
    found = [(ratio, shown, True) for ratio, shown in imperial_scales(text)]
    if not found and (ratio := ratio_of(text)) is not None:
        found.append((ratio, text.strip(), False))
    return found


def _scale(scale: str, tokens: Sequence[OcrToken]) -> Confirmation:
    ratio = ratio_of(scale)
    assert ratio is not None
    imperial = bool(imperial_scales(scale))
    seen = [s for t in tokens for s in _scales(t.text) if s[2] == imperial]
    if any(abs(r - ratio) <= RATIO_TOLERANCE * ratio for r, _, _ in seen):
        return Confirmation(kind="scale_text", printed=scale, outcome="confirmed")
    others = {round(r, 3): shown for r, shown, _ in seen}
    if len(others) != 1:
        return Confirmation(kind="scale_text", printed=scale, outcome="not_found")
    [shown] = others.values()
    return Confirmation(kind="scale_text", printed=scale, outcome="disagrees", read=shown)


def checked(
    printed: PrintedSheet, confirmations: Sequence[Confirmation]
) -> tuple[PrintedSheet, list[Measurement]]:
    """`printed` with what OCR disagrees with: a scale text withheld, a note for every fact, and
    for a printed count a second stage-8 value with OCR's reading (method `annotation`). The
    sheet unchanged, and no values, when nothing disagrees."""
    notes = list(printed.notes)
    extra: list[Measurement] = []
    scale = printed.printed_scale
    for c in confirmations:
        if c.outcome != "disagrees" or c.read is None:
            continue
        if c.kind == "scale_text":
            scale = None
            notes.append(
                f"printed scale {c.printed}: OCR reads {c.read} there: not used, "
                "left for a person to check"
            )
            continue
        assert c.index is not None
        fact = printed.printed_facts[c.index]
        notes.append(f"printed on the sheet: {fact.text}: OCR reads {c.read} there")
        read = next((n for n in numbers_in(c.read)), None)
        if fact.unit == "count" and read is not None and len(read.values) == 1:
            [value] = read.values
            extra += [
                m.model_copy(update={"value": m.value.model_copy(update={"method": "annotation"})})
                for m in fact_measurements([fact.model_copy(update={"value": value})])
            ]
    if scale == printed.printed_scale and len(notes) == len(printed.notes):
        return printed, []
    return printed.model_copy(update={"printed_scale": scale, "notes": tuple(notes)}), extra

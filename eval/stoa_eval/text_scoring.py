"""Free-text golden questions scored by curated claims (D52, review-7's proposal; golden-8 brief).

The headline still judges text by exact match (scoring.judge). This adds its own line: each golden
text question with a line in part2_answering/text_claims.jsonl passes when the answer text states
every claimed number and contains every claimed name.

- Numbers: the answer's numbers are read with their units (`mentions`): feet and inches (6'-2 1/2",
  8 ft 3 1/4 in), inches with fractions (41 1/2"), a number with a unit word (2318 SF, 2.35 m,
  45 MIN.), and bare
  whole numbers or number words up to twenty as counts. A number glued to letters or a hyphen is a
  code, not a quantity (D7, ST-4, 204.C). Claims and mentions meet in one unit per kind (metres,
  square metres, minutes), are matched one to one (each mention serves one claim), and a measure
  matches within 2% while a count matches exactly. Numbers the answer adds beyond the claims are
  reported, not penalised.
- Names: a name or one of its aliases appears in the answer as whole words, after NFKC, casefolding
  and turning every run of other characters into one space ("ST-4/GL-9" = "st 4 gl 9").
"""

import re
import unicodedata
from collections.abc import Mapping, Sequence
from typing import Literal, NamedTuple

from pydantic import BaseModel, ConfigDict, Field

from .models import FREE_TEXT_TYPES, Answer, GoldenItem, NumberClaim, TextClaims
from .scoring import REL_TOL, Tally

Kind = Literal["count", "length", "area", "time"]
FT, INCH = 0.3048, 0.0254
UNITS: dict[str, tuple[Kind, float]] = {  # claim unit -> kind and factor to metres, m2, minutes
    "count": ("count", 1.0),
    "m": ("length", 1.0),
    "cm": ("length", 0.01),
    "mm": ("length", 0.001),
    "ft": ("length", FT),
    "in": ("length", INCH),
    "m2": ("area", 1.0),
    "ft2": ("area", FT**2),
    "min": ("time", 1.0),
    "h": ("time", 60.0),
}
_WORD_UNITS: tuple[tuple[str, str], ...] = (  # unit words after a number, longest first
    (r"sq\.?\s*ft\.?|s\.?f\.?|ft2|ft²|square\s+f(?:ee|oo)t", "ft2"),
    (r"sq\.?\s*m|m2|m²|square\s+met(?:re|er)s?", "m2"),
    (r"millimet(?:re|er)s?|mm", "mm"),
    (r"centimet(?:re|er)s?|cm", "cm"),
    (r"met(?:re|er)s?|m", "m"),
    (r"feet|foot|ft\.?", "ft"),
    (r"inch(?:es)?|in\.", "in"),
    (r"minutes?|mins?\.?", "min"),
    (r"hours?|hrs?\.?|h", "h"),
)
_NUM = r"\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:[.,]\d+)?"  # 2,318 or 2318 or 2.35 or 2,35
_START = r"(?<![\w.'/-])"  # not glued to a code: D7, ST-4, 5/8 inside a fraction
_FEET_INCHES = re.compile(
    rf"{_START}(?P<ft>{_NUM})\s*'(?![a-z])\s*(?:-\s*)?"
    r"(?:(?P<inch>\d+(?:\.\d+)?)(?:[\s-]+(?P<num>\d+)/(?P<den>\d+))?\s*\"?)?"
)
_FEET_WORD_INCHES = re.compile(  # 8 ft 3 1/4 in, 8 feet 3.25 inches
    rf"{_START}(?P<ft>{_NUM})\s*(?:ft\.?|feet|foot)\s*(?P<inch>\d+(?:\.\d+)?)"
    r"(?:[\s-]+(?P<num>\d+)/(?P<den>\d+))?\s*(?:\"|inch(?:es)?\b|in\b\.?)"
)
_FRACTION_INCHES = re.compile(
    rf"{_START}(?:(?P<whole>\d+)[\s-]+)?(?P<num>\d+)/(?P<den>\d+)\s*(?:\"|inch(?:es)?\b|in\.)"
)
_PLAIN_INCHES = re.compile(rf"{_START}(?P<value>{_NUM})\s*\"")
_WITH_UNIT = re.compile(
    rf"{_START}(?P<value>{_NUM})\s*(?P<unit>"
    + "|".join(f"(?:{pattern})" for pattern, _ in _WORD_UNITS)
    + r")(?![\w²])"
)
_BARE = re.compile(rf"{_START}(?P<value>\d+)(?![\w'\"/]|[.,]\w)")
_NUMBER_NAMES = (
    "zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven",
    "twelve", "thirteen", "fourteen", "fifteen", "sixteen", "seventeen", "eighteen", "nineteen",
    "twenty",
)  # fmt: skip
_NUMBER_WORDS = {word: n for n, word in enumerate(_NUMBER_NAMES)}  # as counts
_NUMBER_WORD = re.compile(r"\b(" + "|".join(_NUMBER_WORDS) + r")\b")


# double prime, curly double quotes and low-9 quote -> "; prime and curly single quotes -> '
_QUOTES = str.maketrans(
    dict.fromkeys("\u2033\u201c\u201d\u201e", '"') | dict.fromkeys("\u2032\u2018\u2019", "'")
)


class Mention(NamedTuple):
    kind: Kind
    value: float  # in metres, square metres, minutes, or a count
    text: str


def _number(text: str) -> float:
    if re.fullmatch(r"\d{1,3}(?:,\d{3})+(?:\.\d+)?", text):
        return float(text.replace(",", ""))
    return float(text.replace(",", "."))


def _unit_of(word: str) -> str:
    for pattern, unit in _WORD_UNITS:
        if re.fullmatch(pattern, word):
            return unit
    raise AssertionError(f"no unit for {word!r}")  # the alternation only matches listed words


def normalise(text: str) -> str:
    """NFKC, casefolded, typographic quotes and primes as ' and "."""
    text = unicodedata.normalize("NFKC", text).casefold()
    return text.translate(_QUOTES)


def mentions(answer: str) -> list[Mention]:
    """The numbers an answer states, with their kind; each piece of text is read once."""
    text = normalise(answer)
    found: list[Mention] = []

    def take(match: re.Match[str], kind: Kind, value: float) -> str:
        found.append(Mention(kind, value, match[0].strip()))
        return " " * len(match[0])  # blank it so a later pattern can't read it again

    def feet_inches(m: re.Match[str]) -> str:
        inches = float(m["inch"] or 0) + (int(m["num"]) / int(m["den"]) if m["num"] else 0)
        return take(m, "length", _number(m["ft"]) * FT + inches * INCH)

    def fraction(m: re.Match[str]) -> str:
        inches = int(m["whole"] or 0) + int(m["num"]) / int(m["den"])
        return take(m, "length", inches * INCH)

    def with_unit(m: re.Match[str]) -> str:
        kind, factor = UNITS[_unit_of(m["unit"])]
        return take(m, kind, _number(m["value"]) * factor)

    text = _FEET_INCHES.sub(feet_inches, text)
    text = _FEET_WORD_INCHES.sub(feet_inches, text)
    text = _FRACTION_INCHES.sub(fraction, text)
    text = _PLAIN_INCHES.sub(lambda m: take(m, "length", _number(m["value"]) * INCH), text)
    text = _WITH_UNIT.sub(with_unit, text)
    text = _BARE.sub(lambda m: take(m, "count", float(m["value"])), text)
    _NUMBER_WORD.sub(lambda m: take(m, "count", float(_NUMBER_WORDS[m[1]])), text)
    return found


def matches(claim: NumberClaim, mention: Mention) -> bool:
    kind, factor = UNITS[claim.unit]
    if kind != mention.kind:
        return False
    want = claim.value * factor
    if kind == "count":
        return mention.value == want
    return abs(mention.value - want) <= REL_TOL * abs(want) * (1 + 1e-9)


def matched_claims(claims: Sequence[NumberClaim], found: Sequence[Mention]) -> int:
    """The most claims that distinct mentions can meet (bipartite matching, augmenting paths)."""
    owner: dict[int, int] = {}  # mention index -> claim index

    def assign(claim: int, seen: set[int]) -> bool:
        for index, mention in enumerate(found):
            if index in seen or not matches(claims[claim], mention):
                continue
            seen.add(index)
            if index not in owner or assign(owner[index], seen):
                owner[index] = claim
                return True
        return False

    return sum(assign(claim, set()) for claim in range(len(claims)))


def _words(text: str) -> str:
    return " ".join(re.sub(r"[\W_]+", " ", normalise(text)).split())


def has_name(answer: str, names: Sequence[str]) -> bool:
    """Whether any of `names` appears in the answer as whole words."""
    padded = f" {_words(answer)} "
    return any(f" {_words(name)} " in padded for name in names if _words(name))


def _as_text(value: str | float | None) -> str:
    """The answer as text: a bare number answering a text question reads as that number."""
    if value is None:
        return ""
    return value if isinstance(value, str) else f"{value:g}"


class TextClaimsItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    source: str
    split: str
    passed: bool
    numbers: int
    numbers_matched: int
    names: int
    names_found: int
    extra_numbers: int = Field(description="numbers in the answer that met no claim")


class TextClaimsScore(BaseModel):
    """Golden free-text questions judged by their claims; not in the headline."""

    model_config = ConfigDict(extra="forbid")

    claims_sha256: str
    passed: Tally
    numbers: Tally
    names: Tally
    by_split: dict[str, Tally]
    without_claims: list[int] = Field(description="golden text question ids with no claims line")
    items: list[TextClaimsItem]


def _tally(correct: int, n: int) -> Tally:
    return Tally(n=n, correct=correct, accuracy=correct / n if n else None)


def score_text_claims(
    golden: Sequence[GoldenItem],
    answers: Mapping[int, Answer],
    claims: Sequence[TextClaims],
    claims_sha256: str,
) -> TextClaimsScore:
    text_items = {item.id: item for item in golden if item.type in FREE_TEXT_TYPES}
    by_id: dict[int, TextClaims] = {}
    for line in claims:
        if line.id in by_id:
            raise ValueError(f"text claims repeat id {line.id}")
        if line.id not in text_items:
            raise ValueError(f"text claims id {line.id} is not a golden free-text question")
        by_id[line.id] = line
    items: list[TextClaimsItem] = []
    for item_id, item in text_items.items():
        line = by_id.get(item_id)
        if line is None:
            continue
        answer = answers.get(item_id)
        text = _as_text(answer.answer if answer is not None else None)
        found = mentions(text)
        numbers = matched_claims(line.numbers, found)
        names = sum(has_name(text, [claim.name, *claim.aliases]) for claim in line.names)
        items.append(
            TextClaimsItem(
                id=item_id,
                source=item.source,
                split=item.split,
                passed=numbers == len(line.numbers) and names == len(line.names),
                numbers=len(line.numbers),
                numbers_matched=numbers,
                names=len(line.names),
                names_found=names,
                extra_numbers=len(found) - numbers,
            )
        )
    return TextClaimsScore(
        claims_sha256=claims_sha256,
        passed=_tally(sum(i.passed for i in items), len(items)),
        numbers=_tally(sum(i.numbers_matched for i in items), sum(i.numbers for i in items)),
        names=_tally(sum(i.names_found for i in items), sum(i.names for i in items)),
        by_split={
            split: _tally(
                sum(i.passed for i in items if i.split == split),
                sum(i.split == split for i in items),
            )
            for split in ("dev", "holdout")
        },
        without_claims=sorted(text_items.keys() - by_id.keys()),
        items=items,
    )


def _cell(tally: Tally) -> str:
    rate = "n/a" if tally.accuracy is None else f"{tally.accuracy:.1%}"
    return f"{tally.correct}/{tally.n} {rate}"


def format_text_claims(score: TextClaimsScore) -> str:
    return "\n".join(
        [
            "text by claims (not in the headline; the headline's text line is exact match)",
            f"  passed           {_cell(score.passed)} (dev {_cell(score.by_split['dev'])}, "
            f"holdout {_cell(score.by_split['holdout'])})",
            f"  claims           numbers {_cell(score.numbers)}, names {_cell(score.names)}",
            f"  without claims   {len(score.without_claims)} golden text questions",
        ]
    )

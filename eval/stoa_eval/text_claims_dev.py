"""Claims for a split's free-text questions, read from the dataset's own answers (ifc-eval brief).

The golden set's claims are curated by hand (text_scoring.py, D52); the ifc_bench text questions
have none there. Here a deterministic reader derives them from each gold answer, so
`score --against dev` can judge long text answers by what they state, not by exact match:

- Numbers: every number `text_scoring.mentions` reads in the gold answer, in one unit per kind.
  A measure the gold restates in another unit (1,111.8 cu ft (31.48 cu m)) is claimed once.
- Names: labels the gold lists ("- Basiswand:STB 25.0: 370 mm", "Rum nr. 501: 179.2 m²"),
  without a trailing parenthesis, unless every word is report vocabulary (Total area, Level 1);
  "yes" or "no" when the gold starts with it; "not available" (with aliases) when the gold says
  the model doesn't hold the answer.

The claims are partner-derived, so they live in the gitignored split folder
(`<split>_text_claims.jsonl`), never in the repo. `write_text_answers` turns {question id ->
answer text} into an answer_v1 file for answerers outside eval/.
"""

import re
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path, PurePosixPath

from pydantic import Field

from .families import source_of
from .jsonl import write_jsonl
from .models import (
    FREE_TEXT_TYPES,
    Answer,
    ClaimUnit,
    NameClaim,
    NumberClaim,
    NumberedQuestion,
    TextClaims,
)
from .scoring import REL_TOL, Tally
from .text_scoring import (
    Claimed,
    Kind,
    Mention,
    TextClaimsScore,
    format_text_claims,
    mentions,
    score_claims,
)

BY = "text_claims_dev"  # the `by` of every derived line
CANONICAL: dict[Kind, ClaimUnit] = {
    "count": "count",
    "length": "m",
    "area": "m2",
    "volume": "m3",
    "percent": "pct",
    "time": "min",
}
_LABEL = re.compile(r"^[ \t]*(?:[-•*][ \t]*|\d+[.)][ \t]+)?(?P<label>[^\n]{2,80}?):[ \t]+\S", re.M)
_TRAILING_PAREN = re.compile(r"\s*\([^()]*\)$")
_ORDINAL_LABEL = re.compile(r"(?:level|floor|storey|story)\s+\d+")  # the writer's, not the model's
_SUMMARY = frozenset({"total", "average", "number"})
_UNAVAILABLE = re.compile(
    r"not (?:directly )?available|cannot be (?:exactly )?(?:calculated|determined)", re.I
)
UNAVAILABLE = NameClaim(
    name="not available",
    aliases=[
        "not directly available", "unavailable", "not specified", "not modelled", "not modeled",
        "not stored", "not included", "not provided", "no information", "cannot be determined",
        "cannot be calculated", "not in the model", "does not contain", "doesn't contain",
    ],
)  # fmt: skip
# Words of the answer writer's report, not names the model holds; a label of only these (and
# numbers) is not claimed. Picked from the dev ifc_bench labels.
GENERIC = frozenset(
    """a accessories accessory all an analysis and approx approximate area areas average basement
    beam beams bearing building by calculated ceiling ceilings column columns combined component
    components composition count covering coverings curtain data depth description diameter door
    doors duct ducts each electrical element elements elevation entities equipment exterior
    external fifth first fitting fittings fixture fixtures floor floors for fourth furniture gross
    ground height in individual information interior internal largest latitude layer layers length
    level levels light lighting load location longitude main material materials max maximum member
    members mep min minimum model modeling modelling name net non note notes number of on other
    others overview pipe pipes piping plate plates plumbing project quantities quantity railing
    railings remaining residential roof roofs room rooms sanitary second segment segments site size
    slab slabs smallest space spaces specific stair stairs standard standards storey storeys stored
    story structural sum summary system systems terminal terminals the third thickness thicknesses
    to top total totals type types unit units value values version volume wall walls width window
    windows with communication conduit conduits device devices distribution items item flow
    control concrete flexible network connection connected infrastructure mechanical attic primary
    predefinedtype shutoff metering safety highly recyclable recyclability lower uncertain rate
    rates or""".split()  # noqa: SIM905
)


def family_of(path: str) -> str:
    """`ifc_bench/<discipline>` from `data/ifc_bench/<building>_<discipline>.ifc`, else the
    source: the model's discipline is the cheap family of a text question."""
    source = source_of(path)
    if source != "ifc_bench":
        return source
    return f"{source}/{PurePosixPath(path).stem.rsplit('_', 1)[-1]}"


def _unit_word(mention: Mention) -> str:
    return re.sub(r"^[\d.,\s]+", "", mention.text)


def numbers_of(answer: str) -> list[NumberClaim]:
    claims: list[NumberClaim] = []
    kept: list[Mention] = []
    for mention in mentions(answer, extended=True):
        restated = mention.kind != "count" and any(
            other.kind == mention.kind
            and _unit_word(other) != _unit_word(mention)
            and abs(other.value - mention.value) <= REL_TOL * abs(other.value)
            for other in kept
        )
        if restated:
            continue
        kept.append(mention)
        value = int(mention.value) if mention.kind == "count" else round(mention.value, 6)
        claims.append(NumberClaim(value=value, unit=CANONICAL[mention.kind], what=mention.text))
    return claims


def _is_name(label: str) -> bool:
    words = re.findall(r"[^\W_]+", label.casefold())
    if not words or len(words) > 8 or words[0] in _SUMMARY:  # Total ...: a summary row
        return False
    if _ORDINAL_LABEL.fullmatch(label.casefold()):
        return False
    return any(word not in GENERIC for word in words)  # a number is not generic: Space 4


def names_of(answer: str) -> list[NameClaim]:
    names: list[NameClaim] = []
    first = re.match(r"\s*(yes|no)\b", answer, re.I)
    if first:
        names.append(NameClaim(name=first[1].casefold()))
    if _UNAVAILABLE.search(answer):
        names.append(UNAVAILABLE)
    seen: set[str] = set()
    for match in _LABEL.finditer(answer):
        label = _TRAILING_PAREN.sub("", match["label"]).strip()
        if _is_name(label) and label.casefold() not in seen:
            seen.add(label.casefold())
            names.append(NameClaim(name=label))
    return names


def derive(rows: Iterable[NumberedQuestion], source: str) -> list[TextClaims]:
    """One claims line per free-text question of `source` whose gold states anything."""
    lines: list[TextClaims] = []
    for row in rows:
        if row.type not in FREE_TEXT_TYPES or source_of(row.path) != source:
            continue
        assert isinstance(row.answer, str)  # Question checks a text answer is a string
        numbers, names = numbers_of(row.answer), names_of(row.answer)
        if numbers or names:
            lines.append(TextClaims(id=row.id, numbers=numbers, names=names, by=BY))
    return lines


def claims_path(split_dir: Path, split: str) -> Path:
    return split_dir / f"{split}_text_claims.jsonl"


class SplitClaimsScore(TextClaimsScore):
    """A split's free-text questions judged by derived claims; answered questions only."""

    unanswered: int = Field(description="claimed questions without an answer, not judged")
    by_source: dict[str, Tally]
    by_family: dict[str, Tally] = Field(description="family_of: source, ifc_bench/<discipline>")


def score_split_claims(
    questions: Sequence[tuple[NumberedQuestion, str]],
    answers: Mapping[int, str | float | None],
    claims: Sequence[TextClaims],
    claims_sha256: str,
) -> SplitClaimsScore:
    """`questions`: (question, split name) pairs; `answers`: id -> answer, absent or None when
    unanswered (coverage mode: not wrong, counted apart)."""
    text = [(row, split) for row, split in questions if row.type in FREE_TEXT_TYPES]
    family = {row.id: family_of(row.path) for row, _ in text}
    base = score_claims(
        {row.id: Claimed(source_of(row.path), split) for row, split in text},
        answers,
        claims,
        claims_sha256,
        splits=sorted({split for _, split in text}),
        what="split",
        skip_unanswered=True,
        extended=True,
    )

    def by(key: Mapping[int, str]) -> dict[str, Tally]:
        groups: dict[str, list[bool]] = {}
        for item in base.items:
            groups.setdefault(key[item.id], []).append(item.passed)
        return {
            name: Tally(n=len(passed), correct=sum(passed), accuracy=sum(passed) / len(passed))
            for name, passed in sorted(groups.items())
        }

    judged = {item.id for item in base.items}
    return SplitClaimsScore(
        **dict(base),
        unanswered=sum(line.id not in judged for line in claims),
        by_source=by({row.id: source_of(row.path) for row, _ in text}),
        by_family=by(family),
    )


def format_split_claims(score: SplitClaimsScore) -> str:
    lines = [
        format_text_claims(score, "answered"),
        f"  unanswered       {score.unanswered} claimed questions (not judged)",
    ]
    for title, groups in (("source", score.by_source), ("family", score.by_family)):
        lines += [
            f"  {title + ' ' + name:<28} {tally.correct}/{tally.n} {tally.accuracy or 0:.1%}"
            for name, tally in groups.items()
        ]
    return "\n".join(lines)


def write_text_answers(
    texts: Mapping[int, str],
    out: Path,
    *,
    method: str,
    cost_usd: float = 0.0,
    latency_s: float = 0.0,
) -> None:
    """{question id -> answer text} as an answer_v1 file (no evidence; cost and latency per
    answer), for answerers that live outside eval/."""
    write_jsonl(
        out,
        (
            Answer(
                id=question_id,
                answer=text,
                unit=None,
                evidence=[],
                method=method,
                cost_usd=cost_usd,
                latency_s=latency_s,
            )
            for question_id, text in sorted(texts.items())
        ),
    )

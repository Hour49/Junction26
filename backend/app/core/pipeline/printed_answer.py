"""PRINTED_TOTAL_ANSWERS=on: a count the sheet prints for exactly what a stage-8 entry counts is
the value the entry reports; the count read off the drawing stays on the entry as its other value.

The architect's printed total ("SECOND FLOOR = 48 DORMS") is a statement on the drawing; our count
is a reading of it (QA round 4 R4-D1: T2 read 40 bedrooms where the sheet prints 48 for its floor).
With the setting off, printed.py's printed counts are only second values and no rule decides
(docs/PIPELINE.md section 2).

Exact match only, else nothing changes:
- the subject: the same element class, room type or all rooms (printed.fact_measurements' keys, so
  Carbon's own mapping, DORMS to room:bedroom, and its filters: a whole count, no flat type);
- the scope: the sheet shows one floor (one plan, or plans of one storey). When any printed count
  of the subject names a floor, only those naming the sheet's floor count, so another floor's and
  the building's total ("TOTAL = 144 DORMS") do not; when none names a floor, a sheet-wide count
  counts. A count of one part of the floor (a wing, a block) never does;
- one value: the counts left must all print the same number.
Then the entry reports it, only when no other rule already decided (second_count's FAR_COUNTS keeps
a reading more than 2x a printed room count). The entry stays a conflict, both values on it, so a
person still sees the drawing shows another number. Pure.
"""

import re
from collections.abc import Sequence

from app.core.drawing.model import Conflict, Resolution
from app.core.ifc_question import storey_number
from app.core.pipeline.model import Extracted, Measurement, PrintedAnswer
from app.core.pipeline.printed import PrintedFact, fact_measurements

# A floor a printed count names: "SECOND FLOOR", "2ND FLOOR", "GROUND LEVEL", "LEVEL 2", "FLOOR 3"
FLOOR = re.compile(
    r"\b(?:(?:ground|basement|first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth"
    r"|eleventh|twelfth|\d+(?:st|nd|rd|th)?)\s+(?:floor|level|storey|story)"
    r"|(?:level|floor|storey|story)\s+\d+)\b",
    re.IGNORECASE,
)
# A part of a floor a printed count can be of: never the sheet's whole floor
PART = re.compile(r"\b(?:wing|block|zone|phase|tower|building|bldg|section|house)s?\b", re.I)


def printed_answers(found: Extracted, facts: Sequence[PrintedFact]) -> Extracted:
    """`found` with the printed counts that match its entries exactly as `printed_answers`, and
    each one's measurement in `printed` in place of the one printed.fact_measurements kept (its
    first, which may be another floor's)."""
    floor = _sheets_floor(found)
    if floor is False:
        return found
    keyed: dict[tuple[str, str | None, str], list[tuple[Measurement, PrintedFact]]] = {}
    for fact in facts:
        for measured in fact_measurements([fact]):
            key = (measured.quantity, measured.subject.ref, measured.subject.kind)
            keyed.setdefault(key, []).append((measured, fact))
    answers: list[PrintedAnswer] = []
    for printed in keyed.values():
        named = [(m, f, _floor_of(f.text)) for m, f in printed]
        if any(number is not None for _, _, number in named):
            kept = [(m, f) for m, f, n in named if n is not None and n == floor]
        else:
            kept = [(m, f) for m, f, _ in named if not PART.search(f.text)]
        if kept and len({m.value.value for m, _ in kept}) == 1:
            answers.append(PrintedAnswer(measurement=kept[0][0], text=kept[0][1].text))
    if not answers:
        return found
    chosen = {(a.measurement.quantity, a.measurement.subject): a.measurement for a in answers}
    printed_now = tuple(
        chosen.get((m.quantity, m.subject), m) if m.value.method == "printed_total" else m
        for m in found.printed
    )
    return found.model_copy(update={"printed": printed_now, "printed_answers": tuple(answers)})


def answered(conflicts: Sequence[Conflict], answers: Sequence[PrintedAnswer]) -> list[Conflict]:
    """The stage-8 entries, each one a printed answer is about reporting the printed value: a
    conflict of the reading and that printed count only, which no rule decided."""
    by_key = {(a.measurement.quantity, a.measurement.subject): a for a in answers}
    out: list[Conflict] = []
    for entry in conflicts:
        answer = by_key.get((entry.quantity, entry.subject))
        methods = [value.method for value in entry.values]
        if (
            answer is None
            or entry.status != "conflict"
            or entry.resolution is not None
            or len(entry.values) != 2
            or methods[1] != "printed_total"
            or entry.values[1].value != answer.measurement.value.value
        ):
            out.append(entry)
            continue
        drawn = entry.values[0].value
        rule = f"printed on the sheet: {answer.text} ({drawn:g} drawn)"
        resolution = Resolution(rule=rule, value=answer.measurement.value.value)
        out.append(entry.model_copy(update={"resolution": resolution}))
    return out


def _sheets_floor(found: Extracted) -> int | bool | None:
    """The floor the sheet shows, as a number (storey_number); None when it shows one floor it
    does not name; False when it shows more than one, or one no number can be read from."""
    storeys = {plan.storey for plan in found.plans}
    if len(found.plans) > 1 and (len(storeys) != 1 or None in storeys):
        return False
    storey = next(iter(storeys), None)
    if storey is None:
        return None
    if isinstance(storey, int):
        return storey
    phrase = FLOOR.search(storey)
    number = storey_number((phrase[0] if phrase else storey).lower())
    return False if number is None else number


def _floor_of(text: str) -> int | None:
    """The floor a printed count names, as a number; None when it names none."""
    phrase = FLOOR.search(text)
    return None if phrase is None else storey_number(phrase[0].lower())

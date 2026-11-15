"""The drawings a chat message names (big QA R1 S2): "on Drawn plan 1", "on Plan image 2" by the
plain names list_drawings gives, and the project's IFC models by "building model" (misspelt as
"bulding model", "the model", "IFC model", Finnish "rakennusmalli"). ask_drawings then asks only
those, so the reply's cards and numbers are the named drawing's, not every drawing's."""

import re
from collections.abc import Mapping

# The IFC models' plain names start with this (api/views.NAME_WORDS["ifc"])
MODEL_NAME = "building model"
# The words for "the building model": "b?ilding" with a letter left out or doubled, BIM / IFC
# model, "the model", and the Finnish and German words
MODEL_WORDS = re.compile(
    r"\bb\w{0,2}l\w?d\w{0,2}ng[\s-]*model|\b(?:bim|ifc)[\s-]*model|\bthe\s+model\b(?!\s+of\b)"
    r"|\brakennusmall|\bgeb(?:ä|ae)udemodell|\bbauwerksmodell",
    re.IGNORECASE,
)
# the word before a drawing's name ("on Drawn plan 1", "Drawn plan 1 and Drawn plan 2")
BEFORE = r"(?:\b(?:on|in|of|for|from|and|or)\b|,)"
# A message about other drawings too ("Drawn plan 1 and the others", "besides Drawn plan 1",
# "more than the other drawings", "which drawing"): the named drawings alone would answer for
# them, or give the very number left out, so nothing is narrowed (review-693 M1)
OTHERS = re.compile(
    r"\b(?:others?|rest|except|besides|apart\s+from|excluding|not\s+counting|without|than"
    r"|compar\w*|versus|vs)\b|\bwhich\s+(?:drawing|plan|sheet|model|file)"
    r"|\b(?:every|each|all|both)\s+(?:of\s+)?(?:the\s+)?(?:drawings?|plans?|sheets?|files?|models?)\b",
    re.IGNORECASE,
)


def named_drawings(message: str, names: Mapping[str, str]) -> set[str]:
    """The ids of the drawings `message` names (`names`: drawing id → plain name), the longest
    name first, so "Drawn plan 10" is not "Drawn plan 1" and "Drawn plan 1, page 2" is not
    "Drawn plan 1"; with the model words, every IFC model. Empty: it names none."""
    if OTHERS.search(message):
        return set()
    found: set[str] = set()
    rest = message
    for drawing_id, name in sorted(names.items(), key=lambda item: -len(item[1])):
        if not name.strip():
            continue
        pattern = re.compile(rf"(?<!\w){_spelled(name)}(?!\w|[.,]\d)", re.IGNORECASE)
        if pattern.search(rest):
            found.add(drawing_id)
            rest = pattern.sub(" ", rest)
    if MODEL_WORDS.search(rest):
        found |= {d for d, name in names.items() if name.lower().startswith(MODEL_NAME)}
    return found


def unnamed(question: str, names: list[str]) -> str:
    """`question` without the drawing names in `names` and the word before them ("How many
    toilets are there on Plan image 2?" → "How many toilets are there?"), nor "in the building
    model": the asked drawings are already those, and the question reader takes no drawing name."""
    rest = question
    for name in sorted(names, key=len, reverse=True):
        rest = re.sub(
            rf"(?:\s*{BEFORE}(?:\s+the)?)?\s*(?<!\w){_spelled(name)}(?!\w|[.,]\d)",
            " ",
            rest,
            flags=re.IGNORECASE,
        )
    rest = re.sub(
        rf"\s+{BEFORE}(?:\s+the)?\s+(?:{MODEL_WORDS.pattern})\w*", " ", rest, flags=re.IGNORECASE
    )
    return re.sub(r"\s+([?.!,])", r"\1", " ".join(rest.split()))


def _spelled(name: str) -> str:
    """`name` as a pattern that also takes it without its comma ("Drawn plan 1 page 2")."""
    return r",?\s+".join(re.escape(part) for part in re.split(r",?\s+", name.strip()))

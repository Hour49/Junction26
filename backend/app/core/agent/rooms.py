"""The words of a question that can name a room label printed on a drawing (find_rooms, item 6):
the agent's toolbox looks rooms up by them, and the rules planner asks for them."""

import re

FIND_ROOMS = "find_rooms"
TOKEN = re.compile(r"[^\W\d_]{3,}|\d+(?:\.\d+)?")
NOT_A_NAME = frozenset(
    {
        "what",
        "which",
        "where",
        "whats",
        "the",
        "area",
        "size",
        "how",
        "big",
        "many",
        "much",
        "room",
        "rooms",
        "there",
        "this",
        "that",
        "does",
        "have",
        "has",
        "total",
        "floor",
        "level",
        "storey",
        "plan",
        "drawing",
        "drawings",
        "square",
        "metres",
        "meters",
        "net",
        "gross",
        "count",
        "number",
        "and",
        "for",
        "with",
        "its",
        "their",
        "show",
        "tell",
        "me",
        "is",
        "are",
        "of",
        "in",
        "on",
        "an",
        "do",
        "please",
        "about",
    }
)


# a unit, or a floor named by its number, is no part of a room's label (review-360 N1)
NOT_A_LABEL = re.compile(
    r"\b(?:m2|m²|sqm|sq\.? ?m|sq\.? ?ft|ft2|ft²|square (?:met(?:er|re)s?|feet|foot))(?!\w)|"
    r"\b(?:level|floor|storey|story)\s*\d+"
)


def name_words(text: str) -> list[str]:
    """The words of `text` that can name a printed room label: letters (3 or more) and numbers,
    lowercased, without question words, units or a floor's number."""
    plain = NOT_A_LABEL.sub(" ", text.lower())
    return [w for w in TOKEN.findall(plain) if w not in NOT_A_NAME]

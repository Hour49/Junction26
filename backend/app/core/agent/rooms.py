"""The words of a question that can name a room label printed on a drawing (find_rooms, item 6):
the agent's toolbox looks rooms up by them, and the rules planner asks for them."""

import re

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


def name_words(text: str) -> list[str]:
    """The words of `text` that can name a printed room label: letters (3 or more) and numbers,
    lowercased, without question words."""
    return [w for w in TOKEN.findall(text.lower()) if w not in NOT_A_NAME]

"""get_counting_rules: the agent's read-only tool for what a count or area includes ("does that
include closet doors?"), from the conventions the pipeline applies (fable-rooms/chat item 8).

One table, `CONVENTIONS`: per quantity, the words that name it and the convention in words. Where
the pipeline's counting rules (app/core/pipeline/rules.py, stage 9) or the answer's own notes
(app/core/review/ask.py) already say it, their text is used, not copied. The rest is what the
readers are told to list (the Carbon reader's classes, app/adapters/carbon/contract.py) and what
the question parser reads (app/adapters/question_templates.py). No numbers: a convention, not a
reading, so there is no evidence to cite. Tool contract: docs/specs/agent-chat.md AC-13; the
project is not an argument, and `run_counting_tool` never raises.
"""

import json
import re
from typing import Any

from app.core.pipeline.rules import (
    APARTMENT_AREA,
    EACH_ONCE,
    ROOM_AREA,
    ROOMS_TOTAL,
    SAUNA_ROOM_ELSE_STOVE,
    SHOWERS_AND_BATHTUBS,
)
from app.core.review.ask import CLOSET_RULE

NAME = "get_counting_rules"


def _said(*parts: str) -> str:
    return "; ".join(parts) + "."


# quantity -> (the words that name it, the convention). A cue matches as a whole word (with a
# plural ending), the cue that ends last wins, the longest of those (`_score`), and
# when the question names an area (AREA_WORDS) the area conventions come first ("the bathroom's
# area" is a room's area, "does the area include the balcony" the floor area's). English, with
# the common German and Finnish words.
CONVENTIONS: dict[str, tuple[tuple[str, ...], str]] = {
    "toilets": (
        ("toilet", "toilette", "wc", "wc seat", "wc room", "toilet room", "water closet", "urinal",
         "wc istuin"),
        _said(
            EACH_ONCE.text,
            "a toilet is a toilet bowl (WC seat), wherever it is; a urinal is not a toilet",
            "a separate toilet room counts as a room of type wc, and the toilet in it counts as "
            "a toilet",
        ),
    ),
    "doors": (
        ("door", "closet", "closet door", "cupboard", "wardrobe", "double door", "sliding door",
         "doorway", "tür", "türen", "ovi", "ovet"),
        _said(
            EACH_ONCE.text,
            "each door opening counts once: a double door, a sliding or folding door is one door",
            CLOSET_RULE,
            "cupboard and wardrobe doors (furniture) are not doors, nor is an open doorway "
            "without a door leaf",
            "a door between two rooms belongs to both rooms when you count a room's doors",
        ),
    ),
    "windows": (
        ("window", "sash", "pane", "glazing", "fenster", "ikkuna", "ikkunat"),
        _said(
            EACH_ONCE.text,
            "a window is a whole window unit in a wall: a unit with several panes or sashes in "
            "one frame is one window, not one per sash or pane",
        ),
    ),
    "sinks": (
        ("sink", "basin", "washbasin", "wash basin", "lavatory", "double bowl",
         "double bowl sink", "spüle", "waschbecken", "pesuallas", "allas"),
        _said(
            EACH_ONCE.text,
            "a sink is a sink or wash basin in a kitchen, a bathroom or anywhere else; a "
            "double-bowl sink is one sink",
        ),
    ),
    "showers and bathtubs": (
        ("shower", "bathtub", "bath tub", "bath", "dusche", "badewanne", "suihku", "kylpyamme"),
        _said(
            "showers and bathtubs are counted apart when asked apart: a shower is a tray, a "
            "cubicle or a shower drawn in a wet room",
            f"asked together: {SHOWERS_AND_BATHTUBS.text}",
        ),
    ),
    "saunas": (("sauna", "sauna stove", "kiuas"), _said(SAUNA_ROOM_ELSE_STOVE.text)),
    "floor area": (
        ("floor area", "total area", "net area", "gross area", "indoor", "outdoor", "gross",
         "footprint", "balcony", "balconies", "terrace", "patio", "shaft", "lift", "elevator",
         "stairwell", "stair", "stairs", "staircase", "balkon", "terrasse", "aufzug",
         "treppenhaus", "schacht", "parveke", "terassi", "hissi", "porraskäytävä", "kuilu"),
        _said(
            "the floor area of a sheet is the net area of its indoor rooms: every room that is "
            "not outdoor counts, shafts, lifts and stairwells included",
            "outdoor rooms (balconies, terraces) are left out",
            "a gross area or a footprint is not taken off",
            ROOMS_TOTAL.text,
        ),
    ),
    "apartment area": (
        ("apartment", "dwelling", "wohnung", "asunto"),
        _said(APARTMENT_AREA.text),
    ),
    # any other area question: a room's own area (`counting_rule` falls back to it)
    "room area": (("room area", "room size"), _said(ROOM_AREA.text)),
    "rooms": (
        ("room", "bedroom", "kitchen", "bathroom", "living room", "küche", "schlafzimmer",
         "zimmer", "keittiö", "makuuhuone", "huone"),
        _said(
            EACH_ONCE.text,
            "a room's type comes from its printed label, else from what is drawn in it",
            "a bathroom has a shower or bath; a separate toilet room is a wc room",
        ),
    ),
}  # fmt: skip
AREAS = ("floor area", "apartment area", "room area")  # the conventions about an area
AREA_WORDS = re.compile(r"\b(?:areas?|m2|m²|sq|square|size|how big|fläche|wohnfläche|pinta ala)\b")

TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": NAME,
            "description": (
                "What a count or area includes, as the pipeline counts it: closet doors, double "
                "doors, window sashes, toilets, sinks, showers, outdoor rooms and shafts in a "
                "floor area. A convention, with no values; call it when the user asks what is "
                "included or how something is counted. Without a quantity: every convention."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "quantity": {
                        "type": "string",
                        "maxLength": 200,
                        "description": "what is counted or measured, e.g. 'closet doors'",
                    }
                },
                "required": [],
            },
        },
    }
]


def counting_rule(quantity: str) -> dict[str, Any]:
    """The convention for `quantity` (any wording), every convention for an empty one, or that
    there is none, with the quantities that have one."""
    asked = " ".join(re.findall(r"[^\W_]+", quantity.lower()))  # "double-bowl": "double bowl"
    if not asked:
        return {"conventions": {name: text for name, (_, text) in CONVENTIONS.items()}}
    area = AREA_WORDS.search(asked) is not None
    # (an area convention in an area question, where its last cue ends, that cue's length)
    scores = {name: (0, *_score(asked, cues)) for name, (cues, _) in CONVENTIONS.items()}
    if area:  # an area question: the area conventions first, a room's area when none is named
        scores["room area"] = max(scores["room area"], (0, 0, 1))
        scores |= {name: (1, *scores[name][1:]) for name in AREAS}
    found = {name: score for name, score in scores.items() if score[-1]}  # a cue matched
    if not found:
        return {
            "quantity": quantity,
            "convention": None,
            "unknown": f"no counting convention is recorded for {quantity!r}",
            "known": list(CONVENTIONS),
        }
    name = max(found, key=lambda each: found[each])  # the first of equals: table order
    return {"quantity": name, "convention": CONVENTIONS[name][1]}


def _score(asked: str, cues: tuple[str, ...]) -> tuple[int, int]:
    """Where the last cue found in `asked` (whole words, a plural ending allowed) ends, and the
    longest cue ending there: the counted thing comes last ("living room door" is a door), and of
    cues ending together the longest is the most specific ("water closet" over "closet").
    (0, 0): none."""
    ends = [
        (found.end(), len(cue))
        for cue in cues
        for found in re.finditer(rf"\b{re.escape(cue)}(?:s|es|n|en)?\b", asked)
    ]
    return max(ends, default=(0, 0))


def run_counting_tool(name: str, arguments: str) -> str:
    """The toolbox runner: JSON text back, `{"error": ...}` on a bad call, never raises."""
    try:
        given: Any = json.loads(arguments or "{}")
        if name != NAME:
            raise ValueError(f"unknown tool {name!r}")
        if not isinstance(given, dict):
            raise ValueError("the arguments must be a JSON object")
        quantity: Any = given.get("quantity", "")  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
        if not isinstance(quantity, str):
            raise ValueError("quantity must be text")
        return json.dumps(counting_rule(quantity[:200]), ensure_ascii=False)
    except (ValueError, json.JSONDecodeError) as error:
        return json.dumps({"error": str(error)}, ensure_ascii=False)

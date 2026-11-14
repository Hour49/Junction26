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
    INDOOR_TOTAL,
    ROOM_AREA,
    ROOMS_TOTAL,
    SAUNA_ROOM_ELSE_STOVE,
    SHOWERS_AND_BATHTUBS,
)
from app.core.review.ask import CLOSET_RULE

NAME = "get_counting_rules"


def _said(*parts: str) -> str:
    return "; ".join(parts) + "."


# quantity -> (the words that name it, the convention). First match wins, so the narrower
# quantities come first: "water closet" is a toilet before "closet" is a door, "floor area" a
# floor area before "area" is a room's.
CONVENTIONS: dict[str, tuple[tuple[str, ...], str]] = {
    "toilets": (
        ("toilet", "wc seat", "water closet", "urinal"),
        _said(
            EACH_ONCE.text,
            "a toilet is a toilet bowl (WC seat), wherever it is; a urinal is not a toilet",
            "a separate toilet room is counted as a room of type wc, not as a toilet",
        ),
    ),
    "doors": (
        ("door", "closet", "doorway"),
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
        ("window", "sash", "pane", "glazing"),
        _said(
            EACH_ONCE.text,
            "a window is a whole window unit in a wall: a unit with several panes or sashes in "
            "one frame is one window, not one per sash or pane",
        ),
    ),
    "sinks": (
        ("sink", "basin", "washbasin", "lavatory"),
        _said(
            EACH_ONCE.text,
            "a sink is a sink or wash basin in a kitchen, a bathroom or anywhere else; a "
            "double-bowl sink is one sink",
        ),
    ),
    "showers and bathtubs": (
        ("shower", "bathtub", "bath tub", "tub"),
        _said(
            "showers and bathtubs are counted apart when asked apart: a shower is a tray, a "
            "cubicle or a shower drawn in a wet room",
            f"asked together: {SHOWERS_AND_BATHTUBS.text}",
        ),
    ),
    "saunas": (("sauna", "kiuas"), _said(SAUNA_ROOM_ELSE_STOVE.text)),
    "floor area": (
        (
            "floor area",
            "total area",
            "net area",
            "indoor",
            "outdoor",
            "shaft",
            "gross",
            "footprint",
        ),
        _said(
            "the floor area of a sheet is the net area of its indoor rooms",
            INDOOR_TOTAL.text,
            "outdoor rooms (balconies, terraces) are left out",
            "a gross area or a footprint is not taken off",
            ROOMS_TOTAL.text,
        ),
    ),
    "apartment area": (("apartment", "dwelling", "flat"), _said(APARTMENT_AREA.text)),
    "room area": (("area", "room size", "how big"), _said(ROOM_AREA.text)),
    "rooms": (
        ("room", "bedroom", "kitchen", "bathroom"),
        _said(
            EACH_ONCE.text,
            "a room's type comes from its printed label, else from what is drawn in it",
            "a bathroom has a shower or bath; a separate toilet room is a wc",
        ),
    ),
}

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
    asked = " ".join(re.findall(r"[a-zäöå]+", quantity.lower()))
    if not asked:
        return {"conventions": {name: text for name, (_, text) in CONVENTIONS.items()}}
    for name, (cues, text) in CONVENTIONS.items():
        if any(re.search(rf"\b{re.escape(cue)}", asked) for cue in cues):
            return {"quantity": name, "convention": text}
    return {
        "quantity": quantity,
        "convention": None,
        "unknown": f"no counting convention is recorded for {quantity!r}",
        "known": list(CONVENTIONS),
    }


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

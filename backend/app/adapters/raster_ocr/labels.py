"""From a piece of read text to a room type, through room_labels.json (build_room_labels.py) and
room_labels_read.json.

room_labels.json holds the labels the dev gold's annotators typed. room_labels_read.json adds how
the OCR actually reads bedroom and balcony labels (misreads such as "HM", "PAVVEKE", printed long
words such as MAKUUHUONE): built by `prototypes/ocr/reselect.py --learn` from arm A's readings
of 1,000 experiment-train sheets (a reading inside a gold room votes for its type; >= 5 votes,
share >= 0.6), keeping the bedroom and balcony entries only (arm A2b: on val balcony +7.2 pp,
bedroom +3.3 pp; the other types' learned entries made bathrooms and kitchens worse), and of the
bedroom entries only those at share >= 0.9 (arm A2d: the cut drops "MM", the unit of ceiling
notes, and other junk; on val bedroom +0.8 pp, wc +1.1 pp, no family worse). Where both files
name a label, room_labels.json wins.

`fold` is how both the table and a reading are compared: accents dropped (OCR often loses the
dots of Ä and Ö), upper case, and everything but letters, "/" and "+" removed, so "MH1", "MH 2"
and "mh." are all MH. A folded reading (or one of its words) must equal a table label: a one or
two letter code is too short for a near match to mean anything.
"""

import json
import unicodedata
from functools import cache
from pathlib import Path

from app.core.drawing.model import RoomType

TABLE = Path(__file__).with_name("room_labels.json")
READ = Path(__file__).with_name("room_labels_read.json")


def fold(text: str) -> str:
    plain = unicodedata.normalize("NFKD", text)
    letters = (c for c in plain if not unicodedata.combining(c))
    return "".join(c for c in "".join(letters).upper() if ("A" <= c <= "Z") or c in "/+")


@cache
def table() -> dict[str, RoomType]:
    rows = {
        **json.loads(READ.read_text(encoding="utf-8")),
        **json.loads(TABLE.read_text(encoding="utf-8")),
    }
    return {label: row["type"] for label, row in rows.items()}


def room_type(text: str) -> RoomType | None:
    """The type of the room a reading names, or None when the reading names no room we know.
    A reading of several words ("MH 12,5 m2") names the room of its first word of two or more
    letters that is a label: a lone letter inside other text is noise."""
    if (kind := table().get(fold(text))) is not None:
        return kind
    for word in text.split():
        key = fold(word)
        if len(key) >= 2 and key in table():
            return table()[key]
    return None

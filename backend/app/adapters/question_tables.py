"""Schedule questions to a `TableQuery` (part of the `templates` parser), with no model call.

A question is about a schedule when it names one ("door schedule", "finish room schedule") or
asks for what only a schedule prints (a hardware group, a door or frame material, a finish, a
note, a door by its number). From its words:

1. What is done: "how many" ("count the", "number of") a kind of row counts rows (or adds a
   schedule's Count column); an area sums the area column; "what"/"which" reads the cells of
   the column the words before "of"/"for"/"is" name.
2. Which rows: the codes (A1, WD-1, F0, "type SS"), door numbers (121.A), room numbers ("room
   128"), names ("named OFFICE"), notes ("note A") and dimensions ("3'-0\" wide") it mentions,
   each with the few words before it, which pick the column when several hold the value; and
   words a description has or starts with (the counted phrase's capitalised names, "on the 3rd
   floor", "starts with 'SWING'").
3. Which table: the one it names, else the kind of row it counts or names (doors, windows,
   rooms).

Two quantities in one question, a superlative or rows it can't name are `Unsupported`.
"""

import re
from typing import Literal

from app.core.answering.model import TableFilter, TableQuery, Unsupported

TABLE_CUES = re.compile(
    r"schedul|\bfinish|\bhardware\b|\bmaterial\b|\bmatl\b|\bdoor types?\b|\bframes?\b"
    r"|\bnotes? [A-Z]\b|\bbase\b|(?<![\w.])[A-Z]?\d{2,4}\.[A-Z]\d?(?![\w.])",
)
# "On sheet A-801 of the ..., ", "On sheet A700 of the ... drawings (1750 N Oxford Ave, Eau Claire,
# WI), ": the context ends at the first comma outside parentheses.
CONTEXT = re.compile(r"^\s*on sheet (?:[^,(]|\([^)]*\))*,\s*", re.IGNORECASE)
NAMED_TABLE = re.compile(r"\b(?:in|from|on|does)\s+the\s+([\w ]*?)\s*schedule\b", re.IGNORECASE)
TWO_QUANTITIES = re.compile(r"\bhow many\b.*\band\b.*\b(?:total|area|sum)\b", re.IGNORECASE)
# The two quantities that are one query: a count of rows and their total area.
AND_THEIR_AREA = re.compile(
    r",?\s+and what is (?:their|the) (?:total |combined )?area\s*\??$", re.IGNORECASE
)
# "which room ... has the largest area": the row of a kind with the largest or smallest area.
WHICH_ROW = re.compile(r"^(?:which|what)\s+(\w+)\b", re.IGNORECASE)
EXTREME_AREA = re.compile(r"\bthe (largest|biggest|smallest) (?:floor )?area\b", re.IGNORECASE)
BREAKDOWN = re.compile(
    r"\beach\b|\bper (?:type|room|floor)\b|\bby type\b|\blist (?:all|the)\b", re.IGNORECASE
)
SUPERLATIVE = re.compile(r"\b(?:largest|smallest|biggest|longest|shortest|most|least)\b", re.I)
MEANING = re.compile(r"\bmean|\bwhat kind\b|\bstand for\b|\bdescri", re.IGNORECASE)
WHOLE_TABLE = re.compile(r"\ball\b|\blisted\b", re.IGNORECASE)
AREA = re.compile(r"\barea\b", re.IGNORECASE)
# "how many doors", "count the doors", "the number of rooms", "how many unit entry doors (type
# U01) are", "how many 2-wide window assemblies": the counted noun phrase runs to a parenthesis or
# the first verb or preposition ("the room number of" is no count).
COUNTED = re.compile(
    r"\b(?:how many|count(?:\s+the)?|(?:the|a|total)\s+number of)\s+([^?()]*?)\s*"
    r"(?=[(?]|$|\b(?:are|is|in|on|of|does|do|with|have|has|carry|that|listed|scheduled|for)\b)",
    re.IGNORECASE,
)
# A counted phrase names a kind of row (below) or is one of these words for any row; anything
# else ("how many hardware sets", "how many square feet") is not a count of a schedule's rows.
ANY_ROW = re.compile(r"\b(?:items?|entries|entry|rows?)$", re.IGNORECASE)
# What a counted phrase or a named table is a row of.
ROW_KINDS = (
    ("door", re.compile(r"\b(?:doors?|gates?|leaf|leaves|openings?)\b", re.IGNORECASE)),
    ("window", re.compile(r"\bwindows?\b", re.IGNORECASE)),
    ("room", re.compile(r"\brooms?\b|\bfinish", re.IGNORECASE)),
)
READ_COLUMNS = re.compile(
    r"^(?:what|which)\s+(?:(?:is|are)\s+)?(?:the\s+)?(.+?)\s+(?:of|for|is|are)\b", re.IGNORECASE
)
DOOR_ID = re.compile(r"(?<![\w.])([A-Z]?\d{2,4}\.[A-Z]\d?|[A-Z]?\d{3}[A-Z])(?![\w.])")
ROOM_NUMBER = re.compile(r"\brooms?\s+(\d{2,4}[A-Z]?)\b", re.IGNORECASE)
NOTE = re.compile(r"\bnotes?\s+([A-Z])\b")
DIMENSION = re.compile(r"""(\d+\s*['’′]\s*-\s*\d+(?:\s+\d+/\d+)?\s*["”″])\s+(wide|high|tall)""")  # noqa: RUF001
NAMED = re.compile(r"\bnamed\s+([A-Z][A-Z0-9.'&/-]*(?:\s+[A-Z][A-Z0-9.'&/-]*)*)")
EVERY_WALL = re.compile(r"\ball (?:four |4 )?walls\b[^?]*?\b([A-Z]{1,3}-?\d{1,2})\b")
# A code: one to three capitals, an optional dash, digits (A1, B2, WD-1, STL-1, F0, W1). Codes in
# one parenthesis joined by "or"/"and" are one filter: "(AL-1 or AL-2)".
CODE = r"[A-Z]{1,3}-?\d{1,2}[A-Z]?"
CODE_GROUP = re.compile(rf"(?<![\w.-])({CODE}(?:\s*(?:,|or|and)\s*{CODE})*)(?![\w.-])")
# Type marks of capitals only (SS, RR) are codes only right after "type(s)":
# "(types SS, TT and UU)".
LETTER_CODE = r"[A-Z]{1,3}"
TYPE_LETTERS = re.compile(
    rf"\btypes?\s+({LETTER_CODE}(?:\s*(?:,|or|and)\s*{LETTER_CODE})*)(?![\w.-])"
)
# Rows a counted phrase describes by a name the schedule prints in a description ("Marvin
# Essential sliding patio doors", "Vistagrande fiberglass entry doors"): its capitalised words.
PROPER_NAME = re.compile(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b")
FLOOR = re.compile(r"\bon the (\d+(?:st|nd|rd|th) floor)\b", re.IGNORECASE)  # "on the 3rd floor"
QUOTE = "'‘’\"“”"  # noqa: RUF001
STARTS = re.compile(
    rf"\b(?:starts?|begins?) with [{QUOTE}]([^{QUOTE}]+)[{QUOTE}]", re.IGNORECASE
)  # "whose description starts with 'SWING'"
CUE_WORDS = 3  # how many words before a value say which column it is in


def is_table_question(text: str) -> bool:
    return TABLE_CUES.search(text) is not None


def parse_table(text: str) -> TableQuery | Unsupported:
    """`text` is a question `is_table_question` accepts, whitespace normalised."""
    body = CONTEXT.sub("", text)
    extreme = _extreme(body)
    if SUPERLATIVE.search(body) and extreme is None:
        return Unsupported(reason="a superlative (largest, longest...) is not a schedule lookup")
    if BREAKDOWN.search(body):
        return Unsupported(reason="a breakdown or list is not one quantity")
    with_area = AND_THEIR_AREA.search(body)
    if TWO_QUANTITIES.search(body) and with_area is None:
        return Unsupported(reason="two quantities in one question")
    named = NAMED_TABLE.search(body)
    table_name = named.group(1) if named else ""
    counted = _counted(body)
    kind = _kind(table_name, counted, body)
    rest = NAMED_TABLE.sub(" ", body)
    filters, rest = _filters(rest)
    if extreme is not None:
        op, column = extreme, (("area",),)
    elif with_area is not None:
        if counted is None:
            return Unsupported(reason="two quantities in one question")
        op, column = "count_sum", (("area",),)
    elif counted is not None:
        filters += [
            TableFilter(values=(name,), match="contains") for name in PROPER_NAME.findall(counted)
        ]
        op, column = "count", ()
    elif AREA.search(body):
        op, column = "sum", (("area",),)
    elif match := READ_COLUMNS.match(body):
        op = "read"
        column = tuple(tuple(part.split()) for part in re.split(r"\s+and\s+", match.group(1)))
    else:
        return Unsupported(reason="no count, area or schedule cell asked for")
    if op == "read" and not filters:
        return Unsupported(reason="a schedule cell without saying which row")
    return TableQuery(
        op=op,
        kind=kind,
        table=tuple(table_name.casefold().split()),
        column=column,
        filters=tuple(filters),
        every_row=not filters and WHOLE_TABLE.search(body) is not None,
        meaning=MEANING.search(body) is not None,
    )


def _extreme(body: str) -> Literal["max", "min"] | None:
    """ "max"/"min" when the question asks which row of a kind has the largest/smallest area."""
    row, most = WHICH_ROW.match(body), EXTREME_AREA.search(body)
    if row is None or most is None or _row_kind(row.group(1)) is None:
        return None
    return "min" if most.group(1).casefold() == "smallest" else "max"


def _counted(body: str) -> str | None:
    """The counted noun phrase of a count of rows, or None when it asks no such count."""
    match = COUNTED.search(body)
    if match is None:
        return None
    phrase = match.group(1).strip()
    return phrase if _row_kind(phrase) or ANY_ROW.search(phrase) else None


def _row_kind(text: str) -> str | None:
    return next((kind for kind, words in ROW_KINDS if words.search(text)), None)


def _kind(table_name: str, counted: str | None, body: str) -> str | None:
    if table_name and (kind := _row_kind(table_name)):
        return kind
    if counted and (kind := _row_kind(counted)):
        return kind
    if DOOR_ID.search(body) or re.search(r"\bdoors\b", body, re.IGNORECASE):
        return "door"
    if ROOM_NUMBER.search(body) or re.search(r"\brooms\b", body, re.IGNORECASE):
        return "room"
    return None


def _cue(text: str, end: int) -> tuple[str, ...]:
    return tuple(re.findall(r"[^\W\d_]+", text[:end])[-CUE_WORDS:])


def _filters(text: str) -> tuple[list[TableFilter], str]:
    """The filters a question names, and the question with their values blanked out."""
    found: list[TableFilter] = []

    def take(pattern: re.Pattern[str], cue: tuple[str, ...] | None = None) -> None:
        nonlocal text
        values: list[str] = []
        for match in pattern.finditer(text):
            values.append(match.group(1))
        if not values:
            return
        if pattern is DOOR_ID:  # door numbers, one filter (a range names both ends)
            found.append(TableFilter(values=tuple(values), cue=("door", "number")))
        else:
            for match in pattern.finditer(text):
                words = cue if cue is not None else _cue(text, match.start())
                found.append(TableFilter(values=(match.group(1),), cue=words))
        text = pattern.sub(" _ ", text)

    if every := EVERY_WALL.search(text):
        found.append(TableFilter(values=(every.group(1),), cue=("wall",), every=True))
        text = text[: every.start(1)] + " _ " + text[every.end(1) :]
    for match in STARTS.finditer(text):
        found.append(TableFilter(values=(match.group(1),), match="starts"))
    text = STARTS.sub(" _ ", text)
    for match in FLOOR.finditer(text):
        found.append(TableFilter(values=(match.group(1),), match="contains"))
    text = FLOOR.sub(" _ ", text)
    take(DOOR_ID)
    take(ROOM_NUMBER, ("room", "number"))
    take(NOTE, ("note",))
    for match in DIMENSION.finditer(text):
        found.append(TableFilter(values=(match.group(1),), cue=(match.group(2),)))
    text = DIMENSION.sub(" _ ", text)
    take(NAMED, ("name",))
    for match in TYPE_LETTERS.finditer(text):
        found.append(
            TableFilter(values=tuple(re.findall(LETTER_CODE, match.group(1))), cue=("type",))
        )
    text = TYPE_LETTERS.sub(" type _ ", text)
    for match in CODE_GROUP.finditer(text):
        codes = tuple(re.findall(CODE, match.group(1)))
        start = match.start() - 1 if text[: match.start()].endswith("(") else match.start()
        found.append(TableFilter(values=codes, cue=_cue(text, start)))
    return found, CODE_GROUP.sub(" _ ", text)

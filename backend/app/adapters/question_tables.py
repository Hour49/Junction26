"""Schedule questions to a `TableQuery` (part of the `templates` parser), with no model call.

A question is about a schedule when it names one ("door schedule", "finish room schedule") or
asks for what only a schedule prints (a hardware group, a door or frame material, a finish, a
note, a door by its number). From its words:

1. What is done: "how many" ("count the", "number of") counts rows; an area sums the area
   column; "what"/"which" reads the cells of the column the words before "of"/"for"/"is" name.
2. Which rows: the codes (A1, WD-1, F0), door numbers (121.A), room numbers ("room 128"),
   names ("named OFFICE"), notes ("note A") and dimensions ("3'-0\" wide") it mentions, each
   with the few words before it, which pick the column when several hold the value.
3. Which table: the one it names, else the kind of row it counts or names (doors, rooms).

Two quantities in one question, a superlative or rows it can't name are `Unsupported`.
"""

import re

from app.core.answering.model import TableFilter, TableQuery, Unsupported

TABLE_CUES = re.compile(
    r"schedul|\bfinish|\bhardware\b|\bmaterial\b|\bmatl\b|\bdoor types?\b|\bframes?\b"
    r"|\bnotes? [A-Z]\b|\bbase\b|(?<![\w.])[A-Z]?\d{2,4}\.[A-Z]\d?(?![\w.])",
)
CONTEXT = re.compile(r"^\s*on sheet [^,]*,\s*", re.IGNORECASE)  # "On sheet A-801 of the ..., "
NAMED_TABLE = re.compile(r"\b(?:in|from|on|does)\s+the\s+([\w ]*?)\s*schedule\b", re.IGNORECASE)
TWO_QUANTITIES = re.compile(r"\bhow many\b.*\band\b.*\b(?:total|area|sum)\b", re.IGNORECASE)
BREAKDOWN = re.compile(
    r"\beach\b|\bper (?:type|room|floor)\b|\bby type\b|\blist (?:all|the)\b", re.IGNORECASE
)
SUPERLATIVE = re.compile(r"\b(?:largest|smallest|biggest|longest|shortest|most|least)\b", re.I)
MEANING = re.compile(r"\bmean|\bwhat kind\b|\bstand for\b|\bdescri", re.IGNORECASE)
WHOLE_TABLE = re.compile(r"\ball\b|\blisted\b", re.IGNORECASE)
AREA = re.compile(r"\barea\b", re.IGNORECASE)
# "how many doors", "count the doors", "the number of rooms"
COUNTED = re.compile(
    r"\b(?:how many|count(?:\s+the)?|number of)\s+(doors?|rooms?)\b", re.IGNORECASE
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
CUE_WORDS = 3  # how many words before a value say which column it is in


def is_table_question(text: str) -> bool:
    return TABLE_CUES.search(text) is not None


def parse_table(text: str) -> TableQuery | Unsupported:
    """`text` is a question `is_table_question` accepts, whitespace normalised."""
    body = CONTEXT.sub("", text)
    if SUPERLATIVE.search(body):
        return Unsupported(reason="a superlative (largest, longest...) is not a schedule lookup")
    if BREAKDOWN.search(body):
        return Unsupported(reason="a breakdown or list is not one quantity")
    if TWO_QUANTITIES.search(body):
        return Unsupported(reason="two quantities in one question")
    named = NAMED_TABLE.search(body)
    kind = _kind(named.group(1) if named else "", body)
    rest = NAMED_TABLE.sub(" ", body)
    filters, rest = _filters(rest)
    if COUNTED.search(body):
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
        column=column,
        filters=tuple(filters),
        every_row=not filters and WHOLE_TABLE.search(body) is not None,
        meaning=MEANING.search(body) is not None,
    )


def _kind(table_name: str, body: str) -> str | None:
    lower = table_name.casefold()
    if "door" in lower:
        return "door"
    if "room" in lower or "finish" in lower:
        return "room"
    if counted := COUNTED.search(body):
        return "door" if counted.group(1).casefold().startswith("door") else "room"
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
    take(DOOR_ID)
    take(ROOM_NUMBER, ("room", "number"))
    take(NOTE, ("note",))
    for match in DIMENSION.finditer(text):
        found.append(TableFilter(values=(match.group(1),), cue=(match.group(2),)))
    text = DIMENSION.sub(" _ ", text)
    take(NAMED, ("name",))
    for match in CODE_GROUP.finditer(text):
        codes = tuple(re.findall(CODE, match.group(1)))
        start = match.start() - 1 if text[: match.start()].endswith("(") else match.start()
        found.append(TableFilter(values=codes, cue=_cue(text, start)))
    return found, CODE_GROUP.sub(" _ ", text)

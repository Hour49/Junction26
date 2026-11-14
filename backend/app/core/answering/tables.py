"""Answers from the schedules printed on a sheet (Drawing.tables): count rows, sum a column, read
cells.

A filter's column is found from its values: the one column whose cells hold one of them ("WD-1"
is only ever a door material, "121.A" only a door number). When several columns hold a value, the
words the question puts before it pick the column whose header shares one ("frame" picks Frame
Matl over Door Matl for "AL-1"). The column to sum or read is the one whose header the question's
words cover best. Anything that does not resolve to one table and one column gives no answer, so
the question is refused, never guessed. The rules below are data.
"""

import re
from collections.abc import Iterable, Mapping, Sequence

from app.core.answering.model import TableFilter, TableQuery, Unit
from app.core.drawing.model import Box, Table, TableRow
from app.core.model import Frozen

# A table whose title has one of these words explains codes (a finish key, door keynotes): it is
# read for what a code means, never counted or summed.
LEGEND_WORDS = frozenset({"key", "keynote", "legend"})
# A column whose header has one of these words prints codes that say nothing without their key
# (F2, W1, C2): its cells are read with what they mean, asked or not (the sheet's finish key).
KEYED_WORDS = frozenset({"finish"})
# A code read with its key's description is said in the sheet's words, which need not be the
# words the question expects, so the answer abstains while keeping the value.
MEANING_WHY = "what the code means is copied from the sheet's key; the wording asked for may differ"
# Which tables a kind of row lives in, by title words.
KIND_WORDS: Mapping[str, frozenset[str]] = {
    "door": frozenset({"door"}),
    "room": frozenset({"room", "finish"}),
}
# Header and question words that mean the same, after case folding.
SYNONYMS: Mapping[str, str] = {
    "matl": "material",
    "mat": "material",
    "wide": "width",
    "high": "height",
    "tall": "height",
    "finishes": "finish",
    "finished": "finish",
    "notes": "note",
    "specs": "spec",
    "hw": "hardware",
}
STOP_WORDS = frozenset(
    {"the", "a", "an", "of", "in", "on", "is", "are", "for", "with", "and", "or", "see", "have",
     "has", "that", "this", "what", "which", "how", "many", "does", "do", "carry", "it"}
)  # fmt: skip
# A printed area: a number and its unit ("5183 SF").
AREA_CELL = re.compile(
    r"^\s*(\d[\d,]*(?:\.\d+)?)\s*(sf|sq\.?\s*ft\.?|ft2|ft²|m2|m²|sqm)?\s*$", re.IGNORECASE
)
AREA_UNITS: Mapping[str, Unit] = {"sf": "ft2", "sqft": "ft2", "ft2": "ft2", "ft²": "ft2",
                                  "m2": "m2", "m²": "m2", "sqm": "m2"}  # fmt: skip
CELL_PARTS = re.compile(r"\s*(?:[,/&]|\band\b)\s*")
DIMENSION = re.compile(r"(\d+')\s*-\s*(\d)")  # 5' - 10 3/8" is written 5'-10 3/8"
QUOTES = str.maketrans({"’": "'", "‘": "'", "′": "'", "″": '"', "“": '"', "”": '"'})  # noqa: RUF001


class TableAnswer(Frozen):
    value: int | float | str
    unit: Unit | None  # None for text
    page: int
    boxes: tuple[Box, ...]  # the rows it rests on
    abstain_why: str | None = None  # set: the value is a best estimate, and why


def answer_table(query: TableQuery, tables: Sequence[Table]) -> TableAnswer | None:
    """The answer from the one table the query resolves on, or None."""
    legends = [table for table in tables if _is_legend(table)]
    candidates = [table for table in tables if not _is_legend(table) and _of_kind(table, query)]
    found = [answer for table in candidates if (answer := _on(table, query, legends))]
    return found[0] if len(found) == 1 else None


def words(text: str) -> set[str]:
    """Normalised words: case folded, synonyms mapped, a plural s dropped, stop words out."""
    found: set[str] = set()
    for word in re.findall(r"[^\W_]+", text.casefold()):
        word = SYNONYMS.get(word, word)
        if len(word) > 3 and word.endswith("s") and not word.endswith("ss"):
            word = word[:-1]
        if word not in STOP_WORDS:
            found.add(word)
    return found


def _is_legend(table: Table) -> bool:
    return bool(words(table.title or "") & LEGEND_WORDS)


def _of_kind(table: Table, query: TableQuery) -> bool:
    kind_words = KIND_WORDS.get(query.kind or "", frozenset[str]())
    return query.kind is None or bool(words(table.title or "") & kind_words)


def _flat(text: str) -> str:
    return "".join(text.translate(QUOTES).split()).casefold()


def _tokens(cell: str | None) -> set[str]:
    """A cell and each part of it ("AL-2/GL-2", "A, B", "F2 & F3"), compared without spaces."""
    if not cell:
        return set()
    return {_flat(cell), *(_flat(part) for part in CELL_PARTS.split(cell) if part.strip())}


def _cell(row: TableRow, column: int) -> str | None:
    return row.cells[column] if column < len(row.cells) else None


def _filter_columns(table: Table, wanted: TableFilter) -> list[int] | None:
    values = {_flat(value) for value in wanted.values}
    cue = words(" ".join(wanted.cue))
    named = [i for i, header in enumerate(table.columns) if words(header) & cue]
    if wanted.every:
        return named or None
    holding = [
        i
        for i in range(len(table.columns))
        if any(_tokens(_cell(row, i)) & values for row in table.rows)
    ]
    narrowed = [i for i in holding if i in named] or holding
    return narrowed if len(narrowed) == 1 else None


def _rows(table: Table, query: TableQuery) -> list[TableRow] | None:
    """The rows every filter keeps, or None when a filter's column does not resolve or a count
    or sum names no rows at all."""
    if not query.filters and query.op != "read" and not query.every_row:
        return None
    rows = list(table.rows)
    for wanted in query.filters:
        columns = _filter_columns(table, wanted)
        if columns is None:
            return None
        values = {_flat(value) for value in wanted.values}
        rows = [row for row in rows if all(_tokens(_cell(row, i)) & values for i in columns)]
    return rows


def _column(table: Table, named: Iterable[str]) -> int | None:
    """The column whose header the words cover most (then the largest share of its words)."""
    asked = words(" ".join(named))
    scores: list[tuple[int, float, int]] = []
    for i, header in enumerate(table.columns):
        heading = words(header)
        hit = len(heading & asked)
        if hit:
            scores.append((hit, hit / len(heading), i))
    if not scores:
        return None
    scores.sort(reverse=True)
    if len(scores) > 1 and scores[0][:2] == scores[1][:2]:
        return None
    return scores[0][2]


def _on(table: Table, query: TableQuery, legends: Sequence[Table]) -> TableAnswer | None:
    rows = _rows(table, query)
    if rows is None:
        return None
    boxes = tuple(row.box or table.box for row in rows) or (table.box,)
    if query.op == "count":
        return TableAnswer(value=len(rows), unit="count", page=table.page, boxes=boxes)
    columns = [_column(table, named) for named in query.column]
    if not columns or any(column is None for column in columns):
        return None
    chosen = [column for column in columns if column is not None]
    if query.op == "sum":
        return _sum(rows, chosen[0], table.page, boxes)
    if not rows:
        return None
    read = [_read(rows, column) for column in chosen]
    if any(value is None for value in read):
        return None
    texts = [value for value in read if value is not None]
    headers = [words(table.columns[column]) for column in chosen]
    keyed = any(header & KEYED_WORDS for header in headers)
    why = None
    if query.meaning or keyed:
        meant = [_meaning(text, legends) for text in texts]
        if query.meaning and any(found is None for found in meant):
            return None  # what a code means was asked, and no legend on the sheet says it
        if any(found is not None for found in meant):
            texts = [found or text for found, text in zip(meant, texts, strict=True)]
            why = MEANING_WHY
    if len(texts) == 2 and "width" in headers[0] and "height" in headers[1]:
        text = f"{texts[0]} wide x {texts[1]} high"
    else:
        text = "; ".join(texts)
    return TableAnswer(value=text, unit=None, page=table.page, boxes=boxes, abstain_why=why)


def _sum(
    rows: Sequence[TableRow], column: int, page: int, boxes: tuple[Box, ...]
) -> TableAnswer | None:
    """The sum of the printed areas; a cell that is no area ("Redundant Room") is not one, and
    the areas must share one unit."""
    total, units = 0.0, set[Unit]()
    for row in rows:
        match = AREA_CELL.match(_cell(row, column) or "")
        if match is None:
            continue
        total += float(match.group(1).replace(",", ""))
        unit = re.sub(r"[\s.]", "", (match.group(2) or "").casefold())
        if unit not in AREA_UNITS:
            return None
        units.add(AREA_UNITS[unit])
    if len(units) != 1:
        return None
    value = int(total) if total.is_integer() else round(total, 3)
    return TableAnswer(value=value, unit=units.pop(), page=page, boxes=boxes)


def _read(rows: Sequence[TableRow], column: int) -> str | None:
    """The one text the rows print in the column; None when they print different ones."""
    texts = {_flat(text): text for row in rows if (text := _cell(row, column))}
    if len(texts) != 1:
        return None
    return DIMENSION.sub(r"\1-\2", " ".join(next(iter(texts.values())).split()))


def _meaning(text: str, legends: Sequence[Table]) -> str | None:
    """The text with what its codes mean, from the legends: "F4 - RESILIENT FLOORING"; None
    when a code of it is in no legend."""
    meant: list[str] = []
    for part in CELL_PARTS.split(text):
        if not (flat := _flat(part)):
            continue
        for legend in legends:
            row = next(
                (r for r in legend.rows if _flat(_cell(r, legend.key_column) or "") == flat), None
            )
            if row is not None:
                description = next((c for c in reversed(row.cells) if c and _flat(c) != flat), None)
                if description:
                    meant.append(" ".join(description.split()))
                break
        else:
            return None
    return f"{text} - {' and '.join(meant)}" if meant else None

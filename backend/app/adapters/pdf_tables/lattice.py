"""Schedules from ruling lines: the grid the rulings draw, and the characters in its cells.

1. Rulings that touch or cross form one block; a block with at least three rows and two columns
   of cells is a candidate grid. Its rows lie between the distinct y of its horizontal rulings,
   its columns between the distinct x of its vertical ones.
2. Two grid cells are one cell when no ruling separates them (a heading over several columns,
   a header cell two rows tall).
3. Blocks stacked under each other on the same columns, a small gap apart, are one schedule: a
   header box over its body boxes (Revit draws the groups of a keynote list as separate boxes).
4. In the first block, a top row that is one cell across the whole width is the title; the
   header goes down as long as a cell crosses into the next row or a heading spans columns.
   The rows under it, and the rows of the stacked blocks, are the body. A column's header is the
   text of every header cell over it, top down ("Door" over "Width" is "Door Width").
5. A body cell holds the runs of characters that start in it, so a cell a missing ruling joins
   to the next one (a subtotal row) still gives each column its own text. A row without text is
   a gap, not a row.

A grid without a title row is left out: title blocks, revision lists and details drawn as boxes
have none.
"""

from bisect import bisect_left, bisect_right
from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from itertools import pairwise
from statistics import median

from app.adapters.pdf_tables.page import Char, Rule, TablePage
from app.core.drawing.model import Box, Table, TableRow

SNAP = 1.5  # pt: rulings this close are one line; a ruling ends this close to another to touch
COVER = 0.9  # a ruling separates two cells when it covers this share of their common edge
STACK_GAP = 3.0  # row heights: blocks closer than this under each other may be one schedule
SPACE = 0.15  # em: a gap wider than this between two characters' advances is a space
RUN_GAP = 1.0  # em: a gap wider than this starts a new run of text in a row
LINE = 0.5  # em: characters whose centres differ less than this in y are on one line
KEY_COLUMNS = 3  # the key column is looked for among the first columns
DECIMALS = 5


@dataclass(frozen=True)
class Grid:
    """One block of rulings: cell edges and which of them are drawn."""

    xs: tuple[float, ...]
    ys: tuple[float, ...]
    # drawn[k][j]: the horizontal edge at ys[k] over column j is ruled
    across: tuple[tuple[bool, ...], ...]
    # down[i][k]: the vertical edge at xs[k] beside row i is ruled
    down: tuple[tuple[bool, ...], ...]

    @property
    def box(self) -> tuple[float, float, float, float]:
        return self.xs[0], self.ys[0], self.xs[-1], self.ys[-1]

    def cell_of(self) -> list[list[int]]:
        """A label per grid cell; cells no ruling separates share it."""
        rows, cols = len(self.ys) - 1, len(self.xs) - 1
        parent = list(range(rows * cols))

        def find(a: int) -> int:
            while parent[a] != a:
                parent[a] = parent[parent[a]]
                a = parent[a]
            return a

        for i in range(rows):
            for j in range(cols):
                if j + 1 < cols and not self.down[i][j + 1]:
                    parent[find(i * cols + j)] = find(i * cols + j + 1)
                if i + 1 < rows and not self.across[i + 1][j]:
                    parent[find(i * cols + j)] = find((i + 1) * cols + j)
        return [[find(i * cols + j) for j in range(cols)] for i in range(rows)]


def read_tables(page: TablePage) -> list[Table]:
    grids = [grid for rules in _blocks(page.rules) if (grid := _grid(rules))]
    chars = _Chars(page.chars)
    tables: list[Table] = []
    for stack in _stacks(grids):
        table = _table(stack, chars, page)
        if table is not None:
            tables.append(table.model_copy(update={"id": f"t{len(tables) + 1}"}))
    return tables


# 1. Blocks of rulings, and their grids.


def _blocks(rules: Sequence[Rule]) -> list[list[Rule]]:
    """Rulings that touch or cross, transitively. Compared within buckets of the page."""
    size = 50.0
    buckets: dict[tuple[int, int], list[int]] = defaultdict(list)
    for n, rule in enumerate(rules):
        for key in _bucket_keys(rule, size):
            buckets[key].append(n)
    parent = list(range(len(rules)))

    def find(a: int) -> int:
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    for members in buckets.values():
        for at, a in enumerate(members):
            for b in members[at + 1 :]:
                if find(a) != find(b) and _touch(rules[a], rules[b]):
                    parent[find(a)] = find(b)
    groups: dict[int, list[Rule]] = defaultdict(list)
    for n, rule in enumerate(rules):
        groups[find(n)].append(rule)
    return list(groups.values())


def _bucket_keys(rule: Rule, size: float) -> Iterable[tuple[int, int]]:
    lo, hi = int((rule.start - SNAP) // size), int((rule.end + SNAP) // size)
    across = range(int((rule.at - SNAP) // size), int((rule.at + SNAP) // size) + 1)
    for along in range(lo, hi + 1):
        for at in across:
            yield (along, at) if rule.horizontal else (at, along)


def _touch(a: Rule, b: Rule) -> bool:
    if a.horizontal == b.horizontal:
        return abs(a.at - b.at) <= SNAP and a.start <= b.end + SNAP and b.start <= a.end + SNAP
    return a.start - SNAP <= b.at <= a.end + SNAP and b.start - SNAP <= a.at <= b.end + SNAP


def _levels(values: Iterable[float]) -> list[float]:
    """Distinct positions: values closer than SNAP to the previous one join its level."""
    levels: list[list[float]] = []
    for value in sorted(values):
        if levels and value - levels[-1][-1] <= SNAP:
            levels[-1].append(value)
        else:
            levels.append([value])
    return [sum(level) / len(level) for level in levels]


def _grid(rules: Sequence[Rule]) -> Grid | None:
    ys = _levels(rule.at for rule in rules if rule.horizontal)
    xs = _levels(rule.at for rule in rules if not rule.horizontal)
    if len(ys) < 2 or len(xs) < 3:  # one row of two cells; a schedule is checked later
        return None
    spans: dict[tuple[bool, int], list[tuple[float, float]]] = defaultdict(list)
    for rule in rules:
        levels = ys if rule.horizontal else xs
        level = min(range(len(levels)), key=lambda n: abs(levels[n] - rule.at))
        spans[(rule.horizontal, level)].append((rule.start, rule.end))
    merged = {key: _union(value) for key, value in spans.items()}

    def ruled(horizontal: bool, level: int, lo: float, hi: float) -> bool:
        need = (hi - lo) * COVER
        return (
            sum(
                max(0.0, min(hi, end) - max(lo, start))
                for start, end in merged.get((horizontal, level), ())
            )
            >= need
        )

    across = tuple(
        tuple(ruled(True, k, xs[j], xs[j + 1]) for j in range(len(xs) - 1)) for k in range(len(ys))
    )
    down = tuple(
        tuple(ruled(False, k, ys[i], ys[i + 1]) for k in range(len(xs))) for i in range(len(ys) - 1)
    )
    return Grid(tuple(xs), tuple(ys), across, down)


def _union(spans: list[tuple[float, float]]) -> list[tuple[float, float]]:
    out: list[tuple[float, float]] = []
    for start, end in sorted(spans):
        if out and start <= out[-1][1] + SNAP:
            out[-1] = (out[-1][0], max(out[-1][1], end))
        else:
            out.append((start, end))
    return out


# 3. Blocks stacked into one schedule.


def _row_height(grid: Grid) -> float:
    return median(b - a for a, b in pairwise(grid.ys))


def _last_row_columns(grid: Grid) -> list[float]:
    """The x of the vertical rulings beside the grid's last row."""
    return [x for x, drawn in zip(grid.xs, grid.down[-1], strict=True) if drawn]


def _same_columns(upper: Grid, lower: Grid) -> bool:
    above, below = _last_row_columns(upper), _last_row_columns(lower)
    return len(above) == len(below) and all(
        abs(a - b) <= 2 * SNAP for a, b in zip(above, below, strict=True)
    )


def _stacks(grids: list[Grid]) -> list[list[Grid]]:
    stacks: list[list[Grid]] = []
    for grid in sorted(grids, key=lambda grid: (grid.ys[0], grid.xs[0])):
        for stack in stacks:
            last = stack[-1]
            gap = grid.ys[0] - last.ys[-1]
            if 0 <= gap <= STACK_GAP * _row_height(last) and _same_columns(last, grid):
                stack.append(grid)
                break
        else:
            stacks.append([grid])
    return stacks


# Characters into text.


class _Chars:
    """The page's characters, found by box."""

    def __init__(self, chars: Sequence[Char]) -> None:
        self._chars = sorted(chars, key=lambda char: _centre(char)[1])
        self._ys = [_centre(char)[1] for char in self._chars]

    def inside(self, x0: float, y0: float, x1: float, y1: float) -> list[Char]:
        lo, hi = bisect_left(self._ys, y0), bisect_right(self._ys, y1)
        return [char for char in self._chars[lo:hi] if x0 <= _centre(char)[0] <= x1]


def _centre(char: Char) -> tuple[float, float]:
    x0, y0, x1, y1 = char.bounds
    return (x0 + x1) / 2, (y0 + y1) / 2


def _lines(chars: Iterable[Char]) -> list[list[Char]]:
    """Characters by line, top down, each line left to right."""
    lines: list[list[Char]] = []
    for char in sorted(chars, key=lambda char: _centre(char)[1]):
        if lines and abs(_centre(char)[1] - _centre(lines[-1][0])[1]) < LINE * char.size:
            lines[-1].append(char)
        else:
            lines.append([char])
    return [sorted(line, key=lambda char: char.bounds[0]) for line in lines]


def _join(line: Sequence[Char]) -> str:
    text = ""
    for before, char in zip([None, *line], line, strict=False):
        if before is not None and char.bounds[0] - before.bounds[2] > SPACE * char.size:
            text += " "
        text += char.text
    return text


def text_of(chars: Iterable[Char]) -> str | None:
    text = " ".join(_join(line) for line in _lines(chars))
    return " ".join(text.split()) or None


def _runs(line: Sequence[Char], walls: Sequence[float]) -> list[list[Char]]:
    """A line cut where the gap is wide or a ruling stands between two characters."""
    runs: list[list[Char]] = []
    for char in line:
        if runs:
            last = runs[-1][-1]
            gap = char.bounds[0] - last.bounds[2]
            wall = any(last.bounds[2] <= x <= char.bounds[0] for x in walls)
            if gap <= RUN_GAP * char.size and not wall:
                runs[-1].append(char)
                continue
        runs.append([char])
    return runs


# 4-5. Title, header and body.


@dataclass
class _Row:
    top: float
    bottom: float
    cells: list[str | None]


def _table(stack: list[Grid], chars: _Chars, page: TablePage) -> Table | None:
    first = stack[0]
    labels = first.cell_of()
    rows = len(first.ys) - 1
    start = 0
    title: str | None = None
    if len(set(labels[0])) == 1 and (rows == 1 or labels[1][0] != labels[0][0]):
        title = text_of(chars.inside(first.xs[0], first.ys[0], first.xs[-1], first.ys[1]))
        start = 1
    if len(stack) > 1:
        end = rows  # the first block is title and header; the others are the body
    else:
        end = start + 1
        while end < rows and (_crosses(labels, end) or _spans(labels[end - 1])):
            end += 1
    if end <= start or (len(stack) == 1 and end >= rows):
        return None
    columns = _body_columns(stack, end)
    if len(columns) < 2:
        return None
    header = _header(first, labels, start, end, columns, chars)
    body: list[_Row] = []
    for number, grid in enumerate(stack):
        for i in range(end if number == 0 else 0, len(grid.ys) - 1):
            body.append(_body_row(grid, i, columns, chars))
    body = [row for row in body if any(row.cells)]
    if not body or title is None:
        return None
    x0, y0 = first.xs[0], first.ys[0]
    x1, y1 = max(grid.xs[-1] for grid in stack), stack[-1].ys[-1]
    return Table(
        id="t",
        page=1,
        box=_box(x0, y0, x1, y1, page),
        title=title,
        columns=tuple(header),
        key_column=_key_column(body),
        rows=tuple(
            TableRow(cells=tuple(row.cells), box=_box(x0, row.top, x1, row.bottom, page))
            for row in body
        ),
    )


def _crosses(labels: list[list[int]], below: int) -> bool:
    """A cell of row `below - 1` reaches into row `below`."""
    return any(a == b for a, b in zip(labels[below - 1], labels[below], strict=True))


def _spans(labels: list[int]) -> bool:
    """A cell of the row covers several columns (a group heading)."""
    return len(set(labels)) < len(labels)


def _body_columns(stack: list[Grid], end: int) -> list[tuple[float, float]]:
    """The columns of the body: grid columns between the vertical rulings most body rows have."""
    first = stack[0]
    beside: list[tuple[bool, ...]] = list(first.down[end:])
    xs = first.xs
    for grid in stack[1:]:
        for i in range(len(grid.ys) - 1):
            beside.append(
                tuple(
                    any(
                        abs(x - y) <= 2 * SNAP and d
                        for y, d in zip(grid.xs, grid.down[i], strict=True)
                    )
                    for x in xs
                )
            )
    walls = [
        x
        for k, x in enumerate(xs)
        if k in (0, len(xs) - 1) or sum(row[k] for row in beside) * 2 > len(beside)
    ]
    return list(pairwise(walls))


def _header(
    grid: Grid,
    labels: list[list[int]],
    start: int,
    end: int,
    columns: list[tuple[float, float]],
    chars: _Chars,
) -> list[str]:
    """Per body column, the text of the header cells over it, top down."""
    extent: dict[int, list[float]] = {}
    for i in range(start, end):
        for j in range(len(grid.xs) - 1):
            box = extent.setdefault(
                labels[i][j], [grid.xs[j], grid.ys[i], grid.xs[j + 1], grid.ys[i + 1]]
            )
            box[:] = [
                min(box[0], grid.xs[j]),
                min(box[1], grid.ys[i]),
                max(box[2], grid.xs[j + 1]),
                max(box[3], grid.ys[i + 1]),
            ]
    texts = {label: text_of(chars.inside(*box)) for label, box in extent.items()}
    order = sorted(extent, key=lambda label: (extent[label][1], extent[label][0]))
    names: list[str] = []
    for lo, hi in columns:
        parts: list[str] = []
        for label in order:
            x0, _, x1, _ = extent[label]
            text = texts[label]
            if text and x0 < (lo + hi) / 2 < x1:
                if parts and text.casefold().startswith(parts[-1].casefold()):
                    parts[-1] = text
                else:
                    parts.append(text)
        names.append(" ".join(parts))
    return names


def _body_row(grid: Grid, i: int, columns: list[tuple[float, float]], chars: _Chars) -> _Row:
    top, bottom = grid.ys[i], grid.ys[i + 1]
    walls = [x for x, drawn in zip(grid.xs, grid.down[i], strict=True) if drawn]
    found: list[list[Char]] = [[] for _ in columns]
    for line in _lines(chars.inside(grid.xs[0], top, grid.xs[-1], bottom)):
        for run in _runs(line, walls):
            x = run[0].bounds[0]
            at = next((n for n, (lo, hi) in enumerate(columns) if lo <= x < hi), None)
            if at is not None:
                found[at].extend(run)
    return _Row(top, bottom, [text_of(part) for part in found])


def _key_column(body: list[_Row]) -> int:
    """The first column whose cells are all filled and all different: what names a row."""
    for column in range(min(KEY_COLUMNS, len(body[0].cells))):
        values = [row.cells[column] for row in body]
        keys = {" ".join(value.split()).casefold() for value in values if value}
        if len(keys) == len(values):
            return column
    return 0


def _box(x0: float, y0: float, x1: float, y1: float, page: TablePage) -> Box:
    def fraction(value: float, size: float) -> float:
        return round(min(max(value / size, 0.0), 1.0), DECIMALS)

    return (
        fraction(x0, page.width),
        fraction(y0, page.height),
        fraction(x1, page.width),
        fraction(y1, page.height),
    )

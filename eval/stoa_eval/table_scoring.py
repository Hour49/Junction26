"""Part 1 schedules: the tables a question can be about (door, window, hardware, finish and room
schedules on opening_design sheets; formats-v1-1 brief §1). Scored apart from the headline.

Per gold file with `tables` (truth `tables`, or `elements` with tables next to the plan):
- A gold table is found by a predicted table on the same page with the same title (after
  whitespace and case normalisation) or box IoU >= 0.3; one-to-one, title matches first, then the
  highest IoU.
- Rows are keyed by the cell in the gold table's `key_column` (default 0) on both sides,
  normalised; a key that repeats pairs in order of appearance. Row recall is over every gold row
  (the rows of a table not found are missed); row precision is over the rows of found tables, so an
  extra table shows as `tables_extra`, not as wrong rows.
- Cells: columns match by position (review-8 prefixed group headings, e.g. "Door Width", so header
  text is no key). In each matched row, every gold cell but the key is compared with the predicted
  cell in the same column; a column the prediction lacks makes its cells wrong. Empty and null
  cells are equal. Headers that differ after normalisation are only counted, as a sanity check.
"""

from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict, Field

from .extraction import Extraction, Table
from .geometry import iou
from .scale_scoring import Rate

TABLE_IOU_MIN = 0.3
_SLACK = 1e-9


def cell_text(value: str | None) -> str:
    """Whitespace collapsed and case folded; null is the empty string."""
    return " ".join(value.split()).casefold() if value else ""


def match_tables(gold: Sequence[Table], pred: Sequence[Table]) -> list[tuple[int, int]]:
    """One-to-one (gold index, pred index): same page, and the same title or box IoU >= 0.3."""
    candidates: list[tuple[int, float, int, int]] = []
    for g, want in enumerate(gold):
        for p, got in enumerate(pred):
            if want.page != got.page:
                continue
            title = bool(cell_text(want.title)) and cell_text(want.title) == cell_text(got.title)
            overlap = iou(want.box, got.box)
            if title or overlap >= TABLE_IOU_MIN * (1 - _SLACK):
                candidates.append((-int(title), -overlap, g, p))
    used_gold: set[int] = set()
    used_pred: set[int] = set()
    pairs: list[tuple[int, int]] = []
    for _, _, g, p in sorted(candidates):
        if g not in used_gold and p not in used_pred:
            used_gold.add(g)
            used_pred.add(p)
            pairs.append((g, p))
    return pairs


def _cell(table: Table, row: int, column: int) -> str | None:
    cells = table.rows[row].cells
    return cells[column] if column < len(cells) else None


def match_rows(gold: Table, pred: Table) -> list[tuple[int, int]]:
    """(gold row, pred row) pairs with the same normalised cell in the gold key column, in order
    of appearance. A prediction without that column matches no row."""
    key = gold.key_column
    if key >= len(pred.columns):
        return []
    queues: dict[str, list[int]] = {}
    for p in range(len(pred.rows)):
        queues.setdefault(cell_text(_cell(pred, p, key)), []).append(p)
    pairs: list[tuple[int, int]] = []
    for g in range(len(gold.rows)):
        queue = queues.get(cell_text(_cell(gold, g, key)))
        if queue:
            pairs.append((g, queue.pop(0)))
    return pairs


def headers_differ(gold: Table, pred: Table) -> int:
    """Gold columns whose header differs from the predicted one in the same position (or that the
    prediction lacks)."""
    return sum(
        n >= len(pred.columns) or cell_text(header) != cell_text(pred.columns[n])
        for n, header in enumerate(gold.columns)
    )


class TableResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    file: str
    table: str = Field(description="the gold table's id")
    title: str | None
    found: bool
    rows: Rate = Field(description="gold rows matched")
    pred_rows: int = Field(description="rows of the predicted table it was matched to")
    cells: Rate
    headers_differ: int = Field(description="sanity check only: columns with another header")


class TableScore(BaseModel):
    model_config = ConfigDict(extra="forbid")

    files: int = 0
    tables_found: Rate = Field(default_factory=Rate)
    tables_extra: int = 0
    row_recall: Rate = Field(default_factory=Rate)
    row_precision: Rate = Field(default_factory=Rate)
    cell_accuracy: Rate = Field(default_factory=Rate)
    headers_differ: int = Field(default=0, description="sanity check, not scored")
    per_table: list[TableResult] = Field(default_factory=list[TableResult])

    def add(self, gold: Extraction, pred: Extraction | None) -> None:
        gold_tables = gold.tables or []
        pred_tables = (pred.tables or []) if pred else []
        pairs = dict(match_tables(gold_tables, pred_tables))
        self.files += 1
        self.tables_extra += len(pred_tables) - len(pairs)
        for g, want in enumerate(gold_tables):
            got = pred_tables[pairs[g]] if g in pairs else None
            row_pairs = match_rows(want, got) if got else []
            cells = Rate()
            for g_row, p_row in row_pairs:
                assert got is not None  # rows only match in a found table
                for column, cell in enumerate(want.rows[g_row].cells):
                    if column != want.key_column:
                        cells.add(
                            column < len(got.columns)
                            and cell_text(cell) == cell_text(_cell(got, p_row, column))
                        )
            rows = Rate(n=len(want.rows), correct=len(row_pairs))
            differ = headers_differ(want, got) if got else 0
            self.headers_differ += differ
            self.tables_found.add(got is not None)
            _merge(self.row_recall, rows)
            _merge(self.cell_accuracy, cells)
            if got is not None:
                _merge(self.row_precision, Rate(n=len(got.rows), correct=len(row_pairs)))
            self.per_table.append(
                TableResult(
                    file=gold.file,
                    table=want.id,
                    title=want.title,
                    found=got is not None,
                    rows=rows,
                    pred_rows=len(got.rows) if got else 0,
                    cells=cells,
                    headers_differ=differ,
                )
            )


def _merge(total: Rate, part: Rate) -> None:
    total.n, total.correct = total.n + part.n, total.correct + part.correct


def _pct(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.1%}"


def format_table_section(score: TableScore) -> str:
    def ratio(rate: Rate) -> str:
        return f"{rate.correct}/{rate.n} {_pct(rate.rate)}"

    return "\n".join(
        [
            f"tables (schedules, not in the headline): {score.files} files",
            f"  tables found     {ratio(score.tables_found)}, extra predicted {score.tables_extra}",
            f"  row recall       {ratio(score.row_recall)}",
            f"  row precision    {ratio(score.row_precision)} (rows of found tables)",
            f"  cell accuracy    {ratio(score.cell_accuracy)} (non-key cells of matched rows)",
            f"  headers differ   {score.headers_differ} columns of found tables (sanity check)",
        ]
    )

"""Part 1 conflict slice: does ingestion stage 8 (a second, independent method measures the same
quantity) flag the quantities that really disagree, and only those? Scored apart from the headline
(formats-v1-1 brief §2; Bogdan 2026-11-13 23:05: a small separate slice).

The slice is the gold files that list `conflicts`. Gold lists only checked facts: `conflict`
entries (real disagreements, looked at on the drawing) and `agree` entries (two methods within
tolerance: the negatives). A predicted entry pairs with a gold entry of the same quantity and
subject, one-to-one in order. Subjects are the same when:
- sheet: always; class: the same class;
- room: the predicted room is the gold room under the Part 1 room matching (IoU >= 0.5), so the
  pipeline's own room ids work;
- apartment: the same id, or the same label.

Per quantity: found = gold `conflict` entries paired with a predicted `conflict` (recall); false
alarms = gold `agree` entries paired with a predicted `conflict`; unlisted = predicted conflicts on
slice files that pair with no gold entry (gold did not check them, so they are reported, not
judged). Predicted conflicts outside the slice are counted as not scored. A missing prediction file
finds nothing and raises no alarm.
"""

from collections.abc import Mapping

from pydantic import BaseModel, ConfigDict, Field, computed_field

from .extraction import Conflict, Extraction
from .table_scoring import cell_text


class QuantityCounts(BaseModel):
    model_config = ConfigDict(extra="forbid")

    conflicts: int = 0
    found: int = 0
    agree: int = 0
    false_alarms: int = 0
    unlisted: int = 0

    @computed_field
    @property
    def recall(self) -> float | None:
        return self.found / self.conflicts if self.conflicts else None

    @computed_field
    @property
    def false_alarm_rate(self) -> float | None:
        return self.false_alarms / self.agree if self.agree else None

    def merge(self, other: "QuantityCounts") -> None:
        for name in ("conflicts", "found", "agree", "false_alarms", "unlisted"):
            setattr(self, name, getattr(self, name) + getattr(other, name))


class ConflictFileResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    file: str
    predicted: bool
    missed: list[str] = Field(description="gold conflict ids not flagged")
    false_alarms: list[str] = Field(description="gold agree ids flagged as conflicts")
    unlisted: list[str] = Field(description="predicted conflict ids with no gold entry")


class ConflictScore(BaseModel):
    model_config = ConfigDict(extra="forbid")

    files: int = 0
    by_quantity: dict[str, QuantityCounts] = Field(default_factory=dict[str, QuantityCounts])
    not_scored: int = Field(default=0, description="predicted conflicts outside the slice")
    per_file: list[ConflictFileResult] = Field(default_factory=list[ConflictFileResult])

    @computed_field
    @property
    def overall(self) -> QuantityCounts:
        total = QuantityCounts()
        for counts in self.by_quantity.values():
            total.merge(counts)
        return total

    def add(self, gold: Extraction, pred: Extraction | None, room_map: Mapping[str, str]) -> None:
        """Score one slice file; `room_map` is predicted room id -> matched gold room id."""
        self.files += 1
        predicted = list(pred.conflicts or []) if pred else []
        used: set[int] = set()
        missed: list[str] = []
        alarms: list[str] = []
        for want in gold.conflicts or []:
            counts = self.by_quantity.setdefault(want.quantity, QuantityCounts())
            got = next(
                (
                    p
                    for p, item in enumerate(predicted)
                    if p not in used
                    and item.quantity == want.quantity
                    and same_subject(want, item, gold, pred, room_map)
                ),
                None,
            )
            if got is not None:
                used.add(got)
            flagged = got is not None and predicted[got].status == "conflict"
            if want.status == "conflict":
                counts.conflicts += 1
                counts.found += flagged
                if not flagged:
                    missed.append(want.id)
            else:
                counts.agree += 1
                counts.false_alarms += flagged
                if flagged:
                    alarms.append(want.id)
        unlisted = [
            item for p, item in enumerate(predicted) if p not in used and item.status == "conflict"
        ]
        for item in unlisted:
            self.by_quantity.setdefault(item.quantity, QuantityCounts()).unlisted += 1
        self.per_file.append(
            ConflictFileResult(
                file=gold.file,
                predicted=pred is not None,
                missed=missed,
                false_alarms=alarms,
                unlisted=[item.id for item in unlisted],
            )
        )


def same_subject(
    gold_item: Conflict,
    pred_item: Conflict,
    gold: Extraction,
    pred: Extraction | None,
    room_map: Mapping[str, str],
) -> bool:
    want, got = gold_item.subject, pred_item.subject
    if want.kind != got.kind:
        return False
    if want.kind == "sheet":
        return True
    if want.kind == "class":
        return cell_text(want.ref) == cell_text(got.ref)
    if want.kind == "room":
        return got.ref is not None and room_map.get(got.ref) == want.ref
    if want.ref == got.ref:
        return True
    labels = {a.id: cell_text(a.label) for a in gold.apartments}
    theirs = {a.id: cell_text(a.label) for a in pred.apartments} if pred else {}
    label = labels.get(want.ref or "", "")
    return bool(label) and label == theirs.get(got.ref or "", "")


def _pct(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.1%}"


def format_conflict_section(score: ConflictScore) -> str:
    lines = [
        f"conflicts (stage 8, not in the headline): {score.files} files in the slice, "
        f"{score.not_scored} predicted conflicts outside it not scored",
        f"  {'quantity':<16} {'found':>9} {'recall':>7} {'false alarms':>13} {'rate':>7} "
        f"{'unlisted':>9}",
    ]
    rows = [*sorted(score.by_quantity.items()), ("overall", score.overall)]
    for name, counts in rows:
        lines.append(
            f"  {name:<16} {counts.found:>4}/{counts.conflicts:<4} {_pct(counts.recall):>7} "
            f"{counts.false_alarms:>6}/{counts.agree:<6} {_pct(counts.false_alarm_rate):>7} "
            f"{counts.unlisted:>9}"
        )
    return "\n".join(lines)

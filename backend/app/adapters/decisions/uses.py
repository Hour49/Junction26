"""The two uses of G1main's count distributions, both off unless settings turn them on.

- `DecisionsCountExtractor` (counts): wraps another raster component (the detector) and applies
  arm F1main's swap rule. Where Gemini gives the component's count c of a family a probability
  below that family's threshold, the count becomes Gemini's own count: elements are dropped (the
  lowest `attrs.score` first) or added. An added element has no location of its own: it gets the
  box of the component's first plan (else the whole page) and `attrs.located` false, so a viewer
  can tell it from a detection. Thresholds per named arm (`SWAP_ARMS`), fitted on all of val
  and frozen; a family an arm does not list is never swapped. F1main-v8 (decide-2, fitted on
  C-yolo26s-v8 counts) is the default; S1536 (decide-4, fitted on region:C-yolo26s-1536's val
  counts, data/stoa/exp/decide/thresholds-S1536.json) swaps only the families whose val interval
  was above 0 against that detector alone.
- `DecisionsConfidence` (confidence): Gemini's probability that a family's answer on a page is
  the given count. The answering side decides what probability counts as sure.

On a Decisions error neither use guesses: the counts stay as the component read them and the
note says "confidence not available: <why>"; the confidence is None with the same note.
"""

from collections.abc import Mapping
from dataclasses import dataclass

from app.adapters.decisions.client import DecisionsError
from app.adapters.decisions.g1main import FAMILIES, G1MainReader, PageCounts
from app.core.drawing.model import Element, ElementClass
from app.core.errors import InvalidInputError
from app.core.pipeline.model import DrawingFile, Extracted, Sheet
from app.core.pipeline.ports import DrawingFiles, Extractor

# arm -> family -> swap when P_gemini(component's count) < this (val, frozen from all 376 pages)
SWAP_ARMS: Mapping[str, Mapping[str, float]] = {
    "F1main-v8": {"toilet": 0.05, "shower+bathtub": 0.25, "sauna": 0.05},
    # val vs region:C-yolo26s-1536 alone: shower+bathtub +4.4 pp [+0.9, +7.9], sauna +1.5
    # [+0.4, +3.0], all +0.6 [+0.2, +0.9]; sink, toilet, plan dropped (intervals reach 0)
    "S1536": {"shower+bathtub": 0.15, "sauna": 0.05},
}
DEFAULT_ARM = "F1main-v8"
SWAP_BELOW = SWAP_ARMS[DEFAULT_ARM]
# family -> (the element classes it counts, the class an added element gets)
CLASSES: Mapping[str, tuple[tuple[ElementClass, ...], ElementClass]] = {
    "toilet": (("toilet",), "toilet"),
    "shower+bathtub": (("shower", "bathtub"), "shower"),  # dev gold: 4610 showers, 312 tubs
    "sauna": (("sauna_stove",), "sauna_stove"),  # a detector reads stoves, not sauna rooms
}
UNAVAILABLE = "confidence not available"


def swapped(
    count: int, page: PageCounts, family: str, below: Mapping[str, float] = SWAP_BELOW
) -> int:
    """F1main's rule: Gemini's own count when it gives `count` less than the threshold."""
    dist = page.families[family]
    return dist.top if dist.p(count) < below.get(family, 0.0) else count


def _score(element: Element) -> float:
    value = element.attrs.get("score")
    return float(value) if isinstance(value, int | float) and not isinstance(value, bool) else -1.0


class DecisionsCountExtractor:
    def __init__(
        self,
        inner: Extractor,
        files: DrawingFiles,
        reader: G1MainReader,
        *,
        arm: str = DEFAULT_ARM,
    ) -> None:
        if arm not in SWAP_ARMS:
            raise InvalidInputError(
                f"decisions: unknown swap arm {arm!r}; arms are {', '.join(SWAP_ARMS)}"
            )
        self._inner = inner
        self._files = files
        self._reader = reader
        self._below = SWAP_ARMS[arm]
        self.arm = arm

    def extract(self, source: DrawingFile, sheet: Sheet) -> Extracted:
        found = self._inner.extract(source, sheet)
        try:
            page = self._reader.read(self._files.read(source.path))
        except DecisionsError as error:
            note = f"decisions: {UNAVAILABLE}: {error}; counts left as read"
            return found.model_copy(update={"notes": (*found.notes, note)})
        elements = list(found.elements)
        changes: list[str] = []
        for family, (classes, added) in CLASSES.items():
            if found.read is not None and not set(classes) <= set(found.read):
                continue  # the component did not look for it: no count to check
            mine = [e for e in elements if e.class_ in classes]
            count = len(mine)
            target = swapped(count, page, family, self._below)
            if target == count:
                continue
            p = page.families[family].p(count)
            changes.append(f"{family} {count} -> {target} (P({count}) = {p:.3f})")
            if target < count:
                drop = {
                    e.id for e in sorted(mine, key=lambda e: (_score(e), e.id))[: count - target]
                }
                elements = [e for e in elements if e.id not in drop]
            else:
                box = found.plans[0].box if found.plans else (0.0, 0.0, 1.0, 1.0)
                plan = found.plans[0].id if found.plans else None
                for n in range(target - count):
                    elements.append(
                        Element(
                            id=f"decisions-{family}-{n + 1}", class_=added, page=1, plan=plan,
                            box=box,
                            attrs={"located": False, "source": "decisions",
                                   "p": round(page.families[family].p(target), 4)},
                        )
                    )  # fmt: skip
        note = f"decisions {self.arm}: " + ("; ".join(changes) if changes else "counts kept")
        return found.model_copy(
            update={"elements": tuple(elements), "notes": (*found.notes, f"{note} ({page.note})")}
        )


@dataclass(frozen=True)
class Confidence:
    value: float | None  # None: no probability (the note says why)
    note: str
    agrees: bool | None = None  # Gemini's most likely count is the answered one


class DecisionsConfidence:
    """Gemini's probability for an answer, by the drawing's path, the family as the template
    parser names it (`door`, `room:wc`...) and the answered count."""

    def __init__(self, files: DrawingFiles, reader: G1MainReader) -> None:
        self._files = files
        self._reader = reader
        self._pages: dict[str, PageCounts] = {}  # per instance: one read per page

    def probability(self, path: str, family: str, value: object) -> Confidence:
        if family not in FAMILIES:
            return Confidence(None, f"decisions: no question for {family}")
        if isinstance(value, bool) or not isinstance(value, int | float) or value != int(value):
            return Confidence(None, f"decisions: {value!r} is not a count")
        try:
            if path not in self._pages:
                self._pages[path] = self._reader.read(self._files.read(path))
        except DecisionsError as error:
            return Confidence(None, f"decisions: {UNAVAILABLE}: {error}")
        page, count = self._pages[path], int(value)
        counts = page.families[family]
        return Confidence(counts.p(count), f"decisions: {page.note}", agrees=counts.top == count)

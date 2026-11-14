"""Rebuild room_labels.json, the table from a printed room label to a room type.

Only the dev split of the CubiCasa5K extraction gold is read (decision 0003): every gold room's
`label` (what the annotator typed for the room, the printed abbreviation) and `type`. Labels are
folded the way the reader folds what it reads (`fold`), and each folded label keeps the type most
of its rooms have. With a second argument (data/stoa/exp/split.json) only the `train` part's
files are read, so the experiment's val and test images stay out of the table. The output is
aggregate vocabulary (label, type, how many dev rooms, the share that agrees), not dataset rows.
A label seen on fewer than MIN_ROOMS rooms, or whose type agrees on less than MIN_SHARE of them,
is left out: the reader then makes no room of it.

Run from backend/:
    uv run python -m app.adapters.raster_ocr.build_room_labels \
        ../data/stoa/extraction_gold/cubicasa5k ../data/stoa/exp/split.json
"""

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

from app.adapters.raster_ocr.labels import fold

MIN_ROOMS = 5
MIN_SHARE = 0.6
# Gold labels that are no printed text: the annotation tool's defaults.
NOT_PRINTED = frozenset({"UNDEFINED", "ULKOTILA"})
OUT = Path(__file__).with_name("room_labels.json")


def build(gold_dir: Path, only: set[str] | None = None) -> dict[str, dict[str, object]]:
    types: defaultdict[str, Counter[str]] = defaultdict(Counter)
    for path in sorted(gold_dir.glob("*.json")):
        gold = json.loads(path.read_text(encoding="utf-8"))
        if gold.get("split") != "dev" or (only is not None and gold["file"] not in only):
            continue
        for room in gold.get("rooms", []):
            key = fold(room.get("label") or "")
            if key and key not in NOT_PRINTED:
                types[key][room["type"]] += 1
    table: dict[str, dict[str, object]] = {}
    for key in sorted(types):
        counts = types[key]
        kind, agree = counts.most_common(1)[0]
        rooms = sum(counts.values())
        if rooms >= MIN_ROOMS and agree / rooms >= MIN_SHARE:
            table[key] = {"type": kind, "rooms": rooms, "share": round(agree / rooms, 3)}
    return table


def main() -> None:
    only = None
    if len(sys.argv) > 2:
        parts = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))["parts"]
        only = set(parts["train"]["files"])
    table = build(Path(sys.argv[1]), only)
    OUT.write_text(json.dumps(table, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{len(table)} labels -> {OUT}")


if __name__ == "__main__":
    main()

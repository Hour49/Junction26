"""Where recorded runs live: one JSON file per run in eval/results/runs/ (tracked, aggregates only).

Bogdan, 2026-11-13 ~22:48: "also make sure all the runs of the golden dataset, will be saved
somewhere so at the end we will be able to show the improvement". One file per run (not one shared
JSONL) so that PRs from several agents never conflict. The full score JSON of a run goes to the
gitignored data/stoa/golden/runs/ under the same stem; the history file keeps its sha256.
"""

import json
import re
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import ValidationError

from .models import ExtractionRecord, RunRecord

Part = Literal["answering", "extraction"]
Record = RunRecord | ExtractionRecord


def slug(name: str) -> str:
    """A file-name-safe form of a method name: lowercase, runs of other characters become "-"."""
    text = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return text[:48].rstrip("-") or "run"


def run_stem(now: datetime, part: Part, name: str, folders: Sequence[Path]) -> str:
    """`<YYYYMMDD-HHMMSS>-<part>-<slug>`, with -2, -3, ... when a file of that stem already
    exists in any of `folders` (two runs in the same second)."""
    base = f"{now:%Y%m%d-%H%M%S}-{part}-{slug(name)}"
    stem, n = base, 1
    while any((folder / f"{stem}.json").exists() for folder in folders):
        n += 1
        stem = f"{base}-{n}"
    return stem


def write_record(path: Path, record: Record) -> None:
    """Write one run's file; an existing file is never overwritten."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as out:
        out.write(record.model_dump_json(indent=2) + "\n")


def parse_record(text: str, where: str) -> Record:
    model = ExtractionRecord if json.loads(text).get("part") == "extraction" else RunRecord
    try:
        return model.model_validate_json(text)
    except ValidationError as error:
        raise ValueError(f"{where}: {error}") from error


def read_records(folder: Path) -> list[Record]:
    """Every run file in `folder`, oldest first (ties by file name)."""
    paths = sorted(folder.glob("*.json")) if folder.is_dir() else []
    records = [(parse_record(path.read_text("utf-8"), str(path)), path.name) for path in paths]
    return [
        record for record, _ in sorted(records, key=lambda pair: (pair[0].recorded_at, pair[1]))
    ]


def part_of(record: Record) -> Part:
    return "extraction" if isinstance(record, ExtractionRecord) else "answering"


def migrate_jsonl(source: Path, folder: Path) -> list[Path]:
    """Move every row of the old shared runs.jsonl into its own file (the file is left in place)."""
    written: list[Path] = []
    for lineno, line in enumerate(source.read_text("utf-8").splitlines(), 1):
        if not line.strip():
            continue
        record = parse_record(line, f"{source}:{lineno}")
        stem = run_stem(record.recorded_at, part_of(record), record.name, [folder])
        write_record(folder / f"{stem}.json", record)
        written.append(folder / f"{stem}.json")
    return written

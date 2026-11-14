"""The licence credit of a drawing that came from the Stoa dataset or the Commons demo photos.

An upload keeps no dataset path, so a file is found by its content: the dataset files of the same
size are hashed (once, then cached) and the one with the same sha256 gives the credit. Where the
credit comes from:

- `<dataset>/data/<source>/LICENSE.md`: the file's own row of the `| file | title | licence |
  credit | source |` table; else the row of a file with the same name and another extension (the
  dataset README: the same drawing in another format); else the source's `All files: ...` line.
- `<commons>/manifest.jsonl`: one JSON line per photo, `file`, `author` (HTML), `licence`,
  `source`.

Anything else, such as a user's own drawing, has no credit (None).
"""

import hashlib
import html
import json
import re
import threading
from pathlib import Path, PurePosixPath

TAG = re.compile(r"<[^>]+>")
ALL_FILES = "All files: "


def cells(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def with_licence(credit: str, licence: str) -> str:
    """The credit, with its licence named unless the credit already names it."""
    plain = licence.replace("-", " ").lower()
    return credit if plain in credit.replace("-", " ").lower() else f"{credit} ({licence})"


def parse_licence(text: str) -> tuple[dict[str, str], str | None]:
    """A source's LICENSE.md: the credit of each file in its table (path relative to the source
    folder), and the line that covers every file, if it has one."""
    by_file: dict[str, str] = {}
    every: str | None = None
    header: list[str] | None = None
    for line in text.splitlines():
        if line.startswith(ALL_FILES):
            every = line.removeprefix(ALL_FILES).strip()
        elif not line.startswith("|"):
            header = None
        elif header is None:
            header = cells(line)
        elif not set(line) <= set("|-: ") and {"file", "licence", "credit"} <= set(header):
            row = dict(zip(header, cells(line), strict=False))
            by_file[row["file"]] = with_licence(row["credit"], row["licence"])
    return by_file, every


def commons_credit(record: dict[str, str]) -> str:
    author = html.unescape(TAG.sub("", record.get("author", ""))).strip() or "unknown author"
    return f"{author}, via Wikimedia Commons ({record['licence']}), {record['source']}"


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def source_credits(licence: Path) -> dict[Path, str | None]:
    """The credit of every file in the folder of a source's LICENSE.md."""
    folder = licence.parent
    by_file, every = parse_licence(licence.read_text(encoding="utf-8"))
    by_stem = {str(PurePosixPath(name).with_suffix("")): c for name, c in by_file.items()}
    credits: dict[Path, str | None] = {}
    for path in sorted(folder.rglob("*")):
        if path == licence or not path.is_file():
            continue
        name = path.relative_to(folder).as_posix()
        stem = str(PurePosixPath(name).with_suffix(""))
        credits[path] = by_file.get(name) or by_stem.get(stem) or every
    return credits


def manifest_credits(folder: Path) -> dict[Path, str | None]:
    """The credit of every photo the Commons manifest lists."""
    credits: dict[Path, str | None] = {}
    for line in (folder / "manifest.jsonl").read_text(encoding="utf-8").splitlines():
        if line.strip():
            record = json.loads(line)
            if (folder / record["file"]).is_file():
                credits[folder / record["file"]] = commons_credit(record)
    return credits


class DatasetCredits:
    """Credits of the files under `dataset` (the junction-dataset folder) and `commons`. A folder
    that does not exist gives no credits. The index is built on the first lookup."""

    def __init__(self, dataset: Path | None, commons: Path | None) -> None:
        self._dataset = dataset
        self._commons = commons
        self._lock = threading.Lock()
        self._by_size: dict[int, list[Path]] | None = None
        self._credit: dict[Path, str | None] = {}
        self._sha: dict[Path, str] = {}

    def of(self, size: int, sha256: str) -> str | None:
        with self._lock:
            for path in self._index().get(size, []):
                if path not in self._sha:
                    self._sha[path] = sha256_of(path)
                if self._sha[path] == sha256:
                    return self._credit[path]
        return None

    def _index(self) -> dict[int, list[Path]]:
        if self._by_size is None:
            credits: dict[Path, str | None] = {}
            if self._dataset is not None:
                for licence in sorted(self._dataset.glob("data/*/LICENSE.md")):
                    credits |= source_credits(licence)
            if self._commons is not None and (self._commons / "manifest.jsonl").is_file():
                credits |= manifest_credits(self._commons)
            self._credit = credits
            self._by_size = {}
            for path in credits:
                self._by_size.setdefault(path.stat().st_size, []).append(path)
        return self._by_size

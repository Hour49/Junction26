"""The realistic demo archive: real dataset files of every kind ingest reads, in one zip.

    cd backend && uv run python scripts/make_demo_archive.py [--out <zip>]

The files are listed in scripts/demo_archive.json (repo-relative paths, read in place: partner
data never goes into the repo). The default out is data/demo/demo-project.zip (gitignored).

Each file's licence is checked when the zip is built: it must match the source's own record
(the row for the file in its LICENSE.md table, the LICENSE.md "All files:" line, or the
manifest.jsonl next to a Commons photo) and be CC BY, CC BY-SA, CC0 or MIT, or CubiCasa's
CC BY-NC-SA 4.0 for this prototype. The zip carries a CREDITS.md with each file's credit.
"""

import argparse
import html
import io
import json
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
LIST = Path(__file__).with_name("demo_archive.json")
DEFAULT_OUT = REPO / "data" / "demo" / "demo-project.zip"
ZIP_TIME = (2026, 11, 14, 0, 0, 0)
OPEN = re.compile(r"CC-BY(-SA)?-\d\.\d|CC0-1\.0|MIT")
PROTOTYPE_ONLY = frozenset({"CC-BY-NC-SA-4.0"})
ALL_FILES = re.compile(r"^All files: (\S+)\. Credit: (.+)$", re.MULTILINE)
TAG = re.compile(r"<[^>]+>")


class DemoArchiveError(ValueError):
    pass


@dataclass(frozen=True)
class Credit:
    title: str
    licence: str
    credit: str
    source: str


def allowed(licence: str) -> bool:
    return bool(OPEN.fullmatch(licence)) or licence in PROTOTYPE_ONLY


def credit_of(path: Path) -> Credit:
    """The licence record of a dataset file: the manifest.jsonl next to it (Commons photos) or
    the nearest LICENSE.md above it (dataset sources)."""
    manifest = path.with_name("manifest.jsonl")
    if manifest.is_file():
        for line in manifest.read_text(encoding="utf-8").splitlines():
            row = json.loads(line)
            if row["file"] == path.name:
                author = html.unescape(TAG.sub("", row["author"])).strip()
                licence = row["licence"].replace(" ", "-")
                return Credit(row["title"], licence, f"{author}, {row['licence']}", row["source"])
        raise DemoArchiveError(f"{path.name} is not in {manifest}")
    for folder in path.parents:
        record = folder / "LICENSE.md"
        if record.is_file():
            return _from_licence_md(record, path.relative_to(folder).as_posix())
    raise DemoArchiveError(f"no LICENSE.md or manifest.jsonl above {path}")


def _from_licence_md(record: Path, name: str) -> Credit:
    """The file's row in the `| file | title | licence | credit | source |` table, else the
    source-wide "All files: <licence>. Credit: <credit>" line."""
    text = record.read_text(encoding="utf-8")
    for line in text.splitlines():
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if line.startswith("|") and len(cells) == 5 and cells[0] == name:
            return Credit(cells[1], cells[2], cells[3], cells[4])
    found = ALL_FILES.search(text)
    if found is None:
        raise DemoArchiveError(f"{name} has no row in {record} and no 'All files:' line")
    return Credit(name.rsplit("/", 1)[-1], found[1], found[2], "")


def checked(entries: list[dict[str, Any]], root: Path) -> list[tuple[dict[str, Any], Credit]]:
    """Each listed file with its credit; refuses a missing file, a repeated zip name, or a
    licence that is not allowed or not the one the source records."""
    names = [entry["name"] for entry in entries]
    if len(set(names)) != len(names):
        raise DemoArchiveError("a zip name is listed twice")
    out: list[tuple[dict[str, Any], Credit]] = []
    for entry in entries:
        path = root / entry["path"]
        if not path.is_file():
            raise DemoArchiveError(f"{entry['path']} is missing (fetch the dataset first)")
        credit = credit_of(path)
        if credit.licence != entry["licence"]:
            raise DemoArchiveError(
                f"{entry['path']}: listed as {entry['licence']}, its source says {credit.licence}"
            )
        if not allowed(credit.licence):
            raise DemoArchiveError(f"{entry['path']}: {credit.licence} is not allowed in the demo")
        out.append((entry, credit))
    return out


def credits_md(files: list[tuple[dict[str, Any], Credit]]) -> str:
    lines = [
        "# Credits",
        "",
        "Files collected for a demo of a hackathon prototype; none was edited for this archive.",
        "Each keeps its own licence. CC BY-NC-SA 4.0 files (CubiCasa5K): non-commercial use only.",
        "",
    ]
    for entry, credit in files:
        source = f" Source: {credit.source}." if credit.source else ""
        lines.append(
            f"- `{entry['name']}`: {credit.title.removeprefix('File:')}. "
            f"Licence: {credit.licence}. Credit: {credit.credit.rstrip('.')}.{source}"
        )
    return "\n".join(lines) + "\n"


def build_archive(entries: list[dict[str, Any]], root: Path) -> bytes:
    """The zip: every listed file under its zip name, then CREDITS.md, with fixed times so the
    same list gives the same bytes."""
    files = checked(entries, root)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, data in [
            *((entry["name"], (root / entry["path"]).read_bytes()) for entry, _ in files),
            ("CREDITS.md", credits_md(files).encode()),
        ]:
            archive.writestr(zipfile.ZipInfo(name, ZIP_TIME), data, zipfile.ZIP_DEFLATED)
    return buffer.getvalue()


def main() -> None:
    parser = argparse.ArgumentParser(description="Writes the realistic demo archive.")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    out: Path = parser.parse_args().out
    entries = json.loads(LIST.read_text(encoding="utf-8"))["files"]
    data = build_archive(entries, REPO)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(data)
    print(f"wrote {out} ({len(entries)} files + CREDITS.md, {len(data)} bytes)")


if __name__ == "__main__":
    main()

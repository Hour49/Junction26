"""The licence credit of a drawing: found by content in a synthetic dataset's LICENSE.md tables
and a synthetic Commons manifest, never in data/."""

import hashlib
import json
from pathlib import Path

from conftest import upload
from fastapi.testclient import TestClient

from app.adapters.credits import DatasetCredits, parse_licence
from app.composition import build_ingest
from app.main import create_app
from app.settings import Settings

TABLE = """# plans

Intro text, with | a pipe that is not a table.

All files: CC-BY-4.0. Credit: Plans dataset, CC BY 4.0.

## Files

| file | title | licence | credit | source |
|---|---|---|---|---|
| a.pdf | Plan A | CC-BY-SA-4.0 | Ana; Own work (CC BY-SA 4.0) | https://example.org/a |
| sub/b.jpg | Plan B | PDM | Archive of B | https://example.org/b |
"""


def write(path: Path, data: bytes) -> bytes:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return data


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def test_licence_table_gives_each_file_its_line_with_the_licence_named_once() -> None:
    by_file, every = parse_licence(TABLE)
    assert by_file == {"a.pdf": "Ana; Own work (CC BY-SA 4.0)", "sub/b.jpg": "Archive of B (PDM)"}
    # the frontend writes "Credit: " before it: the line's own "<licence>. Credit: " goes (R3-qa2-1)
    assert every == "Plans dataset, CC BY 4.0."


def test_a_source_line_that_does_not_name_its_licence_gets_it_once() -> None:
    _, every = parse_licence("All files: PDM. Credit: Archive of plans\n")
    assert every == "Archive of plans (PDM)"


def test_a_file_is_credited_by_its_content_its_row_its_twin_or_the_source_line(
    tmp_path: Path,
) -> None:
    source = tmp_path / "dataset" / "data" / "plans"
    write(source / "LICENSE.md", TABLE.encode())
    a = write(source / "a.pdf", b"%PDF a")
    b_svg = write(source / "sub" / "b.svg", b"<svg>b</svg>")  # not listed: its twin b.jpg is
    other = write(source / "c.png", b"png c")  # not listed at all: the source's line
    own = b"%PDF a user's own"  # same size as a.pdf, other content
    credits = DatasetCredits(tmp_path / "dataset", None)

    assert credits.of(len(a), sha(a)) == "Ana; Own work (CC BY-SA 4.0)"
    assert credits.of(len(b_svg), sha(b_svg)) == "Archive of B (PDM)"
    assert credits.of(len(other), sha(other)) == "Plans dataset, CC BY 4.0."
    assert credits.of(len(own), sha(own)) is None


def test_a_commons_photo_is_credited_from_its_manifest_without_html(tmp_path: Path) -> None:
    photo = write(tmp_path / "photos" / "009.jpg", b"jpeg 009")
    record = {
        "file": "009.jpg",
        "licence": "CC BY-SA 4.0",
        "author": '<a href="//commons.wikimedia.org/wiki/User:X" title="User:X">Tom &amp; X</a>',
        "source": "https://commons.wikimedia.org/wiki/File:Plan.jpg",
    }
    (tmp_path / "photos" / "manifest.jsonl").write_text(json.dumps(record) + "\n")
    credits = DatasetCredits(tmp_path / "missing", tmp_path / "photos")

    assert credits.of(len(photo), sha(photo)) == (
        "Tom & X, via Wikimedia Commons (CC BY-SA 4.0), "
        "https://commons.wikimedia.org/wiki/File:Plan.jpg"
    )


def test_the_drawing_view_carries_the_credit_of_a_dataset_file_and_none_for_an_upload(
    settings: Settings, plan_pdf: bytes
) -> None:
    source = settings.credit_dataset / "data" / "plans"
    write(source / "LICENSE.md", TABLE.encode())
    write(source / "a.pdf", plan_pdf)
    ingest = build_ingest(settings, settings.projects_dir, background=False)
    client = TestClient(create_app(settings, ingest))

    dataset_id = client.get(f"/api/projects/{upload(client, plan_pdf)}").json()["drawings"][0]
    own_pdf = plan_pdf.replace(b"%%EOF", b"%%EOF\n% own copy")
    own_id = client.get(f"/api/projects/{upload(client, own_pdf)}").json()["drawings"][0]

    shown = client.get(f"/api/drawings/{dataset_id['drawing_id']}").json()
    assert shown["credit"] == "Ana; Own work (CC BY-SA 4.0)"
    assert client.get(f"/api/drawings/{own_id['drawing_id']}").json()["credit"] is None

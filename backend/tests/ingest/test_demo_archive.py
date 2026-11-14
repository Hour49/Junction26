"""The realistic demo archive builder (scripts/make_demo_archive.py), on files made here: the
dataset itself never goes into tests."""

import io
import json
import zipfile
from pathlib import Path

import pytest

from scripts.make_demo_archive import (
    LIST,
    DemoArchiveError,
    allowed,
    build_archive,
    credit_of,
)

TABLE = """# models

| file | title | licence | credit | source |
| --- | --- | --- | --- | --- |
| house.ifc | A house | CC-BY-4.0 | Someone (2022), CC BY 4.0 | https://example.org/house |
| bridge.ifc | A bridge | CC-BY-ND-3.0 | Someone else | https://example.org/bridge |
"""
ALL_FILES = "# plans\n\nAll files: CC-BY-NC-SA-4.0. Credit: Plan Co., CC BY-NC-SA 4.0.\n"
PHOTO = {
    "file": "001.jpg",
    "title": "File:Escape plan.jpg",
    "licence": "CC BY-SA 3.0",
    "author": '<a href="//commons.wikimedia.org/wiki/User:A">A &amp; B</a>',
    "source": "https://commons.wikimedia.org/wiki/File:Escape_plan.jpg",
}


@pytest.fixture
def root(tmp_path: Path) -> Path:
    for folder, record, name in [
        ("data/models", TABLE, "house.ifc"),
        ("data/models", TABLE, "bridge.ifc"),
        ("data/plans", ALL_FILES, "sub/plan.png"),
    ]:
        (tmp_path / folder / name).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / folder / "LICENSE.md").write_text(record)
        (tmp_path / folder / name).write_bytes(name.encode())
    photos = tmp_path / "photos"
    photos.mkdir()
    (photos / "manifest.jsonl").write_text(json.dumps(PHOTO) + "\n")
    (photos / "001.jpg").write_bytes(b"jpeg")
    return tmp_path


def entry(path: str, licence: str) -> dict[str, str]:
    return {"path": path, "name": f"demo/{Path(path).name}", "licence": licence}


def test_credit_comes_from_the_table_row_the_all_files_line_or_the_manifest(root: Path) -> None:
    house = credit_of(root / "data/models/house.ifc")
    assert (house.title, house.licence, house.source) == (
        "A house",
        "CC-BY-4.0",
        "https://example.org/house",
    )
    plan = credit_of(root / "data/plans/sub/plan.png")
    assert (plan.title, plan.licence, plan.credit) == (
        "plan.png",
        "CC-BY-NC-SA-4.0",
        "Plan Co., CC BY-NC-SA 4.0.",
    )
    photo = credit_of(root / "photos/001.jpg")
    assert (photo.licence, photo.credit) == ("CC-BY-SA-3.0", "A & B, CC BY-SA 3.0")


def test_a_licence_the_source_does_not_record_or_that_is_not_allowed_is_refused(
    root: Path,
) -> None:
    with pytest.raises(DemoArchiveError, match=r"its source says CC-BY-4\.0"):
        build_archive([entry("data/models/house.ifc", "CC0-1.0")], root)
    with pytest.raises(DemoArchiveError, match=r"CC-BY-ND-3\.0 is not allowed"):
        build_archive([entry("data/models/bridge.ifc", "CC-BY-ND-3.0")], root)
    with pytest.raises(DemoArchiveError, match="missing"):
        build_archive([entry("data/models/gone.ifc", "CC-BY-4.0")], root)


def test_the_zip_holds_each_file_and_its_credits_and_is_the_same_every_time(root: Path) -> None:
    entries = [
        entry("data/models/house.ifc", "CC-BY-4.0"),
        entry("data/plans/sub/plan.png", "CC-BY-NC-SA-4.0"),
        entry("photos/001.jpg", "CC-BY-SA-3.0"),
    ]
    data = build_archive(entries, root)
    assert data == build_archive(entries, root)
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        assert archive.namelist() == [
            "demo/house.ifc",
            "demo/plan.png",
            "demo/001.jpg",
            "CREDITS.md",
        ]
        assert archive.read("demo/plan.png") == b"sub/plan.png"
        credits = archive.read("CREDITS.md").decode()
    assert "`demo/001.jpg`: Escape plan.jpg. Licence: CC-BY-SA-3.0. Credit: A & B" in credits
    assert ".." not in credits


def test_the_committed_list_names_each_file_once_with_an_allowed_licence() -> None:
    files = json.loads(LIST.read_text())["files"]
    assert 15 <= len(files) <= 25
    assert len({file["name"] for file in files}) == len(files)
    assert all(allowed(file["licence"]) for file in files)
    assert all(file["path"].startswith("data/stoa/") for file in files)

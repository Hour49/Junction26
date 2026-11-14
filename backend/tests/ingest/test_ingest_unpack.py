"""Safe unpacking: paths, links, bombs, caps, nesting. Each refused entry is listed with why."""

import io
import stat
import zipfile

import pytest

from app.adapters.archive import ZipUnpacker
from app.adapters.archive.unpack import safe_path
from app.core.errors import InvalidInputError
from app.core.ingest.model import Entry


def zipped(*entries: tuple[str | zipfile.ZipInfo, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, data in entries:
            archive.writestr(name, data, compress_type=zipfile.ZIP_DEFLATED)
    return buffer.getvalue()


def unpack(data: bytes, **caps: int) -> dict[str, Entry]:
    return {entry.path: entry for entry in ZipUnpacker(**caps).entries("upload.zip", data)}


@pytest.mark.parametrize(
    "name",
    ["../up.pdf", "a/../../up.pdf", "/etc/passwd", "C:/x.pdf", "a\\..\\..\\up.pdf", "a/\x01b"],
)
def test_a_path_that_could_leave_the_folder_is_refused(name: str) -> None:
    assert safe_path(name) is None
    (entry,) = unpack(zipped((name, b"x"))).values()
    assert entry.data is None and entry.refused is not None
    assert entry.refused.startswith("unsafe path")


def test_ordinary_paths_are_kept_and_backslashes_become_slashes() -> None:
    assert safe_path("plans/floor 2/a.pdf") == "plans/floor 2/a.pdf"
    assert safe_path("plans\\a.pdf") == "plans/a.pdf"
    found = unpack(zipped(("plans/a.pdf", b"%PDF-1.7"), ("dir/", b"")))
    assert list(found) == ["plans/a.pdf"]  # folders are not files
    assert found["plans/a.pdf"].data == b"%PDF-1.7"


def test_a_symlink_is_refused() -> None:
    link = zipfile.ZipInfo("plans/link.pdf")
    link.external_attr = (stat.S_IFLNK | 0o777) << 16
    (entry,) = unpack(zipped((link, b"/etc/passwd"))).values()
    assert entry.refused == "a symbolic link: links are not followed"


def test_a_zip_bomb_is_refused_by_its_ratio() -> None:
    found = unpack(zipped(("zeros.bin", b"\0" * (8 * 2**20)), ("ok.txt", b"fine")))
    assert found["zeros.bin"].refused is not None
    assert "zip bomb" in found["zeros.bin"].refused
    assert found["ok.txt"].data == b"fine"


def test_the_per_file_and_total_caps() -> None:
    noise = bytes(range(256)) * 64  # 16 kB that does not compress much
    found = unpack(zipped(("a", noise), ("b", noise), ("big", noise * 4)),
                   max_file=20_000, max_total=30_000)  # fmt: skip
    assert found["a"].data == noise
    assert found["b"].refused == "the archive is over its total cap of 0 MB"
    assert found["big"].refused == "over the per-file cap of 0 MB"


def test_a_header_that_lies_about_the_size_is_caught_while_reading() -> None:
    data = bytearray(zipped(("a.txt", b"y" * 5000)))
    archive = zipfile.ZipFile(io.BytesIO(bytes(data)))
    info = archive.infolist()[0]
    # make the central directory claim 10 bytes; the stream still holds 5000
    central = data.rfind(b"PK\x01\x02")
    data[central + 24 : central + 28] = (10).to_bytes(4, "little")
    local = info.header_offset
    data[local + 22 : local + 26] = (10).to_bytes(4, "little")
    (entry,) = unpack(bytes(data), max_file=1000).values()
    # zipfile reads no more than the declared size, so the lie ends in a checksum error
    assert entry.data is None
    assert entry.refused == "corrupt entry: Bad CRC-32 for file 'a.txt'"


def test_the_file_count_cap() -> None:
    found = unpack(zipped(*((f"{n}.txt", b"x") for n in range(5))), max_entries=3)
    assert [entry.refused for entry in found.values()][3:] == [
        "the archive has more than 3 files"
    ] * 2


def test_a_zip_inside_is_unpacked_one_level_and_no_deeper() -> None:
    deepest = zipped(("deep.txt", b"deep"))
    inner = zipped(("plan.txt", b"inner"), ("more.zip", deepest))
    found = unpack(zipped(("top.txt", b"top"), ("sub/inner.zip", inner)))
    assert found["sub/inner.zip/plan.txt"].data == b"inner"
    refused = found["sub/inner.zip/more.zip"].refused
    assert refused is not None and "only one level" in refused


def test_a_single_file_is_a_one_file_project_named_by_its_upload() -> None:
    (entry,) = ZipUnpacker().entries("C:\\Users\\me\\plan.pdf", b"%PDF-1.7").__iter__()
    assert (entry.path, entry.data) == ("plan.pdf", b"%PDF-1.7")


def test_an_office_file_is_one_file_not_an_archive() -> None:
    docx = zipped(("[Content_Types].xml", b"<Types/>"), ("word/document.xml", b"<w/>"))
    (entry,) = ZipUnpacker().entries("spec.docx", docx)
    assert (entry.path, entry.data) == ("spec.docx", docx)


def test_an_encrypted_entry_is_refused() -> None:
    data = bytearray(zipped(("secret.txt", b"x")))
    central = data.rfind(b"PK\x01\x02")
    data[central + 8] |= 0x1  # the central directory's flag bits: encrypted
    (entry,) = unpack(bytes(data)).values()
    assert entry.refused == "an encrypted zip entry"


def test_a_corrupt_entry_is_refused_and_an_unreadable_zip_is_one_file() -> None:
    data = bytearray(zipped(("a.txt", b"hello world " * 100)))
    data[40:60] = b"\xff" * 20  # inside the compressed stream
    (entry,) = unpack(bytes(data)).values()
    assert entry.refused is not None and entry.refused.startswith("corrupt entry")
    (whole,) = ZipUnpacker().entries("x.zip", b"PK\x03\x04 not really a zip")
    assert whole.data is not None


def test_a_broken_central_directory_is_one_unreadable_file() -> None:
    with pytest.raises(InvalidInputError):
        list(ZipUnpacker()._unzip(b"PK\x03\x04garbage", "", None, nested=False))  # type: ignore[arg-type]

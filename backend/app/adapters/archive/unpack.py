"""Safe unpacking of an upload (the `Unpacker` port): a zip, found by its content, is unpacked
with every entry checked; anything else is a one-file project.

What is refused, each as a set-aside entry with the reason, so the person sees it:
- a path that is absolute, has a drive letter, `..`, or an empty or hidden-control part;
- a symlink (the zip's Unix mode says so) and an encrypted entry;
- an entry over the per-file cap, one that expands more than `MAX_RATIO` times its compressed
  size (a zip bomb), and everything after the archive's total cap is reached;
- entries beyond `MAX_ENTRIES`, and a zip inside a zip inside the upload (one level is unpacked).

Sizes are checked from the archive's own header and then again while reading, so a header that
lies about a size is caught too. An office file (docx, xlsx, pptx) is a zip but not an archive:
it stays one file.
"""

import io
import stat
import zipfile
import zlib
from collections.abc import Iterator
from pathlib import PurePosixPath

from app.core.errors import InvalidInputError
from app.core.ingest.model import Entry

MAX_ENTRIES = 5000
MAX_FILE = 600 * 2**20  # the largest dataset model is 343 MB
MAX_TOTAL = 2 * 2**30
MAX_RATIO = 200  # a drawing PDF or IFC compresses about 3-10x; a bomb, 1000x and more
RATIO_FROM = 2**20  # small entries may compress well (a blank page): only larger ones count
CHUNK = 2**20
ZIP_MAGIC = (b"PK\x03\x04", b"PK\x05\x06")
OFFICE_MARK = "[Content_Types].xml"


def is_archive(data: bytes) -> bool:
    """A zip that is an archive of files, not an office document."""
    if not data.startswith(ZIP_MAGIC):
        return False
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            return OFFICE_MARK not in archive.namelist()
    except zipfile.BadZipFile:
        return False


def safe_path(name: str) -> str | None:
    """The entry's path, "/"-separated, or None when it could leave the project's folder."""
    path = name.replace("\\", "/")
    if path.startswith("/") or "\x00" in path:
        return None
    parts = PurePosixPath(path).parts
    if not parts or any(part in ("..", ".") or ":" in part for part in parts):
        return None
    if any(ord(char) < 32 for char in path):
        return None
    return "/".join(parts)


class ZipUnpacker:
    def __init__(
        self,
        *,
        max_entries: int = MAX_ENTRIES,
        max_file: int = MAX_FILE,
        max_total: int = MAX_TOTAL,
        max_ratio: float = MAX_RATIO,
    ) -> None:
        self._max_entries, self._max_file = max_entries, max_file
        self._max_total, self._max_ratio = max_total, max_ratio

    def entries(self, name: str, data: bytes) -> Iterator[Entry]:
        if not is_archive(data):
            single = PurePosixPath(name.replace("\\", "/")).name or "upload"
            if len(data) > self._max_file:
                yield Entry(path=single, size=len(data), refused=self._over_file())
            else:
                yield Entry(path=single, size=len(data), data=data)
            return
        budget = _Budget(self._max_entries, self._max_total)
        yield from self._unzip(data, "", budget, nested=False)

    def _unzip(self, data: bytes, prefix: str, budget: "_Budget", nested: bool) -> Iterator[Entry]:
        try:
            archive = zipfile.ZipFile(io.BytesIO(data))
        except zipfile.BadZipFile as error:
            raise InvalidInputError(f"not a readable zip: {error}") from error
        with archive:
            for info in archive.infolist():
                if info.is_dir():
                    continue
                path = safe_path(info.filename)
                shown = f"{prefix}{path or info.filename}"
                refused = self._refusal(info, path, budget)
                if refused is not None or path is None:
                    yield Entry(path=shown, size=info.file_size, refused=refused or "unsafe path")
                    continue
                try:
                    body = _read(archive, info, self._max_file)
                except (zipfile.BadZipFile, zlib.error, EOFError) as error:
                    yield Entry(path=shown, size=info.file_size, refused=f"corrupt entry: {error}")
                    continue
                if body is None:
                    yield Entry(path=shown, size=info.file_size, refused=self._over_file())
                    continue
                budget.total += len(body)
                if budget.total > budget.max_total:
                    yield Entry(path=shown, size=len(body), refused=budget.over())
                    continue
                if is_archive(body):
                    if nested:
                        why = "a zip inside a zip inside the upload: only one level is unpacked"
                        yield Entry(path=shown, size=len(body), refused=why)
                    else:
                        yield from self._unzip(body, f"{shown}/", budget, nested=True)
                    continue
                yield Entry(path=shown, size=len(body), data=body)

    def _refusal(self, info: zipfile.ZipInfo, path: str | None, budget: "_Budget") -> str | None:
        budget.count += 1
        if budget.count > budget.max_count:
            return f"the archive has more than {budget.max_count} files"
        if path is None:
            return "unsafe path: it could be written outside the project folder"
        if stat.S_ISLNK(info.external_attr >> 16):
            return "a symbolic link: links are not followed"
        if info.flag_bits & 0x1:
            return "an encrypted zip entry"
        if info.file_size > self._max_file:
            return self._over_file()
        if info.file_size >= RATIO_FROM and info.file_size > self._max_ratio * max(
            info.compress_size, 1
        ):
            ratio = info.file_size / max(info.compress_size, 1)
            return f"expands {ratio:.0f} times its compressed size: a zip bomb is refused"
        if budget.total + info.file_size > budget.max_total:
            return budget.over()
        return None

    def _over_file(self) -> str:
        return f"over the per-file cap of {self._max_file // 2**20} MB"


class _Budget:
    def __init__(self, max_count: int, max_total: int) -> None:
        self.max_count, self.max_total = max_count, max_total
        self.count = 0
        self.total = 0

    def over(self) -> str:
        return f"the archive is over its total cap of {self.max_total // 2**20} MB"


def _read(archive: zipfile.ZipFile, info: zipfile.ZipInfo, cap: int) -> bytes | None:
    """The entry's bytes, or None when it turns out bigger than `cap` while reading."""
    parts: list[bytes] = []
    size = 0
    with archive.open(info) as entry:
        while chunk := entry.read(CHUNK):
            size += len(chunk)
            if size > cap:
                return None
            parts.append(chunk)
    return b"".join(parts)

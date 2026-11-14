"""`FileTextReader`: a file's own text as a `text` source (decision 0012 sources v2, report 7.4),
for the ingest step and for the index, which reads it again from the stored file. A PDF's drawn
pages are left out: page 1 of a drawn PDF is its picture, its later drawn pages files of their own.
A text document (`pdf_text`, `text`) gives every other page with text; any other PDF only its text
pages of TEXT_PAGE_CHARS characters or more (app/core/evidence/file_sources.py)."""

from typing import cast, get_args

from app.adapters.evidence.file_text import pdf_pages, text_file
from app.core.evidence.chunks import KIND_WORDS
from app.core.evidence.file_sources import TextSource, text_source
from app.core.evidence.model import EvidenceSource
from app.core.ingest.model import TEXT_KINDS, ContentKind
from app.core.ingest.ports import ProjectStore


class FileTextReader:
    def text(self, path: str, kind: ContentKind, data: bytes) -> TextSource | None:
        if kind == "text":
            return text_source(path, KIND_WORDS["text_file"], text_file(data), whole=True)
        if kind not in ("pdf_text", "pdf_vector", "pdf_scan"):
            return None
        pages = [page for page in pdf_pages(data) if not page.drawn]
        whole = kind in TEXT_KINDS
        words = KIND_WORDS["text_document" if whole else "text_pages"]
        return text_source(path, words, pages, whole=whole)


class StoredTexts:
    """A `text` source's own text, read again from the project's stored upload (the index is
    derived from the status and the stored files, so it can be rebuilt at any time)."""

    def __init__(self, store: ProjectStore, reader: FileTextReader) -> None:
        self._store, self._reader = store, reader

    def __call__(self, project_id: str, source: EvidenceSource) -> TextSource | None:
        kind = source.file_kind
        if kind not in get_args(ContentKind):
            return None
        data = self._store.read_upload(project_id, source.path)
        return self._reader.text(source.path, cast(ContentKind, kind), data)

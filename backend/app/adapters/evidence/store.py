"""`SqliteEvidenceIndex`: a project's evidence index as `<projects root>/<id>/evidence.sqlite`.

Tables: `sources` (one row per described non-plan file: its content hash, verdict and the source
as JSON), `passages` (the chunker's passages, each with its file's subject and its vector of
`subject. text`) and `passages_fts` (FTS5 over subject and text with equal weight, external
content). `update` is incremental: a source whose content hash is unchanged
keeps its passages and vectors (only its verdict and JSON are refreshed); a changed one is cut and
embedded again; one no longer in the status is dropped. A change of embedder re-embeds everything.
Each update is one transaction, so a reader sees the index before or after it, never between.
"""

import json
import sqlite3
from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from pathlib import Path
from typing import Protocol

import numpy as np
from numpy.typing import NDArray

from app.adapters.paths import inside
from app.core.evidence.fusion import POOL, FileRanking
from app.core.evidence.model import EvidenceSource, Passage, sources
from app.core.evidence.search import first_per_file, passage_id, words
from app.core.ingest.model import ProjectStatus

FILE = "evidence.sqlite"
Chunker = Callable[[EvidenceSource], Sequence[Passage]]
SCHEMA = """
create table if not exists meta (key text primary key, value text not null);
create table if not exists sources (
    file_id text primary key, content text not null, verdict text, body text not null);
create table if not exists passages (
    rowid integer primary key, id text not null unique, file_id text not null,
    part text not null, n integer not null, subject text not null, text text not null,
    vector blob);
create index if not exists passages_file on passages (file_id);
create virtual table if not exists passages_fts using fts5(
    subject, text, content='passages', content_rowid='rowid',
    tokenize='unicode61 remove_diacritics 2');
"""


class Embedder(Protocol):
    """A local text embedder: one L2-normalised float32 row per text."""

    @property
    def name(self) -> str: ...  # model and revision: a new name re-embeds every passage

    @property
    def label(self) -> str: ...  # the model in a few words, for `method`

    def embed(self, texts: Sequence[str]) -> NDArray[np.float32]: ...  # passages

    def embed_query(self, text: str) -> NDArray[np.float32]: ...  # one row


def fts_query(text: str) -> str | None:
    """A user's words as an FTS5 query: each word quoted (no operators), any of them matching."""
    return " OR ".join(f'"{word}"' for word in words(text)) or None


class SqliteEvidenceIndex:
    def __init__(self, root: Path, chunker: Chunker, embedder: Embedder | None) -> None:
        self._root, self._chunker, self._embedder = root, chunker, embedder

    @property
    def embedder_label(self) -> str | None:
        return None if self._embedder is None else self._embedder.label

    def query_vector(self, query: str) -> NDArray[np.float32] | None:
        return None if self._embedder is None else self._embedder.embed_query(query)

    def path(self, project_id: str) -> Path:
        return inside(self._root, project_id) / FILE

    @contextmanager
    def _db(self, project_id: str) -> Iterator[sqlite3.Connection]:
        path = self.path(project_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(path)
        try:
            db.execute("pragma journal_mode=wal")
            db.executescript(SCHEMA)
            yield db
        finally:
            db.close()

    def update(self, status: ProjectStatus) -> None:
        current = {source.file_id: source for source in sources(status)}
        if not current and not self.path(status.id).is_file():
            return  # nothing described (triage off): no file is made
        embedder = "" if self._embedder is None else self._embedder.name
        with self._db(status.id) as db, db:
            row = db.execute("select value from meta where key = 'embedder'").fetchone()
            stored = dict(db.execute("select file_id, content from sources").fetchall())
            if row is None or row[0] != embedder:
                stored = {}  # another embedder: every source again
                for file_id in [r[0] for r in db.execute("select file_id from sources")]:
                    self._drop(db, file_id)
                db.execute("replace into meta values ('embedder', ?)", (embedder,))
            for file_id in stored.keys() - current.keys():
                self._drop(db, file_id)
            for file_id, source in current.items():
                body = source.model_dump_json()
                if stored.get(file_id) == source.content:
                    db.execute(
                        "update sources set verdict = ?, body = ? where file_id = ?",
                        (source.verdict, body, file_id),
                    )
                    continue
                self._drop(db, file_id)
                self._add(db, source)
                db.execute(
                    "insert into sources values (?, ?, ?, ?)",
                    (file_id, source.content, source.verdict, body),
                )

    def _drop(self, db: sqlite3.Connection, file_id: str) -> None:
        for rowid, subject, text in db.execute(
            "select rowid, subject, text from passages where file_id = ?", (file_id,)
        ).fetchall():
            db.execute(
                "insert into passages_fts (passages_fts, rowid, subject, text) "
                "values ('delete', ?, ?, ?)",
                (rowid, subject, text),
            )
        db.execute("delete from passages where file_id = ?", (file_id,))
        db.execute("delete from sources where file_id = ?", (file_id,))

    def _add(self, db: sqlite3.Connection, source: EvidenceSource) -> None:
        passages = [found for found in self._chunker(source) if found.text.strip()]
        subject = source.description.subject
        vectors: list[bytes | None] = [None] * len(passages)
        if self._embedder is not None and passages:
            found = self._embedder.embed([f"{subject}. {passage.text}" for passage in passages])
            vectors = [np.asarray(row, np.float32).tobytes() for row in found]
        for passage, vector in zip(passages, vectors, strict=True):
            cursor = db.execute(
                "insert into passages (id, file_id, part, n, subject, text, vector) "
                "values (?, ?, ?, ?, ?, ?, ?)",
                (passage_id(source.file_id, passage), source.file_id, passage.part, passage.n,
                 subject, passage.text, vector),
            )  # fmt: skip
            db.execute(
                "insert into passages_fts (rowid, subject, text) values (?, ?, ?)",
                (cursor.lastrowid, subject, passage.text),
            )

    # ---------------------------------------------------------------- reading

    def bm25(
        self, project_id: str, query: str, verdicts: frozenset[str | None], files: int = POOL
    ) -> FileRanking:
        """The first `files` files by FTS5 BM25 (a file ranks as its best passage), each with
        that passage, of sources with one of `verdicts`. The query's words are joined by OR."""
        matched = fts_query(query)
        if matched is None or not self.path(project_id).is_file():
            return []
        with self._db(project_id) as db:
            rows = db.execute(
                "select p.id, s.verdict from passages_fts f join passages p on p.rowid = f.rowid "
                "join sources s on s.file_id = p.file_id where passages_fts match ? "
                "order by bm25(passages_fts), p.id",
                (matched,),
            ).fetchall()
        return first_per_file((found for found, verdict in rows if verdict in verdicts), files)

    def dense(
        self,
        project_id: str,
        vector: NDArray[np.float32],
        verdicts: frozenset[str | None],
        files: int = POOL,
    ) -> FileRanking:
        """The first `files` files by cosine of their best passage to `vector` (both
        L2-normalised), each with that passage, of sources with one of `verdicts`."""
        if not self.path(project_id).is_file():
            return []
        with self._db(project_id) as db:
            rows = db.execute(
                "select p.id, p.vector, s.verdict from passages p "
                "join sources s on s.file_id = p.file_id where p.vector is not null"
            ).fetchall()
        kept = [(found, blob) for found, blob, verdict in rows if verdict in verdicts]
        if not kept:
            return []
        matrix = np.stack([np.frombuffer(blob, np.float32) for _, blob in kept])
        scores = matrix @ np.asarray(vector, np.float32)
        order = np.argsort(-scores, kind="stable")
        return first_per_file((kept[int(i)][0] for i in order), files)

    def passage(self, project_id: str, passage: str) -> tuple[Passage, EvidenceSource] | None:
        """A passage by id with its source; None if the project's index has no such passage."""
        if not self.path(project_id).is_file():
            return None
        with self._db(project_id) as db:
            row = db.execute(
                "select p.part, p.n, p.text, s.body from passages p "
                "join sources s on s.file_id = p.file_id where p.id = ?",
                (passage,),
            ).fetchone()
        if row is None:
            return None
        part, n, text, body = row
        return Passage(part=part, n=n, text=text), EvidenceSource.model_validate(json.loads(body))

    def indexed(self, project_id: str) -> list[EvidenceSource]:
        """The sources in the project's index, in file order."""
        if not self.path(project_id).is_file():
            return []
        with self._db(project_id) as db:
            rows = db.execute("select body from sources").fetchall()
        found = [EvidenceSource.model_validate(json.loads(body)) for (body,) in rows]
        return sorted(found, key=lambda source: int(source.file_id[1:]))

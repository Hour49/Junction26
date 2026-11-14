"""`SqliteEvidenceIndex`: a project's evidence index as `<projects root>/<id>/evidence.sqlite`.

Tables: `sources` (one row per described non-plan file: its content hash, verdict and the source
as JSON), `passages` (the chunker's passages, each with its file's subject and its vector of
`subject. text`) and `passages_fts` (FTS5 over subject and text with equal weight, external
content).

Reads go through an `EvidenceReader`: one connection for everything one request reads, no schema,
no write. `sync` keeps the index in step with the project's status: it compares the stored rows
read-only, and only when something differs takes the write lock (`begin immediate`), compares
again and writes the rows that differ. A source whose content hash is unchanged keeps its
passages and vectors (its verdict and JSON are refreshed when they changed); a changed one is cut
and embedded again; one no longer in the status is dropped; a change of embedder re-embeds
everything. Each write is one transaction, so a reader sees the index before or after it, never
between; an index already in step is never written, so opening it never waits for a writer.
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
# (embedder name, {file id: (content hash, verdict, source JSON)})
Stored = tuple[str | None, dict[str, tuple[str, str | None, str]]]
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


class EvidenceReader:
    """One project's index read through one connection, opened on the first read that finds the
    index file (and kept until `close`); with no file every read is empty. It never writes."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._db: sqlite3.Connection | None = None

    def _connection(self) -> sqlite3.Connection | None:
        """The connection, once the file holds an index: a file without the schema (another sync
        between creating it and committing, or one that died there) reads as empty."""
        if self._db is None and self._path.is_file():
            db = sqlite3.connect(self._path)
            made = db.execute("select 1 from sqlite_master where name = 'meta'").fetchone()
            if made is None:
                db.close()
                return None
            self._db = db
        return self._db

    def close(self) -> None:
        if self._db is not None:
            self._db.close()
            self._db = None

    def stored(self) -> Stored:
        db = self._connection()
        if db is None:
            return None, {}
        row = db.execute("select value from meta where key = 'embedder'").fetchone()
        rows = db.execute("select file_id, content, verdict, body from sources").fetchall()
        return (None if row is None else row[0]), {r[0]: (r[1], r[2], r[3]) for r in rows}

    def indexed(self) -> list[EvidenceSource]:
        """The sources in the index, in file order."""
        db = self._connection()
        if db is None:
            return []
        rows = db.execute("select body from sources").fetchall()
        found = [EvidenceSource.model_validate(json.loads(body)) for (body,) in rows]
        return sorted(found, key=lambda source: int(source.file_id[1:]))

    def bm25(self, query: str, verdicts: frozenset[str | None], files: int = POOL) -> FileRanking:
        """The first `files` files by FTS5 BM25 (a file ranks as its best passage), each with
        that passage, of sources with one of `verdicts`. The query's words are joined by OR."""
        matched = fts_query(query)
        db = self._connection()
        if matched is None or db is None:
            return []
        rows = db.execute(
            "select p.id, s.verdict from passages_fts f join passages p on p.rowid = f.rowid "
            "join sources s on s.file_id = p.file_id where passages_fts match ? "
            "order by bm25(passages_fts), p.id",
            (matched,),
        ).fetchall()
        return first_per_file((found for found, verdict in rows if verdict in verdicts), files)

    def dense(
        self, vector: NDArray[np.float32], verdicts: frozenset[str | None], files: int = POOL
    ) -> FileRanking:
        """The first `files` files by cosine of their best passage to `vector` (both
        L2-normalised), each with that passage, of sources with one of `verdicts`."""
        db = self._connection()
        if db is None:
            return []
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

    def passage(self, passage: str) -> tuple[Passage, EvidenceSource] | None:
        """A passage by id with its source; None if the index has no such passage."""
        db = self._connection()
        if db is None:
            return None
        row = db.execute(
            "select p.part, p.n, p.text, s.body from passages p "
            "join sources s on s.file_id = p.file_id where p.id = ?",
            (passage,),
        ).fetchone()
        if row is None:
            return None
        part, n, text, body = row
        return Passage(part=part, n=n, text=text), EvidenceSource.model_validate(json.loads(body))


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
    def reader(self, project_id: str) -> Iterator[EvidenceReader]:
        found = EvidenceReader(self.path(project_id))
        try:
            yield found
        finally:
            found.close()

    def update(self, status: ProjectStatus) -> None:
        """The index in step with `status` (ingest calls it after judging and overrules)."""
        with self.reader(status.id) as found:
            self.sync(status, found)

    def sync(self, status: ProjectStatus, reader: EvidenceReader) -> None:
        """The index in step with `status`, compared through `reader`: no write, and no write
        lock, when it already is."""
        current = {source.file_id: source for source in sources(status)}
        if not current and not self.path(status.id).is_file():
            return  # nothing described (triage off): no file is made
        if not self._differs(reader.stored(), current):
            return
        path = self.path(status.id)
        path.parent.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(path, isolation_level=None)  # transactions spelt out below
        try:
            db.execute("pragma journal_mode=wal")  # not allowed inside a transaction
            db.execute("begin immediate")
            try:
                for statement in SCHEMA.split(";"):  # in the transaction, with the rows
                    if statement.strip():
                        db.execute(statement)
                self._write(db, current)
                db.execute("commit")
            except BaseException:
                db.execute("rollback")
                raise
        finally:
            db.close()

    def _embedder_name(self) -> str:
        return "" if self._embedder is None else self._embedder.name

    def _differs(self, stored: Stored, current: dict[str, EvidenceSource]) -> bool:
        embedder, rows = stored
        if embedder != self._embedder_name() or rows.keys() != current.keys():
            return True
        return any(
            rows[file_id] != (source.content, source.verdict, source.model_dump_json())
            for file_id, source in current.items()
        )

    def _write(self, db: sqlite3.Connection, current: dict[str, EvidenceSource]) -> None:
        """Write what differs, compared again under the write lock (another writer may have
        brought the index in step meanwhile)."""
        embedder = self._embedder_name()
        row = db.execute("select value from meta where key = 'embedder'").fetchone()
        rows = db.execute("select file_id, content, verdict, body from sources").fetchall()
        stored = {file_id: (content, verdict, body) for file_id, content, verdict, body in rows}
        if row is None or row[0] != embedder:
            for file_id in list(stored):
                self._drop(db, file_id)
            stored = {}  # another embedder: every source again
            db.execute("replace into meta values ('embedder', ?)", (embedder,))
        for file_id in stored.keys() - current.keys():
            self._drop(db, file_id)
        for file_id, source in current.items():
            body = source.model_dump_json()
            before = stored.get(file_id)
            if before == (source.content, source.verdict, body):
                continue
            if before is not None and before[0] == source.content:
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

    # ------------------------------------------- reads of one call each (scripts and tests)

    def bm25(
        self, project_id: str, query: str, verdicts: frozenset[str | None], files: int = POOL
    ) -> FileRanking:
        with self.reader(project_id) as found:
            return found.bm25(query, verdicts, files)

    def dense(
        self,
        project_id: str,
        vector: NDArray[np.float32],
        verdicts: frozenset[str | None],
        files: int = POOL,
    ) -> FileRanking:
        with self.reader(project_id) as found:
            return found.dense(vector, verdicts, files)

    def passage(self, project_id: str, passage: str) -> tuple[Passage, EvidenceSource] | None:
        with self.reader(project_id) as found:
            return found.passage(passage)

    def indexed(self, project_id: str) -> list[EvidenceSource]:
        with self.reader(project_id) as found:
            return found.indexed()

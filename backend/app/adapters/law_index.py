"""The building-law knowledge base (LAWS_DIR, decision 0011): `<pack>/<law id>.json`, each
validated as `Law`. A file that does not validate, whose id is not its file name or whose pack is
not its folder, or that repeats a clause id, stops the start, naming the file. The clauses go into
an in-memory SQLite FTS5 index (stdlib), ranked by BM25 with the English summary and keywords
above the statute text.

Researchers check their files with:

    cd backend && uv run python -m app.adapters.law_index validate app/laws
"""

import sqlite3
import sys
import threading
from pathlib import Path

from pydantic import ValidationError

from app.core.errors import InvalidInputError, NotFoundError, UnknownPackError
from app.core.laws.model import (
    PACKS,
    ClauseView,
    Law,
    LawClause,
    Pack,
    SearchHit,
    TocEntry,
    Topic,
    clause_view,
    toc_entry,
)
from app.core.laws.search import match_query

# Columns of the FTS5 table and their BM25 weights: what was written for search counts most
COLUMNS = {"summary_en": 4.0, "keywords": 4.0, "heading": 2.0, "text_en": 1.0, "text": 1.0,
           "law": 1.0}  # fmt: skip


def load_laws(folder: Path) -> tuple[Law, ...]:
    """Every law in `folder`'s pack folders, by pack and id. A missing folder has none."""
    laws: list[Law] = []
    owner: dict[str, str] = {}  # clause id -> the file that has it
    for path in sorted(folder.glob("*/*.json")) if folder.is_dir() else ():
        name = f"{path.parent.name}/{path.name}"
        try:
            law = Law.model_validate_json(path.read_bytes())
        except ValidationError as error:
            raise InvalidInputError(f"law file {name}: {error}") from error
        if law.id != path.stem:
            raise InvalidInputError(f"law file {name}: its id is {law.id!r}")
        if law.pack != path.parent.name:
            raise InvalidInputError(f"law file {name}: its pack is {law.pack!r}")
        for clause in law.clauses:
            if clause.id in owner:
                raise InvalidInputError(
                    f"law file {name}: clause {clause.id} twice (also in {owner[clause.id]})"
                )
            owner[clause.id] = name
        laws.append(law)
    return tuple(laws)


class SqliteLawIndex:
    """The `LawIndex` port over the loaded laws, built once at start; read-only after."""

    def __init__(self, laws: tuple[Law, ...]) -> None:
        self._laws = laws
        self._clauses: dict[str, tuple[Law, LawClause]] = {}
        self._lock = threading.Lock()  # one connection, used from FastAPI's thread pool
        self._db = sqlite3.connect(":memory:", check_same_thread=False)
        self._db.execute(
            f"CREATE VIRTUAL TABLE fts USING fts5({', '.join(COLUMNS)}, "
            "tokenize='unicode61 remove_diacritics 2', prefix='3 4 5')"
        )
        self._db.execute("CREATE TABLE clause (row INTEGER PRIMARY KEY, id TEXT, pack TEXT)")
        self._db.execute("CREATE TABLE topic (row INTEGER, topic TEXT)")
        for law in laws:
            for clause in law.clauses:
                self._clauses[clause.id] = (law, clause)
                row = len(self._clauses)
                self._db.execute(
                    "INSERT INTO fts (rowid, summary_en, keywords, heading, text_en, text, law) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        row,
                        clause.summary_en,
                        " ; ".join(clause.keywords),
                        " ; ".join(filter(None, (clause.heading, clause.heading_en))),
                        clause.text_en or "",
                        clause.text,
                        f"{law.number} {law.title} {law.title_en}",
                    ),
                )
                self._db.execute("INSERT INTO clause VALUES (?, ?, ?)", (row, clause.id, law.pack))
                self._db.executemany(
                    "INSERT INTO topic VALUES (?, ?)", [(row, topic) for topic in clause.topics]
                )

    def packs(self) -> tuple[Pack, ...]:
        return PACKS

    def search(
        self, pack: str, query: str, topic: Topic | None = None, limit: int = 5
    ) -> list[SearchHit]:
        _known(pack)
        match = match_query(query)
        if match is None:
            return []
        weights = ", ".join(str(weight) for weight in COLUMNS.values())
        sql = (
            f"SELECT clause.id, -bm25(fts, {weights}) AS score FROM fts "
            "JOIN clause ON clause.row = fts.rowid WHERE fts MATCH ? AND clause.pack = ? "
            + ("AND clause.row IN (SELECT row FROM topic WHERE topic = ?) " if topic else "")
            + "ORDER BY score DESC, clause.id LIMIT ?"
        )
        params = (match, pack, *([topic] if topic else []), limit)
        with self._lock:
            rows = self._db.execute(sql, params).fetchall()
        hits: list[SearchHit] = []
        for clause_id, score in rows:
            law, clause = self._clauses[clause_id]
            hits.append(
                SearchHit(
                    id=clause.id,
                    law_id=law.id,
                    ref=clause.ref,
                    title_en=law.title_en,
                    summary_en=clause.summary_en,
                    url=law.url,
                    score=round(score, 3),
                )
            )
        return hits

    def clause(self, clause_id: str) -> ClauseView:
        if clause_id not in self._clauses:
            raise NotFoundError(f"no law clause {clause_id!r}")
        return clause_view(*self._clauses[clause_id])

    def toc(self, pack: str) -> list[TocEntry]:
        _known(pack)
        return [toc_entry(law) for law in self._laws if law.pack == pack]


def _known(pack: str) -> None:
    if pack not in PACKS:
        raise UnknownPackError(f"no law pack {pack!r}")


def main(argv: list[str]) -> int:
    if len(argv) != 2 or argv[0] != "validate":
        print("usage: python -m app.adapters.law_index validate <laws folder>", file=sys.stderr)
        return 2
    try:
        laws = load_laws(Path(argv[1]))
        SqliteLawIndex(laws)
    except InvalidInputError as error:
        print(error, file=sys.stderr)
        return 1
    for pack in PACKS:
        mine = [law for law in laws if law.pack == pack]
        print(f"{pack}: {len(mine)} laws, {sum(len(law.clauses) for law in mine)} clauses")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

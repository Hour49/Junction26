"""The pure part of law search (decision 0014): user text to a safe FTS5 query, and the port the
API and the model's tools read the knowledge base through."""

import re
from typing import Protocol

from app.core.laws.model import ClauseView, Pack, SearchHit, TocEntry, Topic

WORD = re.compile(r"\w+")


def match_query(text: str, every: bool = False) -> str | None:
    """Each word of `text` as a quoted prefix term, OR-ed (AND-ed when `every`): FTS5 operators,
    quotes and stars in the text are plain words then, so it can neither break nor steer the
    MATCH. None: no word."""
    terms = [f'"{word}"*' for word in WORD.findall(text)]
    return (" AND " if every else " OR ").join(terms) or None


class LawIndex(Protocol):
    def packs(self) -> tuple[Pack, ...]: ...

    def search(
        self, pack: str, query: str, topic: Topic | None = None, limit: int = 5
    ) -> list[SearchHit]: ...

    def clause(self, clause_id: str) -> ClauseView: ...

    def toc(self, pack: str) -> list[TocEntry]: ...

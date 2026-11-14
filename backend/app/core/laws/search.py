"""The pure part of law search (decision 0014): user text to a safe FTS5 query, and the port the
API and the model's tools read the knowledge base through."""

import re
from typing import Protocol

from app.core.laws.model import ClauseView, Pack, SearchHit, TocEntry, Topic

WORD = re.compile(r"\w+")
# Words a question is made of but no clause is about ("when do I need a building permit", "what
# does Zürich say about daylight"), and the packs' place names, which every clause of a pack shares
# and which match only prose ("cantonal"). Other 2-letter words stay: "WC", "m2"
STOPWORDS = frozenset(
    {"the", "for", "when", "what", "how", "need", "an", "do", "is", "to", "of", "in", "on", "my",
     "we", "it", "at", "be", "or", "as", "by", "if", "so", "no", "me", "us", "am", "ja", "se",
     "ei", "zu", "im", "es", "does", "say", "says", "about", "tell", "rule", "rules", "law",
     "laws", "zürich", "zurich", "zuerich", "switzerland", "swiss", "canton", "kanton",
     "finland", "finnish", "suomi"}
)  # fmt: skip
MAX_TERMS = 20  # a long query stays one cheap MATCH


def match_query(text: str, every: bool = False) -> str | None:
    """Each word of 2+ letters of `text`, minus stopwords and repeats, as a quoted term, OR-ed
    (AND-ed when `every`), at most MAX_TERMS: FTS5 operators, quotes and stars in the text are
    plain words then, so it can neither break nor steer the MATCH. Words of 3+ letters are prefix
    terms ("Fluchtweg" finds "Fluchtwege"); a 2-letter one is exact ("wc", "m2"; no prefix index
    for 2 letters); 1-letter words would match nearly every clause. None: no word left."""
    words = (word for word in WORD.findall(text.lower()) if len(word) > 1)
    kept = [word for word in dict.fromkeys(words) if word not in STOPWORDS][:MAX_TERMS]
    terms = [f'"{word}"*' if len(word) > 2 else f'"{word}"' for word in kept]
    return (" AND " if every else " OR ").join(terms) or None


def is_old_wording(clause_id: str) -> bool:
    """A clause of a law's Anhang: the wording before an amendment, which applies only where a
    commune has not adapted to it yet, so search ranks it after every current clause."""
    return "-anhang-" in clause_id


class LawIndex(Protocol):
    def packs(self) -> tuple[Pack, ...]: ...

    def search(
        self, pack: str, query: str, topic: Topic | None = None, limit: int = 5
    ) -> list[SearchHit]: ...

    def clause(self, clause_id: str) -> ClauseView: ...

    def toc(self, pack: str) -> list[TocEntry]: ...

"""`ProjectEvidence`: one project's evidence index, as the tools and REST routes use it
(decision 0012, contract v1). Opening it brings the store in line with the
project's status (an incremental update), so a project ingested before the index existed is
indexed on its first query."""

from collections import Counter
from collections.abc import Callable

from app.adapters.evidence.store import SqliteEvidenceIndex
from app.core.evidence.fusion import FileRanking, fused
from app.core.evidence.model import (
    DescriptionView,
    EvidenceDetail,
    EvidenceHit,
    EvidenceSearch,
    HitWhy,
)
from app.core.evidence.search import parsed, passage_id, snippet, terms
from app.core.ingest.model import ProjectStatus

KEPT: frozenset[str | None] = frozenset({"related", "unsure", None})
EVERY: frozenset[str | None] = KEPT | {"unrelated"}
NOTHING = "No file of this project has a description: file triage was off when it was ingested."
LISTED = 30  # evidence_prompt lists each file up to this many
CreditOf = Callable[[int, str], str | None]  # (size, sha256) -> the licence credit


class ProjectEvidence:
    def __init__(
        self, store: SqliteEvidenceIndex, status: ProjectStatus, credit_of: CreditOf
    ) -> None:
        self._store, self._id = store, status.id
        self._files = {file.id: file for file in status.files}
        self._credit_of = credit_of
        store.update(status)
        self._sources = {source.file_id: source for source in store.indexed(status.id)}

    @property
    def method(self) -> str:
        name = self._store.embedder_name
        if name is None:
            return "BM25 (no embedder model on this machine)"
        return f"hybrid: BM25 + {name}, reciprocal rank fusion"

    def _credit(self, file_id: str) -> str | None:
        file = self._files.get(file_id)
        if file is None or file.sha256 is None:
            return None
        return self._credit_of(file.size, file.sha256)

    def search(self, query: str, k: int = 5, include_unrelated: bool = False) -> EvidenceSearch:
        verdicts = EVERY if include_unrelated else KEPT
        left_out = 0 if include_unrelated else sum(
            source.verdict == "unrelated" for source in self._sources.values()
        )  # fmt: skip
        bm25 = self._store.bm25(self._id, query, verdicts)
        rankings = [bm25]
        vector = self._store.query_vector(query)
        dense = None if vector is None else self._store.dense(self._id, vector, verdicts)
        if dense is not None:
            rankings.append(dense)
        hits: list[EvidenceHit] = []
        for file_id, best, score in fused(rankings)[:k]:
            found = self._store.passage(self._id, best)
            if found is None:
                continue
            passage, source = found
            matched = terms(query, passage.text)
            hits.append(
                EvidenceHit(
                    id=passage_id(file_id, passage),
                    file_id=file_id,
                    file=source.path,
                    page=1,
                    part=passage.part,
                    kind=source.kind,
                    subject=source.description.subject,
                    snippet=snippet(passage.text, matched),
                    language=source.description.language,
                    verdict=source.verdict,
                    credit=self._credit(file_id),
                    score=round(score, 6),
                    why=HitWhy(
                        terms=matched,
                        bm25_rank=_rank(bm25, file_id),
                        dense_rank=None if dense is None else _rank(dense, file_id),
                    ),
                )
            )
        return EvidenceSearch(
            query=query,
            method=self.method,
            indexed_files=len(self._sources),
            unrelated_left_out=left_out,
            note=None if self._sources else NOTHING,
            hits=tuple(hits),
        )

    def get(self, found: str) -> EvidenceDetail | None:
        """A passage by its id, or a file by its id (its summary); None if not in the index."""
        asked = parsed(found)
        if asked is None:
            return None
        file_id, part, n = asked
        source = self._sources.get(file_id)
        if source is None:
            return None
        wanted = f"{file_id}-summary" if part == "summary" else f"{file_id}-{part}-{n}"
        stored = self._store.passage(self._id, wanted)
        if stored is None:
            return None
        passage, _ = stored
        described = source.description
        return EvidenceDetail(
            id=wanted,
            file_id=file_id,
            file=source.path,
            page=1,
            part=passage.part,
            text=passage.text,
            kind=source.kind,
            verdict=source.verdict,
            credit=self._credit(file_id),
            description=DescriptionView(
                subject=described.subject,
                text=described.text,
                detail=described.detail,
                visible_text=described.visible_text,
                text_seen=described.text_seen,
                language=described.language,
                what_it_is=described.what_it_is,
                shows_building=described.shows_building,
                model=described.model,
            ),
            register=source.sheet_register,
            relevance=source.relevance,
        )

    def prompt(self) -> str:
        """What the index holds, for the agent's system prompt."""
        sources = list(self._sources.values())
        if not sources:
            return f"Project evidence: none. {NOTHING} Do not call search_evidence."
        kinds = Counter(source.kind for source in sources)
        languages = sorted({s.description.language for s in sources if s.description.language})
        unrelated = sum(source.verdict == "unrelated" for source in sources)
        said = ", ".join(f"{count} {kind}" for kind, count in kinds.most_common())
        lines = [
            f"Project evidence: {len(sources)} described files that are not floor plans ({said})"
            + (f"; printed text in {', '.join(languages)}" if languages else "")
            + (f"; {unrelated} judged unrelated, searched only on request" if unrelated else "")
            + ".",
            "Call search_evidence for what a photo, elevation, section, site plan, map or text page"
            " shows or says, and get_evidence before stating a fact from one; cite the file."
            " The descriptions were written by a model and not checked by a person: say"
            ' "the description says". Floor plan facts (counts, areas, rooms) are not in it.',
        ]
        if len(sources) <= LISTED:
            lines += [f"{s.file_id} {s.kind}: {s.description.subject}" for s in sources]
        return "\n".join(lines)


def _rank(ranking: FileRanking, file_id: str) -> int | None:
    """The file's rank in a retriever's pool; None when the pool doesn't hold it."""
    return next((rank for rank, (found, _) in enumerate(ranking, 1) if found == file_id), None)

"""`ProjectEvidence`: one project's evidence index, as the tools and REST routes use it
(decision 0012, contract v1.1). Its first search, get or prompt brings the store in line with the
project's status (an incremental update that writes nothing when the index is in step), so a
project ingested before the index existed is indexed on its first query. That first use, not the
constructor, is where opening can fail, so the tool dispatcher's catch-all covers it. Each call
reads through one SQLite connection."""

from collections import Counter
from collections.abc import Callable

from app.adapters.evidence.store import EvidenceReader, SqliteEvidenceIndex
from app.core.evidence.fusion import FileRanking, fused
from app.core.evidence.model import (
    DescriptionView,
    EvidenceDetail,
    EvidenceHit,
    EvidenceSearch,
    EvidenceSource,
    HitWhy,
)
from app.core.evidence.search import parsed, passage_id, snippet, terms
from app.core.ingest.model import ProjectStatus

KEPT: frozenset[str | None] = frozenset({"related", "unsure", None})
EVERY: frozenset[str | None] = KEPT | {"unrelated"}
NOTHING = "No file of this project has a description: file triage was off when it was ingested."
LISTED = 30  # evidence_prompt lists each file up to this many
PROMPT_CHARS = 6000  # the longest evidence_prompt, as the law tools' prompt
CreditOf = Callable[[int, str], str | None]  # (size, sha256) -> the licence credit


class ProjectEvidence:
    def __init__(
        self, store: SqliteEvidenceIndex, status: ProjectStatus, credit_of: CreditOf
    ) -> None:
        self._store, self._status, self._id = store, status, status.id
        self._files = {file.id: file for file in status.files}
        self._credit_of = credit_of
        self._sources: dict[str, EvidenceSource] | None = None

    def _opened(self, reader: EvidenceReader) -> dict[str, EvidenceSource]:
        """The indexed sources, the index first brought in step (once per instance)."""
        if self._sources is None:
            self._store.sync(self._status, reader)
            self._sources = {source.file_id: source for source in reader.indexed()}
        return self._sources

    @property
    def project_id(self) -> str:
        return self._id

    @property
    def method(self) -> str:
        label = self._store.embedder_label
        if label is None:
            return "BM25 (no embedder model on this machine)"
        return f"hybrid: BM25 + {label}, reciprocal rank fusion"

    def _credit(self, file_id: str) -> str | None:
        file = self._files.get(file_id)
        if file is None or file.sha256 is None:
            return None
        return self._credit_of(file.size, file.sha256)

    def search(self, query: str, k: int = 5, include_unrelated: bool = False) -> EvidenceSearch:
        with self._store.reader(self._id) as reader:
            sources = self._opened(reader)
            verdicts = EVERY if include_unrelated else KEPT
            left_out = 0 if include_unrelated else sum(
                source.verdict == "unrelated" for source in sources.values()
            )  # fmt: skip
            hits: list[EvidenceHit] = []
            if sources:  # nothing indexed: nothing to rank, and no query to embed
                hits = self._hits(reader, query, k, verdicts)
        return EvidenceSearch(
            query=query,
            method=self.method,
            indexed_files=len(sources),
            unrelated_left_out=left_out,
            note=None if sources else NOTHING,
            hits=tuple(hits),
        )

    def _hits(
        self, reader: EvidenceReader, query: str, k: int, verdicts: frozenset[str | None]
    ) -> list[EvidenceHit]:
        bm25 = reader.bm25(query, verdicts)
        rankings = [bm25]
        vector = self._store.query_vector(query)
        dense = None if vector is None else reader.dense(vector, verdicts)
        if dense is not None:
            rankings.append(dense)
        hits: list[EvidenceHit] = []
        for file_id, best, score in fused(rankings)[:k]:
            found = reader.passage(best)
            if found is None:
                continue
            passage, source = found
            matched = terms(query, passage.text)
            hits.append(
                EvidenceHit(
                    id=passage_id(file_id, passage),
                    file_id=file_id,
                    file=source.path,
                    page=source.page,
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
        return hits

    def get(self, found: str) -> EvidenceDetail | None:
        """A passage by its id, or a file by its id (its summary); None if not in the index."""
        asked = parsed(found)
        if asked is None:
            return None
        file_id, part, n = asked
        wanted = f"{file_id}-summary" if part == "summary" else f"{file_id}-{part}-{n}"
        with self._store.reader(self._id) as reader:
            source = self._opened(reader).get(file_id)
            stored = None if source is None else reader.passage(wanted)
        if source is None or stored is None:
            return None
        passage, _ = stored
        described = source.description
        return EvidenceDetail(
            id=wanted,
            file_id=file_id,
            file=source.path,
            page=source.page,
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
        with self._store.reader(self._id) as reader:
            sources = list(self._opened(reader).values())
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
        text = "\n".join(lines)
        return text if len(text) <= PROMPT_CHARS else text[: PROMPT_CHARS - 3] + "..."


def _rank(ranking: FileRanking, file_id: str) -> int | None:
    """The file's rank in a retriever's pool; None when the pool doesn't hold it."""
    return next((rank for rank, (found, _) in enumerate(ranking, 1) if found == file_id), None)

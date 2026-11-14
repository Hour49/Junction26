"""The building-law knowledge base (decision 0014, docs/API.md "Building law"): each pack's table
of contents, search in one pack, and one clause with its law. The same index the model's tools
read (app/adapters/law_tools.py)."""

from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import LawsDep
from app.api.views import View
from app.core.laws.model import ClauseView, SearchHit, TocEntry, Topic

router = APIRouter(prefix="/api/laws")


class LawPack(View):
    id: str  # "fi", "ch-zh": the ids of the rule packs (GET /api/info rule_packs)
    laws: list[TocEntry]


class LawPacks(View):
    packs: list[LawPack]


class LawSearch(View):
    pack: str
    query: str
    hits: list[SearchHit]  # best first


@router.get("")
def law_packs(index: LawsDep) -> LawPacks:
    return LawPacks(packs=[LawPack(id=pack, laws=index.toc(pack)) for pack in index.packs()])


@router.get("/clauses/{clause_id}")
def law_clause(clause_id: str, index: LawsDep) -> ClauseView:
    return index.clause(clause_id)


@router.get("/{pack}/search")
def law_search(
    pack: str,
    index: LawsDep,
    q: Annotated[str, Query(min_length=1, max_length=500, description="words to search for")],
    topic: Annotated[Topic | None, Query(description="only clauses of this topic")] = None,
    limit: Annotated[int, Query(ge=1, le=20)] = 5,
) -> LawSearch:
    return LawSearch(pack=pack, query=q, hits=index.search(pack, q, topic, limit))

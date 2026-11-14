"""GET /api/projects/{project_id}/evidence/search and /evidence/{evidence_id}: the project's
evidence index (decision 0012), the files that are not floor plans, searched by what triage's
describer says they show and by the words printed on them. The same JSON as the chat agent's
`search_evidence` and `get_evidence` tools (app/adapters/evidence_tools.py). It works in any
project state: it answers from what is described so far."""

from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import EvidenceDep, ProjectId
from app.core.errors import NotFoundError
from app.core.evidence.model import EvidenceDetail, EvidenceSearch

router = APIRouter(prefix="/api/projects")

QUERY_CHARS = 500


@router.get("/{project_id}/evidence/search", response_model=EvidenceSearch)
def search_evidence(
    project_id: ProjectId,
    evidence: EvidenceDep,
    q: Annotated[str, Query(min_length=1, max_length=QUERY_CHARS, pattern=r"\S")],
    k: Annotated[int, Query(ge=1, le=20)] = 5,
    include_unrelated: bool = False,
) -> EvidenceSearch:
    """Up to `k` files, best first, one hit each with its best-matching passage. Files judged
    unrelated are searched only with `include_unrelated`."""
    return evidence.evidence_index(project_id).search(q.strip(), k, include_unrelated)


@router.get("/{project_id}/evidence/{evidence_id}", response_model=EvidenceDetail)
def get_evidence(project_id: ProjectId, evidence_id: str, evidence: EvidenceDep) -> EvidenceDetail:
    """One passage (`f7-detail-2`) or a file as a whole (`f7`, its summary), with the file's
    description, register and relevance."""
    found = evidence.evidence_index(project_id).get(evidence_id)
    if found is None:
        raise NotFoundError(f"no evidence {evidence_id!r} in project {project_id}")
    return found

"""What the evidence index needs from outside, as Protocols (app/adapters/evidence has them)."""

from typing import Protocol

from app.core.ingest.model import ProjectStatus


class EvidenceIndex(Protocol):
    """A project's evidence index, kept in step with its saved status: `update` re-indexes the
    sources whose content changed, drops the ones gone and refreshes every verdict. Ingest calls it
    after a project is judged and after a person's overrule; it must not fail ingest."""

    def update(self, status: ProjectStatus) -> None: ...

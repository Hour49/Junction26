"""What review needs from outside, as Protocols."""

from collections.abc import Callable
from typing import Protocol

from app.core.review.model import (
    Resolved,
    ResolveRequest,
    ResolverUnavailable,
    ReviewState,
)


class ReviewStore(Protocol):
    """The review edits of each drawing in each project, by project id and drawing id: a drawing
    is shared by content, its review is not (R1b-4-1). `project_id` None: the drawing's edits
    outside any project, which no project sees. An unknown pair has no edits."""

    def get(self, project_id: str | None, drawing_id: str) -> ReviewState: ...

    def update(
        self,
        project_id: str | None,
        drawing_id: str,
        change: Callable[[ReviewState], ReviewState],
    ) -> ReviewState:
        """Applies `change` to the stored state and keeps the result, with no other update of
        the same drawing in between. Returns the new state."""
        ...


class Resolver(Protocol):
    """RESOLVER: a model that looks at the places in dispute and picks a value, or says it can't
    tell. It pays for its own calls (the spend guard) and caches each reply by the request, so
    the same request twice costs one call. `page(n)`: page n (1-based) of the drawing as a PNG,
    the image the boxes of the request are fractions of; called only on a cache miss."""

    def resolve(
        self, request: ResolveRequest, page: Callable[[int], bytes]
    ) -> Resolved | ResolverUnavailable: ...

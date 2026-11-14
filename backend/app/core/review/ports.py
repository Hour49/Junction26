"""What review needs from outside, as Protocols."""

from collections.abc import Callable
from typing import Protocol

from app.core.review.model import ReviewState


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

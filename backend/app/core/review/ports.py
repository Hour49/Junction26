"""What review needs from outside, as Protocols."""

from collections.abc import Callable
from typing import Protocol

from app.core.review.model import ReviewState


class ReviewStore(Protocol):
    """The review edits of each drawing, by drawing id. An unknown drawing has no edits."""

    def get(self, drawing_id: str) -> ReviewState: ...

    def update(self, drawing_id: str, change: Callable[[ReviewState], ReviewState]) -> ReviewState:
        """Applies `change` to the stored state and keeps the result, with no other update of
        the same drawing in between. Returns the new state."""
        ...

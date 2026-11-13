"""The base of every core data type."""

from pydantic import BaseModel, ConfigDict


class Frozen(BaseModel):
    """Immutable, and an unknown field is refused, so a typo fails instead of being dropped."""

    model_config = ConfigDict(frozen=True, extra="forbid")

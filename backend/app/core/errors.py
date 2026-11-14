"""Domain errors. Core raises them; app/main.py maps each one to an HTTP status."""


class DomainError(Exception):
    """An error the product expects (missing thing, bad input). Any other exception is a bug."""


class NotFoundError(DomainError):
    """The thing asked for doesn't exist."""


class UnknownPackError(NotFoundError):
    """A building-code rule pack that doesn't exist (decision 0009): its own code, so a screen
    resets its pack choice instead of saying the project is gone."""


class InvalidInputError(DomainError):
    """Input the product refuses: a path that leaves its folder, a file that is not what it says."""


class NotTriagedError(InvalidInputError):
    """Reading as a floor plan, or a relevance call on, a file triage did not call a non-plan
    (decision 0010): its own code, so a screen says why the button does nothing."""

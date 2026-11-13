"""Domain errors. Core raises them; app/main.py maps each one to an HTTP status."""


class DomainError(Exception):
    """An error the product expects (missing thing, bad input). Any other exception is a bug."""


class NotFoundError(DomainError):
    """The thing asked for doesn't exist."""

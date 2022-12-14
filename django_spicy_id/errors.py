class SpicyIdError(ValueError):
    """Base error class for the library."""


class MalformedSpicyIdError(SpicyIdError):
    """Thrown when the provided value does not satisfy the field's configuration."""

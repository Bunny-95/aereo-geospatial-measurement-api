"""Small set of application-level errors for request-safe failures."""


class UploadValidationError(ValueError):
    """Raised when an upload violates a supported safety or format rule."""

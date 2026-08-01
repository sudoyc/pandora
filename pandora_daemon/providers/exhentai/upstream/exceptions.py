"""Custom exception hierarchy for pandora_daemon.providers.exhentai.upstream."""


class ExhentaiError(Exception):
    """Base exception for all pandora_daemon.providers.exhentai.upstream errors."""


class AuthenticationError(ExhentaiError):
    """Authentication configuration is missing or rejected. Do not retry."""


class SessionError(AuthenticationError):
    """The configured upstream session is invalid or expired. Do not retry."""


class UpstreamError(ExhentaiError):
    """The upstream service or endpoint returned an unexpected HTTP status."""

    def __init__(
        self,
        message: str = "Upstream service request failed",
        *,
        status_code: int | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code


class ImageLimitError(ExhentaiError):
    """HTTP 509 — image viewing limit exceeded. Pause and wait."""


class GalleryNotFoundError(ExhentaiError):
    """Gallery removed or unavailable (kokomade / pining). Permanent failure."""


class GalleryOffensiveError(ExhentaiError):
    """Offensive content warning. Requires user confirmation."""


class ParseError(ExhentaiError):
    """Parsing failed — site structure may have changed. Retry 1-2 times."""


class NetworkError(ExhentaiError):
    """Network failure (timeout, connection reset). Exponential backoff retry."""

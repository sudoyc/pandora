"""Custom exception hierarchy for exhentai_api."""


class ExhentaiError(Exception):
    """Base exception for all exhentai_api errors."""


class AuthenticationError(ExhentaiError):
    """Sad Panda or cookie expiry. Do not retry."""


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

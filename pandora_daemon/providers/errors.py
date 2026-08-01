from __future__ import annotations


class ProviderError(Exception):
    """Base failure raised across the provider boundary."""

    kind = "provider"
    retryable = False

    def __init__(self, message: str = "Provider request failed", *, public_code: str = "provider") -> None:
        super().__init__(message)
        self.public_code = public_code


class ProviderAuthenticationError(ProviderError):
    kind = "auth"


class ProviderSessionError(ProviderAuthenticationError):
    kind = "session"


class ProviderUpstreamError(ProviderError):
    kind = "upstream"
    retryable = True

    def __init__(
        self,
        message: str = "Provider service request failed",
        *,
        status_code: int | None = None,
        public_code: str = "provider",
    ) -> None:
        super().__init__(message, public_code=public_code)
        self.status_code = status_code


class ProviderQuotaError(ProviderError):
    kind = "quota"


class ProviderGalleryNotFoundError(ProviderError):
    kind = "not_found"


class ProviderContentBlockedError(ProviderError):
    kind = "content_blocked"


class ProviderParseError(ProviderError):
    kind = "parse"
    retryable = True


class ProviderNetworkError(ProviderError):
    kind = "network"
    retryable = True

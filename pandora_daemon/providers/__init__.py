"""Provider contracts and built-in registry for Pandora."""

from pandora_daemon.providers.contracts import (
    GalleryComment,
    GalleryDetail,
    GalleryProvider,
    GallerySearchQuery,
    GallerySummary,
    ProviderContext,
)
from pandora_daemon.providers.errors import (
    ProviderAuthenticationError,
    ProviderContentBlockedError,
    ProviderError,
    ProviderGalleryNotFoundError,
    ProviderNetworkError,
    ProviderParseError,
    ProviderQuotaError,
    ProviderSessionError,
    ProviderUpstreamError,
)
from pandora_daemon.providers.registry import (
    ProviderFactory,
    ProviderRegistry,
    default_provider_registry,
)

__all__ = [
    "GalleryComment",
    "GalleryDetail",
    "GalleryProvider",
    "GallerySearchQuery",
    "GallerySummary",
    "ProviderContext",
    "ProviderAuthenticationError",
    "ProviderContentBlockedError",
    "ProviderError",
    "ProviderGalleryNotFoundError",
    "ProviderNetworkError",
    "ProviderParseError",
    "ProviderQuotaError",
    "ProviderSessionError",
    "ProviderUpstreamError",
    "ProviderFactory",
    "ProviderRegistry",
    "default_provider_registry",
]

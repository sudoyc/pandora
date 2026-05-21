"""Config system for pandora-daemon.

Reads and writes configuration from/to a TOML file.
Default location: ~/.config/pandora/config.toml
"""
from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import tomli_w

DEFAULT_CONFIG_PATH = Path("~/.config/pandora/config.toml")


@dataclass
class CredentialsConfig:
    """ExHentai session credentials."""

    igneous: str = ""
    ipb_member_id: str = ""


@dataclass
class ServerConfig:
    """Daemon HTTP server settings."""

    host: str = "127.0.0.1"
    port: int = 7860


@dataclass
class DownloadConfig:
    """Download manager settings."""

    path: str = "~/Downloads/pandora"
    gallery_concurrency: int = 2
    page_concurrency: int = 4
    max_retry: int = 3
    retry_base_delay: float = 2.0


@dataclass
class CacheConfig:
    """Cache settings."""

    image_dir: str = "~/.cache/pandora/images"
    image_max_size_mb: int = 2048
    gallery_ttl_seconds: int = 300
    prefetch_ahead: int = 3
    prefetch_behind: int = 1
    eviction_interval_seconds: int = 600


@dataclass
class NetworkConfig:
    """Network settings (proxy, timeout)."""

    proxy: str = ""
    timeout: int = 30


@dataclass
class PandoraConfig:
    """Top-level pandora daemon configuration."""

    credentials: CredentialsConfig = field(default_factory=CredentialsConfig)
    server: ServerConfig = field(default_factory=ServerConfig)
    download: DownloadConfig = field(default_factory=DownloadConfig)
    cache: CacheConfig = field(default_factory=CacheConfig)
    network: NetworkConfig = field(default_factory=NetworkConfig)

    def __post_init__(self) -> None:
        # Allow callers to pass None for sub-configs; replace with defaults.
        if self.credentials is None:
            self.credentials = CredentialsConfig()
        if self.server is None:
            self.server = ServerConfig()
        if self.download is None:
            self.download = DownloadConfig()
        if self.cache is None:
            self.cache = CacheConfig()
        if self.network is None:
            self.network = NetworkConfig()

    def to_public_dict(self) -> dict[str, Any]:
        """Return config as a dict with credentials and proxy secrets stripped out."""
        return {
            "server": {
                "host": self.server.host,
                "port": self.server.port,
            },
            "download": {
                "path": self.download.path,
                "gallery_concurrency": self.download.gallery_concurrency,
                "page_concurrency": self.download.page_concurrency,
                "max_retry": self.download.max_retry,
                "retry_base_delay": self.download.retry_base_delay,
            },
            "cache": {
                "image_dir": self.cache.image_dir,
                "image_max_size_mb": self.cache.image_max_size_mb,
                "gallery_ttl_seconds": self.cache.gallery_ttl_seconds,
                "prefetch_ahead": self.cache.prefetch_ahead,
                "prefetch_behind": self.cache.prefetch_behind,
                "eviction_interval_seconds": self.cache.eviction_interval_seconds,
            },
            "network": {
                "proxy_configured": bool(self.network.proxy),
                "timeout": self.network.timeout,
            },
        }

    def _to_dict(self) -> dict[str, Any]:
        """Return full config as a dict (including credentials)."""
        return {
            "credentials": {
                "igneous": self.credentials.igneous,
                "ipb_member_id": self.credentials.ipb_member_id,
            },
            **self.to_public_dict(),
        }


def load_config(path: Path | str = DEFAULT_CONFIG_PATH) -> PandoraConfig:
    """Load config from a TOML file.

    If the file does not exist, a default config is written to ``path`` and
    returned.  Missing TOML sections fall back to their dataclass defaults.
    """
    path = Path(path)

    if not path.exists():
        cfg = PandoraConfig()
        save_config(cfg, path)
        return cfg

    with open(path, "rb") as f:
        data = tomllib.load(f)

    cred_data = data.get("credentials", {})
    credentials = CredentialsConfig(
        igneous=cred_data.get("igneous", ""),
        ipb_member_id=cred_data.get("ipb_member_id", ""),
    )

    srv_data = data.get("server", {})
    server = ServerConfig(
        host=srv_data.get("host", "127.0.0.1"),
        port=srv_data.get("port", 7860),
    )

    dl_data = data.get("download", {})
    gallery_concurrency = dl_data.get("gallery_concurrency",
                                       dl_data.get("concurrency", 2))
    download = DownloadConfig(
        path=dl_data.get("path", "~/Downloads/pandora"),
        gallery_concurrency=gallery_concurrency,
        page_concurrency=dl_data.get("page_concurrency", 4),
        max_retry=dl_data.get("max_retry", 3),
        retry_base_delay=dl_data.get("retry_base_delay", 2.0),
    )

    cache_data = data.get("cache", {})
    cache = CacheConfig(
        image_dir=cache_data.get("image_dir", "~/.cache/pandora/images"),
        image_max_size_mb=cache_data.get("image_max_size_mb", 2048),
        gallery_ttl_seconds=cache_data.get("gallery_ttl_seconds", 300),
        prefetch_ahead=cache_data.get("prefetch_ahead", 3),
        prefetch_behind=cache_data.get("prefetch_behind", 1),
        eviction_interval_seconds=cache_data.get("eviction_interval_seconds", 600),
    )

    net_data = data.get("network", {})
    network = NetworkConfig(
        proxy=net_data.get("proxy", ""),
        timeout=net_data.get("timeout", 30),
    )

    return PandoraConfig(
        credentials=credentials,
        server=server,
        download=download,
        cache=cache,
        network=network,
    )


def save_config(config: PandoraConfig, path: Path | str = DEFAULT_CONFIG_PATH) -> None:
    """Persist *config* to a TOML file at *path*.

    Parent directories are created automatically.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    toml_bytes = tomli_w.dumps(config._to_dict()).encode()
    path.write_bytes(toml_bytes)

"""Tests for pandora_daemon.config module."""
import tomllib
from pathlib import Path

import pytest
import tomli_w

from pandora_daemon.config import (
    CacheConfig,
    CredentialsConfig,
    DownloadConfig,
    PandoraConfig,
    ServerConfig,
    load_config,
    save_config,
)


class TestDefaultConfig:
    """Test that default config values are correct."""

    def test_default_credentials_config(self):
        cred = CredentialsConfig()
        assert cred.igneous == ""
        assert cred.ipb_member_id == ""

    def test_default_server_config(self):
        srv = ServerConfig()
        assert srv.host == "127.0.0.1"
        assert srv.port == 7860

    def test_default_download_config(self):
        cfg = DownloadConfig()
        assert cfg.path == "~/Downloads/pandora"
        assert cfg.gallery_concurrency == 2
        assert cfg.page_concurrency == 4
        assert cfg.max_retry == 3
        assert cfg.retry_base_delay == 2.0

    def test_default_cache_config(self):
        cache = CacheConfig()
        assert cache.image_dir == "~/.cache/pandora/images"
        assert cache.image_max_size_mb == 2048
        assert cache.gallery_ttl_seconds == 300
        assert cache.prefetch_ahead == 3
        assert cache.prefetch_behind == 1

    def test_default_pandora_config(self):
        cfg = PandoraConfig()
        assert isinstance(cfg.credentials, CredentialsConfig)
        assert isinstance(cfg.server, ServerConfig)
        assert isinstance(cfg.download, DownloadConfig)
        assert isinstance(cfg.cache, CacheConfig)


class TestLoadConfig:
    """Test load_config behavior."""

    def test_load_config_creates_default(self, tmp_path):
        config_path = tmp_path / "config.toml"
        assert not config_path.exists()

        cfg = load_config(config_path)

        assert config_path.exists(), "config file should be created if missing"
        assert isinstance(cfg, PandoraConfig)
        assert cfg.server.host == "127.0.0.1"
        assert cfg.server.port == 7860
        assert cfg.download.path == "~/Downloads/pandora"
        assert cfg.download.gallery_concurrency == 2

    def test_load_config_reads_existing(self, tmp_path):
        config_path = tmp_path / "config.toml"
        data = {
            "credentials": {"igneous": "abc123", "ipb_member_id": "999"},
            "server": {"host": "0.0.0.0", "port": 9999},
            "download": {"path": "/custom/path", "gallery_concurrency": 5},
            "cache": {
                "image_dir": "/custom/cache",
                "image_max_size_mb": 1000,
                "gallery_ttl_seconds": 600,
            },
        }
        config_path.write_bytes(tomli_w.dumps(data).encode())

        cfg = load_config(config_path)

        assert cfg.credentials.igneous == "abc123"
        assert cfg.credentials.ipb_member_id == "999"
        assert cfg.server.host == "0.0.0.0"
        assert cfg.server.port == 9999
        assert cfg.download.path == "/custom/path"
        assert cfg.download.gallery_concurrency == 5
        assert cfg.cache.image_dir == "/custom/cache"
        assert cfg.cache.image_max_size_mb == 1000
        assert cfg.cache.gallery_ttl_seconds == 600

    def test_load_config_partial_toml(self, tmp_path):
        """Missing sections should fall back to defaults."""
        config_path = tmp_path / "config.toml"
        data = {
            "server": {"port": 8888},
        }
        config_path.write_bytes(tomli_w.dumps(data).encode())

        cfg = load_config(config_path)

        # Explicitly set value is preserved
        assert cfg.server.port == 8888
        # Missing key within section falls back to default
        assert cfg.server.host == "127.0.0.1"
        # Entirely missing sections fall back to defaults
        assert cfg.credentials.igneous == ""
        assert cfg.download.path == "~/Downloads/pandora"
        assert cfg.cache.image_max_size_mb == 2048


    def test_load_config_backward_compat_concurrency(self, tmp_path):
        """Old 'concurrency' field maps to gallery_concurrency."""
        config_path = tmp_path / "config.toml"
        data = {"download": {"concurrency": 5, "path": "~/dl"}}
        config_path.write_bytes(tomli_w.dumps(data).encode())
        cfg = load_config(config_path)
        assert cfg.download.gallery_concurrency == 5
        assert cfg.download.page_concurrency == 4

    def test_load_config_new_fields(self, tmp_path):
        """New fields load correctly."""
        config_path = tmp_path / "config.toml"
        data = {"download": {
            "gallery_concurrency": 1, "page_concurrency": 8,
            "max_retry": 5, "retry_base_delay": 1.0,
        }}
        config_path.write_bytes(tomli_w.dumps(data).encode())
        cfg = load_config(config_path)
        assert cfg.download.gallery_concurrency == 1
        assert cfg.download.page_concurrency == 8
        assert cfg.download.max_retry == 5
        assert cfg.download.retry_base_delay == 1.0


class TestSaveConfig:
    """Test save_config behavior."""

    def test_save_config(self, tmp_path):
        config_path = tmp_path / "subdir" / "config.toml"
        cfg = PandoraConfig(
            credentials=CredentialsConfig(igneous="tok", ipb_member_id="42"),
            server=ServerConfig(host="0.0.0.0", port=1234),
            download=DownloadConfig(path="/dl", gallery_concurrency=2),
            cache=CacheConfig(
                image_dir="/cache",
                image_max_size_mb=100,
                gallery_ttl_seconds=60,
            ),
        )

        save_config(cfg, config_path)

        assert config_path.exists()
        with open(config_path, "rb") as f:
            data = tomllib.load(f)

        assert data["credentials"]["igneous"] == "tok"
        assert data["credentials"]["ipb_member_id"] == "42"
        assert data["server"]["host"] == "0.0.0.0"
        assert data["server"]["port"] == 1234
        assert data["download"]["path"] == "/dl"
        assert data["download"]["gallery_concurrency"] == 2
        assert data["cache"]["image_dir"] == "/cache"
        assert data["cache"]["image_max_size_mb"] == 100
        assert data["cache"]["gallery_ttl_seconds"] == 60

    def test_save_and_reload(self, tmp_path):
        config_path = tmp_path / "config.toml"
        original = PandoraConfig(
            server=ServerConfig(host="192.168.1.1", port=5555),
        )

        save_config(original, config_path)
        reloaded = load_config(config_path)

        assert reloaded.server.host == "192.168.1.1"
        assert reloaded.server.port == 5555
        # Defaults remain intact
        assert reloaded.download.gallery_concurrency == 2


class TestToPublicDict:
    """Test to_public_dict() strips credentials."""

    def test_config_to_dict_omits_credentials(self):
        cfg = PandoraConfig(
            credentials=CredentialsConfig(igneous="secret", ipb_member_id="12345"),
        )

        public = cfg.to_public_dict()

        assert "credentials" not in public, "credentials section must be omitted"
        assert "server" in public
        assert "download" in public
        assert "cache" in public

    def test_to_public_dict_contains_correct_values(self):
        cfg = PandoraConfig(
            server=ServerConfig(host="127.0.0.1", port=7860),
            download=DownloadConfig(path="~/Downloads/pandora", gallery_concurrency=2),
        )

        public = cfg.to_public_dict()

        assert public["server"]["host"] == "127.0.0.1"
        assert public["server"]["port"] == 7860
        assert public["download"]["path"] == "~/Downloads/pandora"
        assert public["download"]["gallery_concurrency"] == 2

    def test_to_public_dict_contains_new_download_fields(self):
        cfg = PandoraConfig()
        d = cfg.to_public_dict()
        dl = d["download"]
        assert "gallery_concurrency" in dl
        assert "page_concurrency" in dl
        assert "max_retry" in dl
        assert "retry_base_delay" in dl
        assert "concurrency" not in dl

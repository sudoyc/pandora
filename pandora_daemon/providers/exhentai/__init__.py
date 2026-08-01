"""Built-in ExHentai provider adapter."""

PROVIDER_ID = "exhentai"
FACTORY_TARGET = "pandora_daemon.providers.exhentai.adapter:create_provider"

__all__ = ["FACTORY_TARGET", "PROVIDER_ID"]

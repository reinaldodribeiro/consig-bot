"""ProxyProvider — interface for future rotative pools (v0.4)."""
from __future__ import annotations

from abc import ABC, abstractmethod

from app.models.config import ProxyConfig


class ProxyProvider(ABC):
    @abstractmethod
    def next(self) -> ProxyConfig:
        """Return a proxy to use. May be the same one repeatedly (static) or rotated."""


class NoProxyProvider(ProxyProvider):
    def next(self) -> ProxyConfig:
        return ProxyConfig(enabled=False)


class StaticProxyProvider(ProxyProvider):
    def __init__(self, proxy: ProxyConfig) -> None:
        self._proxy = proxy

    def next(self) -> ProxyConfig:
        return self._proxy


def build_proxy_provider(config: ProxyConfig) -> ProxyProvider:
    if not config.enabled:
        return NoProxyProvider()
    return StaticProxyProvider(config)

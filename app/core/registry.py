"""BotRegistry — auto-discovery of bot implementations under app.bots.*"""
from __future__ import annotations

import importlib
import pkgutil

from loguru import logger

from app.core.base_bot import BaseBot
from app.models.config import AppConfig

_BOTS: dict[str, type[BaseBot]] = {}


def register_bot(cls: type[BaseBot]) -> type[BaseBot]:
    """Decorator. Registers a BaseBot subclass under its `key` class attribute."""
    if not hasattr(cls, "key") or not getattr(cls, "key", None):
        raise ValueError(f"{cls.__name__} sem atributo 'key'")
    key = cls.key
    if key in _BOTS and _BOTS[key] is not cls:
        logger.warning("Bot '{}' substituído: {} → {}", key, _BOTS[key].__name__, cls.__name__)
    _BOTS[key] = cls
    logger.debug("Bot registrado: {} ({})", key, cls.__name__)
    return cls


class BotRegistry:
    @staticmethod
    def discover() -> None:
        """Imports every submodule under app.bots so @register_bot fires."""
        import app.bots as pkg

        for _finder, name, ispkg in pkgutil.iter_modules(pkg.__path__):
            mod_path = f"{pkg.__name__}.{name}"
            try:
                if ispkg:
                    # try to import the bot.py inside each subpackage
                    importlib.import_module(f"{mod_path}.bot")
                else:
                    importlib.import_module(mod_path)
            except Exception as exc:
                logger.error("Falha ao importar bot '{}': {}", mod_path, exc)

    @staticmethod
    def list_available(config: AppConfig) -> list[type[BaseBot]]:
        """Bots that are both registered AND configured in config.sistemas."""
        return [cls for key, cls in _BOTS.items() if key in config.sistemas]

    @staticmethod
    def list_all() -> list[type[BaseBot]]:
        return list(_BOTS.values())

    @staticmethod
    def get(key: str) -> type[BaseBot]:
        if key not in _BOTS:
            raise KeyError(f"Bot '{key}' não registrado. Disponíveis: {list(_BOTS.keys())}")
        return _BOTS[key]

    @staticmethod
    def create(key: str, config: AppConfig) -> BaseBot:
        return BotRegistry.get(key)(config)

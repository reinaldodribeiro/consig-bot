"""Retry decorator with exponential backoff for transient bot errors."""
from __future__ import annotations

import functools
import time
from collections.abc import Callable
from typing import ParamSpec, TypeVar

from loguru import logger

P = ParamSpec("P")
R = TypeVar("R")


def retry(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    backoff: float = 2.0,
    max_delay: float = 30.0,
    on: tuple[type[BaseException], ...] = (Exception,),
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Retry a callable on listed exception types with exponential backoff.

    - max_attempts: total attempts (including the first)
    - base_delay: seconds before second attempt
    - backoff: multiplier per failed attempt
    - max_delay: cap per sleep
    - on: tuple of exception classes to retry; others propagate immediately
    """
    if max_attempts < 1:
        raise ValueError("max_attempts must be >= 1")

    def decorator(fn: Callable[P, R]) -> Callable[P, R]:
        @functools.wraps(fn)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            attempt = 0
            delay = base_delay
            last_exc: BaseException | None = None
            while attempt < max_attempts:
                attempt += 1
                try:
                    return fn(*args, **kwargs)
                except on as exc:
                    last_exc = exc
                    if attempt >= max_attempts:
                        logger.warning(
                            "{} falhou após {} tentativas: {}",
                            fn.__name__, attempt, exc,
                        )
                        raise
                    logger.info(
                        "{} tentativa {}/{} falhou: {} — aguardando {:.1f}s",
                        fn.__name__, attempt, max_attempts, exc, delay,
                    )
                    time.sleep(delay)
                    delay = min(delay * backoff, max_delay)
            assert last_exc is not None  # unreachable
            raise last_exc

        return wrapper

    return decorator

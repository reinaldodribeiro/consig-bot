"""State machine for page-level interactions during a query."""
from __future__ import annotations

from enum import Enum


class PageState(str, Enum):
    FOUND = "found"
    NOT_FOUND = "not_found"
    CAPTCHA = "captcha"
    SESSION_EXPIRED = "session_expired"
    RATE_LIMITED = "rate_limited"
    ERROR = "error"

"""Domain exception hierarchy. All bot-related errors derive from BotError."""
from __future__ import annotations


class BotError(Exception):
    """Base for any bot-related error."""


class ConfigError(BotError):
    """Invalid or missing configuration."""


class AuthenticationError(BotError):
    """Login failed (wrong credentials, locked account, unexpected page)."""


class CaptchaRequired(BotError):
    """Captcha must be solved before proceeding."""


class SessionExpired(BotError):
    """Session/cookie no longer valid; re-login required."""


class RateLimited(BotError):
    """Site rate-limited the request — backoff + retry."""


class NotFoundError(BotError):
    """Site says 'no information for this query' — expected, not a failure."""


class ParseError(BotError):
    """Could not parse expected DOM structure."""


class NavigationTimeout(BotError):
    """Page did not reach expected state within timeout."""

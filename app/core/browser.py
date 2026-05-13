"""Playwright browser session — context manager for one-page sync flows."""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from loguru import logger

from app.core.exceptions import BotError
from app.models.config import BotRuntimeConfig

if TYPE_CHECKING:
    from playwright.sync_api import Browser, BrowserContext, Page, Playwright

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36"
)


class BrowserSession:
    """Single-page Playwright session. Use as context manager.

    Future-ready: a `concurrency` flag + `new_page()` method would allow
    multiple pages per context for parallel workers.
    """

    def __init__(self, config: BotRuntimeConfig, trace_path: Path | None = None) -> None:
        self.config = config
        self.trace_path = trace_path
        self._pw: Playwright | None = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None
        self._tracing_active = False

    @property
    def page(self) -> Page:
        if self._page is None:
            raise BotError("BrowserSession not started — use 'with BrowserSession(...) as session:'")
        return self._page

    def __enter__(self) -> BrowserSession:
        # Lazy import keeps Playwright optional at module load time
        from playwright.sync_api import sync_playwright

        self._pw = sync_playwright().start()
        proxy = self._proxy_args()
        logger.info(
            "Iniciando Chromium (headless={}, proxy={})",
            self.config.headless,
            "yes" if proxy else "no",
        )
        self._browser = self._pw.chromium.launch(
            headless=self.config.headless,
            proxy=proxy,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
            ],
        )
        self._context = self._browser.new_context(
            viewport={"width": 1366, "height": 768},
            locale="pt-BR",
            timezone_id="America/Sao_Paulo",
            user_agent=DEFAULT_USER_AGENT,
        )
        self._context.set_default_timeout(self.config.timeout_selector_ms)
        self._context.set_default_navigation_timeout(self.config.timeout_navigation_ms)
        self._page = self._context.new_page()

        if self.config.debug and self.trace_path is not None:
            try:
                self._context.tracing.start(screenshots=True, snapshots=True, sources=False)
                self._tracing_active = True
                logger.info("Playwright tracing ativo — destino: {}", self.trace_path)
            except Exception as exc:
                logger.warning("Falha ao iniciar tracing: {}", exc)

        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self._cleanup()

    def _cleanup(self) -> None:
        if self._tracing_active and self._context is not None and self.trace_path is not None:
            try:
                self.trace_path.parent.mkdir(parents=True, exist_ok=True)
                self._context.tracing.stop(path=str(self.trace_path))
                logger.info("Trace salvo: {}", self.trace_path)
            except Exception as exc:
                logger.warning("Falha ao salvar trace: {}", exc)
            self._tracing_active = False

        for attr in ("_page", "_context", "_browser"):
            obj = getattr(self, attr, None)
            if obj is not None:
                try:
                    obj.close()
                except Exception as e:  # noqa: BLE001
                    logger.debug("Erro fechando {}: {}", attr, e)
                setattr(self, attr, None)
        if self._pw is not None:
            try:
                self._pw.stop()
            except Exception as e:  # noqa: BLE001
                logger.debug("Erro parando Playwright: {}", e)
            self._pw = None

    def _proxy_args(self) -> dict | None:
        p = self.config.proxy
        if not p.enabled or not p.server:
            return None
        args: dict = {"server": p.server}
        if p.username:
            args["username"] = p.username
        if p.password:
            args["password"] = p.password.get_secret_value()
        return args

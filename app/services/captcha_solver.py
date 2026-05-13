"""CaptchaSolver — abstract + manual implementation. 2Captcha hook left for v0.3."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from loguru import logger
from rich.console import Console
from rich.prompt import Prompt

from app.models.config import CaptchaConfig

if TYPE_CHECKING:
    from playwright.sync_api import Page

_console = Console()


class CaptchaSolver(ABC):
    @abstractmethod
    def solve(self, page: Page, reason: str = "") -> None:
        """Block until captcha is resolved. Raise to abort the run."""


class ManualCaptcha(CaptchaSolver):
    """Pauses execution and asks the human to solve the captcha in the browser."""

    def solve(self, page: Page, reason: str = "") -> None:
        msg = f"Captcha detectado{(' — ' + reason) if reason else ''}."
        logger.warning(msg)
        _console.print(f"\n[bold yellow]{msg}[/bold yellow]")
        _console.print("[yellow]Resolva o captcha no navegador e pressione ENTER aqui para continuar.[/yellow]")
        Prompt.ask("[cyan]Pressione ENTER quando resolver[/cyan]", default="")


def build_captcha_solver(config: CaptchaConfig) -> CaptchaSolver:
    if config.mode == "manual":
        return ManualCaptcha()
    raise NotImplementedError(
        f"Captcha mode '{config.mode}' ainda não implementado (planejado para v0.3)."
    )

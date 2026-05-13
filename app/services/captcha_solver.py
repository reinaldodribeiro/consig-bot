"""CaptchaSolver — abstract + manual implementation. 2Captcha hook left for v0.3."""
from __future__ import annotations

import subprocess
import sys
import tempfile
from abc import ABC, abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING

from loguru import logger
from rich.console import Console
from rich.prompt import Prompt

from app.models.config import CaptchaConfig

if TYPE_CHECKING:
    from playwright.sync_api import Page

_console = Console()


def prompt_image_captcha(image_bytes: bytes, *, label: str = "captcha") -> str:
    """Render the captcha image inline in the terminal and prompt the user for the code.

    Uses term-image (kitty/iTerm2/sixel auto-detect, falls back to unicode blocks).
    If terminal rendering fails, opens the image in the system default viewer instead.
    """
    suffix = ".png"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False, prefix=f"{label}_") as f:
        f.write(image_bytes)
        path = Path(f.name)

    logger.info("Captcha salvo em {}", path)

    rendered = _render_image_in_terminal(path)
    if not rendered:
        _open_image_in_system_viewer(path)
        _console.print(f"[yellow]Imagem aberta no viewer do sistema: {path}[/yellow]")

    code = Prompt.ask("\n[cyan]Digite o código do captcha[/cyan]", default="")
    return code.strip()


def _render_image_in_terminal(path: Path) -> bool:
    """Render an image inline in the terminal. Returns True on success."""
    try:
        import warnings
        from term_image.image import AutoImage
        from PIL import Image
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")  # silence "not in a terminal" warning
            pil_img = Image.open(path)
            # Captchas are detailed — render tall (~20 rows) so distorted chars are legible.
            # Modest size — large enough to read distorted chars, small enough not to dominate the terminal.
            # Block chars are ~1:2 (h:w), so target_w ≈ aspect * target_h * 2.
            w, h = pil_img.size
            target_h = 6
            calculated_w = int(w * (target_h * 2) / max(h, 1))
            target_w = max(24, min(36, calculated_w))
            img = AutoImage(pil_img, width=target_w, height=target_h)
            _console.print("")
            print(img)
            _console.print("")
        return True
    except Exception as exc:
        logger.debug("Falha ao renderizar captcha no terminal: {}", exc)
        return False


def _open_image_in_system_viewer(path: Path) -> None:
    try:
        if sys.platform == "darwin":
            subprocess.Popen(["open", str(path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        elif sys.platform.startswith("linux"):
            subprocess.Popen(["xdg-open", str(path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        elif sys.platform == "win32":
            import os
            os.startfile(str(path))  # type: ignore[attr-defined]
    except Exception as exc:
        logger.debug("Não foi possível abrir captcha no viewer: {}", exc)


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

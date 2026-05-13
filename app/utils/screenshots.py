"""Screenshot helper — saves to disk with timestamp + label."""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from loguru import logger

from app.utils.dates import now_filename_ts
from app.utils.paths import ensure_dir

if TYPE_CHECKING:
    from playwright.sync_api import Page


def save_screenshot(page: Page, label: str, screenshot_dir: Path) -> Path | None:
    """Save a screenshot. Returns path or None on failure (never raises)."""
    try:
        ensure_dir(screenshot_dir)
        safe_label = "".join(c if c.isalnum() or c in "-_" else "_" for c in label)[:60]
        path = screenshot_dir / f"{now_filename_ts()}_{safe_label}.png"
        page.screenshot(path=str(path), full_page=False)
        logger.debug("Screenshot saved: {}", path.name)
        return path
    except Exception as exc:
        logger.warning("Failed to save screenshot '{}': {}", label, exc)
        return None

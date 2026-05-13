"""Parsers — DOM extraction for Econsig. Pure functions, never navigate."""
from __future__ import annotations
import re
from typing import TYPE_CHECKING, Literal
from loguru import logger
from app.bots.econsig import selectors as sel
from app.bots.econsig.schema import EconsigMargens

if TYPE_CHECKING:
    from playwright.sync_api import Page


def parse_margens_success(page: Page) -> EconsigMargens | None:
    """Read MSG_SUCCESS innerHTML and parse margem fields. Returns None if absent or empty."""
    loc = page.locator(sel.MSG_SUCCESS)
    count = loc.count()
    if count == 0:
        logger.info("parse_margens_success: span#idMsgSuccessSession NÃO existe no DOM")
        return None

    try:
        html = loc.first.inner_html(timeout=3000)
    except Exception as exc:
        logger.warning("parse_margens_success: inner_html error: {}", exc)
        return None

    text_only = re.sub(r"<[^>]+>", "", html).strip()
    if not text_only:
        logger.info("parse_margens_success: span existe mas está vazio")
        return None

    logger.info("parse_margens_success: conteúdo bruto={!r}", text_only[:200])

    # Normalise <br> variants to newlines for easier regex matching
    html_normalised = re.sub(r"<br\s*/?>", "\n", html, flags=re.IGNORECASE)

    def _extract(pattern: str) -> str:
        m = re.search(pattern, html_normalised, re.IGNORECASE)
        if not m:
            return ""
        return m.group(1).strip()

    margem_emprestimo = _extract(r"MARGEM\s+EMPR[EÉ]STIMO\s*:\s*([^\n<]+)")
    margem_cartao = _extract(r"MARGEM\s+CART[AÃ]O\s*:\s*([^\n<]+)")
    data_carga = _extract(r"Data\s+da\s+Carga\s+das\s+Margens\s*:\s*([^\n<]+)")

    logger.info(
        "parse_margens_success: emprestimo={!r} cartao={!r} data_carga={!r}",
        margem_emprestimo, margem_cartao, data_carga,
    )
    return EconsigMargens(
        margem_emprestimo=margem_emprestimo,
        margem_cartao=margem_cartao,
        data_carga=data_carga,
    )


def parse_error_message(page: Page) -> str | None:
    """Return text of MSG_ERROR span if present, else None."""
    loc = page.locator(sel.MSG_ERROR)
    if loc.count() == 0:
        return None
    try:
        txt = (loc.first.inner_text(timeout=3000) or "").strip()
    except Exception as exc:
        logger.debug("parse_error_message: inner_text error: {}", exc)
        return None
    return txt or None


def classify_error(msg: str) -> Literal["captcha_invalid", "not_found", "server_excluded", "other"]:
    """Classify an error message string by substring match (case-insensitive)."""
    lower = msg.lower()
    if sel.CAPTCHA_INVALID_TEXT.lower() in lower:
        return "captcha_invalid"
    if sel.NOT_FOUND_TEXT_FRAGMENT.lower() in lower:
        return "not_found"
    if sel.SERVER_EXCLUDED_TEXT_FRAGMENT.lower() in lower:
        return "server_excluded"
    return "other"

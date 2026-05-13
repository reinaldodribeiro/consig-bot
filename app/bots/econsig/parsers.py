"""Parsers — DOM extraction for Econsig. Pure functions, never navigate."""
from __future__ import annotations
import re
from typing import TYPE_CHECKING, Literal, TypedDict
from loguru import logger
from app.bots.econsig import selectors as sel
from app.bots.econsig.schema import EconsigMargens

if TYPE_CHECKING:
    from playwright.sync_api import Page


class EconsigConsultaDados(TypedDict):
    margens: EconsigMargens
    data_nascimento: str
    cpf: str


_DATA_LIST_JS = """
() => {
    const dl = document.querySelector('dl.data-list');
    if (!dl) return null;
    const out = {};
    const kids = Array.from(dl.children);
    for (let i = 0; i < kids.length - 1; i++) {
        if (kids[i].tagName === 'DT' && kids[i+1].tagName === 'DD') {
            const key = (kids[i].textContent || '').trim();
            const value = (kids[i+1].textContent || '').replace(/\\u00a0/g, ' ').trim();
            out[key] = value.replace(/\\s+/g, ' ');
        }
    }
    return out;
}
"""


def parse_consulta_success(page: Page) -> EconsigConsultaDados | None:
    """Parse the result <dl class="data-list">.

    Returns a dict with margens, data_nascimento, and cpf — or None if the <dl> is absent.
    """
    if page.locator(sel.DATA_LIST).count() == 0:
        logger.info("parse_consulta_success: <dl.data-list> NÃO existe no DOM")
        return None

    try:
        data = page.evaluate(_DATA_LIST_JS)
    except Exception as exc:
        logger.warning("parse_consulta_success: evaluate error: {}", exc)
        return None

    if not data:
        logger.info("parse_consulta_success: <dl.data-list> existe mas vazio")
        return None

    logger.info("parse_consulta_success: campos lidos={!r}", list(data.keys()))

    # Helper: case-insensitive key lookup (labels may shift in capitalization)
    def _get(label_fragment: str) -> str:
        frag = label_fragment.lower()
        for k, v in data.items():
            if frag in k.lower():
                return v
        return ""

    nasc_cpf_raw = _get("data de nascimento")  # "23/03/1952 - 617.361.121-04"
    parts = [p.strip() for p in nasc_cpf_raw.split(" - ", 1)]
    data_nascimento = parts[0] if len(parts) >= 1 else ""
    cpf = parts[1] if len(parts) >= 2 else ""

    margens = EconsigMargens(
        margem_emprestimo=_get("margem empr"),  # matches EMPRÉSTIMO / EMPRESTIMO
        margem_cartao=_get("margem cart"),       # matches CARTÃO / CARTAO
    )

    logger.info(
        "parse_consulta_success: emprestimo={!r} cartao={!r} nascimento={!r} cpf={!r}",
        margens.margem_emprestimo, margens.margem_cartao, data_nascimento, cpf,
    )
    return {"margens": margens, "data_nascimento": data_nascimento, "cpf": cpf}


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

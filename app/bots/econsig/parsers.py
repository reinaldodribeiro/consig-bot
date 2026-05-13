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
    // The page has multiple <dl class="data-list"> (a summary card + the result card).
    // Prefer the one inside #consultaMargem; fall back to the <dl> with the most <dt> children.
    let dl = document.querySelector('#consultaMargem dl.data-list');
    if (!dl) {
        const all = Array.from(document.querySelectorAll('dl.data-list'));
        all.sort((a, b) => b.querySelectorAll('dt').length - a.querySelectorAll('dt').length);
        dl = all[0] || null;
    }
    if (!dl) return null;
    const dts = dl.querySelectorAll('dt');
    const dds = dl.querySelectorAll('dd');
    const out = {};
    const n = Math.min(dts.length, dds.length);
    for (let i = 0; i < n; i++) {
        const key = (dts[i].textContent || '').replace(/\\u00a0/g, ' ').trim();
        const value = (dds[i].textContent || '').replace(/\\u00a0/g, ' ').trim();
        out[key] = value.replace(/\\s+/g, ' ');
    }
    return out;
}
"""


def _parse_margens_from_span(page: Page) -> EconsigMargens:
    """Read the success message span and regex out MARGEM EMPRÉSTIMO and MARGEM CARTÃO."""
    loc = page.locator(sel.MSG_SUCCESS)
    if loc.count() == 0:
        logger.info("_parse_margens_from_span: span#idMsgSuccessSession NÃO existe")
        return EconsigMargens()

    try:
        html = loc.first.inner_html(timeout=3000)
    except Exception as exc:
        logger.warning("_parse_margens_from_span: inner_html error: {}", exc)
        return EconsigMargens()

    # Normalize <br> variants to newlines so the regex's [^\n<] terminator works.
    html_normalised = re.sub(r"<br\s*/?>", "\n", html, flags=re.IGNORECASE)
    # Strip <span class="Rotulo">R$</span> wrapper so the value comes through cleanly.
    text = re.sub(r"<[^>]+>", "", html_normalised).replace("\u00a0", " ")

    def _extract(pattern: str) -> str:
        m = re.search(pattern, text, re.IGNORECASE)
        return m.group(1).strip() if m else ""

    margem_emprestimo = _extract(r"MARGEM\s+EMPR[EÉ]STIMO\s*:\s*([^\n]+)")
    margem_cartao = _extract(r"MARGEM\s+CART[AÃ]O\s*:\s*([^\n]+)")

    logger.info(
        "_parse_margens_from_span: emprestimo={!r} cartao={!r}",
        margem_emprestimo, margem_cartao,
    )
    return EconsigMargens(margem_emprestimo=margem_emprestimo, margem_cartao=margem_cartao)


def parse_consulta_success(page: Page) -> EconsigConsultaDados | None:
    """Parse a successful Econsig query result.

    - Margens are read from span#idMsgSuccessSession (via regex).
    - CPF and data_nascimento are read from the <dl> inside #consultaMargem.
    Returns None only if BOTH sources are absent (no result at all).
    """
    data_list_count = page.locator(sel.DATA_LIST).count()
    span_count = page.locator(sel.MSG_SUCCESS).count()

    # Diagnostic: what <dl>s and #consultaMargem actually exist right now?
    try:
        diag = page.evaluate("""() => {
            const dls = Array.from(document.querySelectorAll('dl.data-list'));
            const cm = document.querySelector('#consultaMargem');
            return {
                allDLs: dls.map(d => ({
                    parent: d.parentElement ? (d.parentElement.id || d.parentElement.className) : '',
                    dts: d.querySelectorAll('dt').length,
                    firstDt: (d.querySelector('dt') || {}).textContent || '',
                })),
                hasConsultaMargem: !!cm,
                consultaMargemHTML: cm ? cm.outerHTML.slice(0, 400) : null,
                successSpanText: (document.querySelector('span#idMsgSuccessSession') || {}).textContent || '',
            };
        }""")
        logger.info("parse_consulta_success [DIAG]: {!r}", diag)
    except Exception as exc:
        logger.debug("parse_consulta_success [DIAG] failed: {}", exc)

    if data_list_count == 0 and span_count == 0:
        logger.info("parse_consulta_success: nem <dl.data-list> nem span#idMsgSuccessSession no DOM")
        return None

    # --- Margens via span ---
    margens = _parse_margens_from_span(page)

    # --- CPF + data_nascimento via <dl> ---
    data_nascimento = ""
    cpf = ""
    if data_list_count > 0:
        try:
            dl_data = page.evaluate(_DATA_LIST_JS)
        except Exception as exc:
            logger.warning("parse_consulta_success: evaluate error: {}", exc)
            dl_data = None

        if dl_data:
            logger.info("parse_consulta_success: {} campos lidos do <dl>:", len(dl_data))
            for k, v in dl_data.items():
                logger.info("  {!r} => {!r}", k, v)

            def _get(frag: str) -> str:
                frag_lower = frag.lower()
                for k, v in dl_data.items():
                    if frag_lower in k.lower():
                        return v
                return ""

            nasc_cpf_raw = _get("data de nascimento")
            parts = [p.strip() for p in nasc_cpf_raw.split(" - ", 1)]
            data_nascimento = parts[0] if len(parts) >= 1 else ""
            cpf = parts[1] if len(parts) >= 2 else ""
        else:
            logger.info("parse_consulta_success: <dl> presente mas vazio")

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

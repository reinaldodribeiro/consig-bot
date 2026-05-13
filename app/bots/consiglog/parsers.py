"""Parsers — DOM extraction for ConsigLog."""
from __future__ import annotations
from typing import TYPE_CHECKING
from loguru import logger
from app.bots.consiglog import selectors as sel
from app.bots.consiglog.schema import ConsigLogMargens

if TYPE_CHECKING:
    from playwright.sync_api import Page


def parse_nome(page: Page) -> str:
    loc = page.locator(sel.NOME_INPUT).first
    if loc.count() == 0:
        return ""
    try:
        return (loc.input_value(timeout=2000) or "").strip()
    except Exception as exc:
        logger.debug("parse_nome erro: {}", exc)
        return ""


def parse_cpf(page: Page) -> str:
    loc = page.locator(sel.CPF_INPUT).first
    if loc.count() == 0:
        return ""
    try:
        raw = (loc.input_value(timeout=2000) or "").strip()
    except Exception as exc:
        logger.debug("parse_cpf erro: {}", exc)
        return ""
    return "".join(ch for ch in raw if ch.isdigit())


def parse_margens(page: Page) -> ConsigLogMargens | None:
    """Lê as linhas tr[id^='body_rptMargens_headerservico_'] e extrai a coluna
    'Margem Disponível' (4ª td) por serviço."""
    try:
        rows = page.evaluate(
            """() => {
                const rs = document.querySelectorAll(
                    "tr[id^='body_rptMargens_headerservico_']"
                );
                return Array.from(rs).map(r => {
                    const cells = r.querySelectorAll('td');
                    return {
                        servico: (cells[0]?.innerText || '').trim().toUpperCase(),
                        disponivel: (cells[3]?.innerText || '').trim(),
                    };
                });
            }"""
        )
    except Exception as exc:
        logger.debug("parse_margens erro: {}", exc)
        return None

    if not rows:
        return None

    def _clean(v: str) -> str:
        # 'R$ 2.123,95\n            Composição...' → 'R$ 2.123,95'
        return (v or "").splitlines()[0].strip()

    margens = ConsigLogMargens()
    for r in rows:
        servico = r.get("servico", "")
        disponivel = _clean(r.get("disponivel", ""))
        if "EMPRÉSTIMO" in servico or "EMPRESTIMO" in servico:
            margens.margem_emprestimo = disponivel
        elif "CARTÃO" in servico or "CARTAO" in servico:
            margens.margem_cartao = disponivel
    logger.debug("parse_margens: empréstimo={} cartão={}",
                 margens.margem_emprestimo, margens.margem_cartao)
    return margens


def parse_erro_consulta(page: Page) -> str | None:
    """Detecta mensagem de erro/aviso. Retorna texto ou None."""
    # Tentativas: span de erro padrão ASP.NET, label de validação, alert
    try:
        for selector in [
            "[id*='lblErro']",
            "[id*='lblMensagem']",
            "[id*='ValidationSummary']",
            ".error, .erro, .msg-erro",
        ]:
            loc = page.locator(selector).first
            if loc.count() > 0:
                txt = (loc.inner_text(timeout=1500) or "").strip()
                if txt:
                    return txt
    except Exception as exc:
        logger.debug("parse_erro_consulta erro: {}", exc)
    return None

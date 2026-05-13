"""Parsers — DOM extraction for BIB Cred."""
from __future__ import annotations
from typing import TYPE_CHECKING
from loguru import logger
from app.bots.bib import selectors as sel
from app.bots.bib.schema import BibContract

if TYPE_CHECKING:
    from playwright.sync_api import Frame, Page


def parse_first_secretaria(page: Page) -> str | None:
    """Retorna value da primeira opção não-vazia do select Secretaria."""
    try:
        return page.evaluate(f"""() => {{
            const s = document.querySelector('{sel.SECRETARIA}');
            if (!s) return null;
            const opt = Array.from(s.options).find(o => o.value.trim());
            return opt ? opt.value : null;
        }}""")
    except Exception as exc:
        logger.debug("parse_first_secretaria erro: {}", exc)
        return None


def parse_client_name(frame: Page | Frame) -> str:
    """Extrai nome do cliente da 2ª célula da tr.normal do popup grid."""
    try:
        return frame.evaluate(f"""() => {{
            const row = document.querySelector('{sel.CLIENT_ROW}');
            if (!row) return '';
            const cells = row.querySelectorAll('td');
            return cells.length >= 2 ? (cells[1].innerText || '').trim() : '';
        }}""") or ""
    except Exception as exc:
        logger.debug("parse_client_name erro: {}", exc)
        return ""


def parse_contracts_table(page: Page) -> list[BibContract]:
    """Extrai contratos do grid grdOperacoes usando tr.normal e seletores [id$=]."""
    try:
        rows = page.evaluate(f"""() => {{
            const rows = document.querySelectorAll('{sel.CONTRACTS_ROWS}');
            return Array.from(rows).map(row => ({{
                contrato: (row.querySelector('[id$="_lblNumeroOperacao"]')?.innerText || '').trim(),
                matricula: (row.querySelector('[id$="_Label2"]')?.innerText || '').trim(),
                taxa_am: (row.querySelector('[id$="_lblTaxaApMes"]')?.innerText || '').trim(),
                qtd_parc_total: (row.querySelector('[id$="_Label3"]')?.innerText || '').trim(),
                qtd_parc_vencidas: (row.querySelector('[id$="_Label4"]')?.innerText || '').trim(),
                qtd_parc_em_aberto: (row.querySelector('[id$="_Label5"]')?.innerText || '').trim(),
                vlr_parcela: (row.querySelector('[id$="_lblValorParcela"]')?.innerText || '').trim(),
                saldo_total: (row.querySelector('[id$="_lblSadoParcela"]')?.innerText || '').trim(),
            }}));
        }}""")
        contracts = [BibContract(**r) for r in (rows or []) if r.get("contrato")]
        logger.debug("parse_contracts_table: {} contratos", len(contracts))
        return contracts
    except Exception as exc:
        logger.debug("parse_contracts_table erro: {}", exc)
        return []

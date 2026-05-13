"""Parsers — DOM extraction for Valor Financiamentos."""
from __future__ import annotations

from typing import TYPE_CHECKING

from loguru import logger

from app.bots.valor import selectors as sel
from app.bots.valor.schema import ValorContract

if TYPE_CHECKING:
    from playwright.sync_api import Frame, Page


def parse_contracts_table(page: Page | Frame) -> list[ValorContract]:
    """Extrai contratos usando os IDs de célula do JTPlatinumGrid2."""
    table = page.locator(sel.CONTRACTS_TABLE).first
    if table.count() == 0:
        logger.debug("parse_contracts_table: tabela ausente")
        return []

    def _cell(row: int, col: int) -> str:
        loc = page.locator(f"#JTPlatinumGrid2_cell_{row}_{col}").first
        return loc.inner_text().strip() if loc.count() > 0 else ""

    contracts: list[ValorContract] = []
    i = 0
    while True:
        contrato = _cell(i, 0)
        if not contrato:
            break
        # col: 0=Contrato, 1=Data Crédito, 2=Data Término, 3=Vl. Crédito,
        #       4=Parcelas, 5=Status, 6=Convênio, 7=Banco
        contracts.append(ValorContract(
            contrato=contrato,
            parcelas=_cell(i, 4),
            status=_cell(i, 5).upper(),
            convenio=_cell(i, 6),
            table_row=i,
        ))
        i += 1

    logger.debug("parse_contracts_table: {} contratos extraídos", len(contracts))
    return contracts


def parse_first_due_date(frame: Page | Frame) -> str | None:
    """Extrai vencimento da parcela NDoc=1 do frame parcelas.php (após JS carregar).

    Estrutura: #pn_parcelas_table_detail > tr[id^="cronograma_"] > td > div.linha
    div[0]=Contrato, div[1]=NDoc, div[2]=Vencimento
    """
    try:
        result = frame.evaluate("""() => {
            const rows = document.querySelectorAll(
                '#pn_parcelas_table_detail tr[id^="cronograma_"]'
            );
            for (const row of rows) {
                const divs = row.querySelectorAll('td > div.linha > div');
                if (divs.length < 3) continue;
                const ndoc = (divs[1].textContent || '').trim();
                if (ndoc !== '1') continue;
                const venc = (divs[2].textContent || '').trim();
                if (/\\d{2}\\/\\d{2}\\/\\d{4}/.test(venc)) return venc;
            }
            return null;
        }""")
        logger.debug("parse_first_due_date: {}", result)
        return result or None
    except Exception as exc:
        logger.debug("parse_first_due_date erro: {}", exc)
        return None


def parse_error_toast(page: Page | Frame) -> str | None:
    """Return visible toast/alert/error text, or None."""
    locator = page.locator(sel.ERROR_TOAST)
    n = locator.count()
    if n == 0:
        return None
    for i in range(n):
        try:
            if not locator.nth(i).is_visible(timeout=200):
                continue
            text = locator.nth(i).inner_text().strip()
            if text:
                return text
        except Exception:
            continue
    return None

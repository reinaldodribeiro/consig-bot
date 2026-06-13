"""Parsers — DOM extraction for Valor Financiamentos."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

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


_PARSE_JS = r"""() => {
    const table = document.querySelector('#dbrp_parcelas_table_detail');
    if (!table) {
        const candidates = Array.from(document.querySelectorAll(
            '[id*="parcelas"], [id*="dbrp"]'
        )).map(el => ({ id: el.id, tag: el.tagName, rows: el.querySelectorAll('tr').length }));
        const iframes = Array.from(document.querySelectorAll('iframe')).map(f => ({
            id: f.id, name: f.name, src: (f.src || '').slice(0, 120),
        }));
        return { table_found: false, candidates: candidates, iframes: iframes };
    }
    // A tabela usa tabelas aninhadas + filler rows. Cada parcela aparece
    // como múltiplas <tr>, sendo apenas UMA delas a "clean row" com formato:
    //   ['', contrato, '', status, '', dd/mm/yyyy, '', ndoc, '', '', valor, ...]
    // Filtramos por esse padrão: cells[1]=numérico, cells[5]=data, cells[7]=ndoc.
    const trs = table.querySelectorAll('tr');
    const dateRe = /^\d{2}\/\d{2}\/\d{4}$/;
    const intRe = /^\d+$/;
    const groups = {};
    let clean_rows = 0;
    for (const row of trs) {
        const tds = row.querySelectorAll('td');
        if (tds.length < 8) continue;
        const cells = [];
        for (const td of tds) cells.push((td.textContent || '').trim());
        const contrato = cells[1];
        const status = cells[3] || '';
        const venc = cells[5] || '';
        const ndocStr = cells[7] || '';
        if (!intRe.test(contrato)) continue;
        if (!dateRe.test(venc)) continue;
        if (!intRe.test(ndocStr)) continue;
        clean_rows += 1;
        const ndoc = parseInt(ndocStr, 10);
        if (!groups[contrato]) {
            groups[contrato] = { first_venc: null, min_ndoc: null, count: 0, status: status };
        }
        const g = groups[contrato];
        g.count += 1;
        if (g.min_ndoc === null || ndoc < g.min_ndoc) {
            g.min_ndoc = ndoc;
            g.first_venc = venc;
        }
    }
    return {
        table_found: true,
        total_rows: trs.length,
        clean_rows: clean_rows,
        groups: groups,
    };
}"""


def _eval_in_frame(target: Page | Frame) -> dict[str, Any] | None:
    """Roda o JS de parse em um frame; devolve None em caso de erro."""
    try:
        result = target.evaluate(_PARSE_JS)
        return result if isinstance(result, dict) else None
    except Exception as exc:
        logger.debug("_eval_in_frame erro: {}", exc)
        return None


def parse_parcelas_aggregated(page_or_frame: Page | Frame) -> dict[str, tuple[str | None, int]]:
    """Procura `#dbrp_parcelas_table_detail` em TODOS os frames da página, agrupa por contrato.

    Estrutura esperada da row: `td > div.linha > div` (fallback: texto direto de `td`)
    com `div[0]=Contrato, div[1]=NDoc, div[2]=Vencimento`.

    Retorna `{contrato: (primeira_data_vencimento, total_parcelas)}`.
    """
    # Resolve a lista de frames a inspecionar: começa pelo frame recebido,
    # depois cobre todos os frames da página (rbmcont pode ter sub-iframes).
    targets: list[Page | Frame] = [page_or_frame]
    page = getattr(page_or_frame, "page", None) or page_or_frame
    try:
        # Page expõe .frames (lista). Frame também expõe .page.frames.
        all_frames = getattr(page, "frames", None) or []
        for f in all_frames:
            if f is not page_or_frame:
                targets.append(f)
    except Exception as exc:
        logger.debug("parse_parcelas_aggregated: falha listando frames: {}", exc)

    payload: dict[str, Any] | None = None
    matched_frame_label = "<desconhecido>"
    for i, t in enumerate(targets):
        label = _describe_target(t, i)
        result = _eval_in_frame(t)
        if result is None:
            logger.debug("parse_parcelas_aggregated: frame {} sem JS executável", label)
            continue
        if result.get("table_found"):
            payload = result
            matched_frame_label = label
            break
        # Não achou — loga candidatos e iframes daquele frame
        logger.info(
            "parse_parcelas_aggregated: frame {} sem #dbrp_parcelas_table_detail. "
            "Candidatos id-parcial={} | iframes-filhos={}",
            label,
            result.get("candidates"),
            result.get("iframes"),
        )

    if payload is None:
        logger.warning("parse_parcelas_aggregated: tabela não encontrada em nenhum frame")
        return {}

    total_rows = int(payload.get("total_rows") or 0)
    clean_rows = int(payload.get("clean_rows") or 0)
    groups = payload.get("groups") or {}

    logger.info(
        "parse_parcelas_aggregated: tabela em '{}' | {} <tr> totais, {} clean rows, {} contratos",
        matched_frame_label, total_rows, clean_rows, len(groups),
    )
    for contrato, info in groups.items():
        if not isinstance(info, dict):
            continue
        logger.info(
            "  contrato {} | parcelas={} | primeiro_venc={} (NDoc {}) | status={}",
            contrato,
            info.get("count"),
            info.get("first_venc"),
            info.get("min_ndoc"),
            info.get("status"),
        )

    result: dict[str, tuple[str | None, int]] = {}
    for contrato, info in groups.items():
        if not isinstance(info, dict):
            continue
        first_venc = info.get("first_venc")
        count = int(info.get("count") or 0)
        result[str(contrato)] = (first_venc or None, count)
    return result


def _describe_target(target: Page | Frame, idx: int) -> str:
    name = getattr(target, "name", None)
    url = ""
    try:
        url = getattr(target, "url", "") or ""
    except Exception:
        pass
    return f"[{idx}] name={name!r} url={url[:80]!r}"


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

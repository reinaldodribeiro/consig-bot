"""BibBot — BIB Cred automation."""
from __future__ import annotations

import contextlib
from typing import Any, ClassVar

from loguru import logger

from app.bots.bib import parsers, selectors as sel
from app.bots.bib.schema import BibInputRow, BibResult
from app.core.base_bot import BaseBot
from app.core.browser import BrowserSession
from app.core.exceptions import AuthenticationError, NotFoundError, ParseError
from app.core.registry import register_bot
from app.utils.cpf import mask_cpf
from app.utils.dates import now_str

_LOGIN_URL_DEFAULT = "https://www.bibcred.com.br/Funcao.WebAutorizador/Login/AC.UI.LOGIN.aspx"
_PROPOSTA_URL_DEFAULT = "https://www.bibcred.com.br/Funcao.WebAutorizador/MenuWeb/Cadastro/Proposta/UI.PropostaSintetizada.aspx?Origem3=007374"


@register_bot
class BibBot(BaseBot):
    key: ClassVar[str] = "bib"
    display_name: ClassVar[str] = "BIB Cred"
    InputRowModel: ClassVar[type[BibInputRow]] = BibInputRow
    ResultModel: ClassVar[type[BibResult]] = BibResult

    def __init__(self, config) -> None:
        super().__init__(config)
        extras = self.system.extras or {}
        self._login_url: str = extras.get("login_url", _LOGIN_URL_DEFAULT)
        self._proposta_url: str = extras.get("proposta_url", _PROPOSTA_URL_DEFAULT)
        self._tipo_operacao: str = extras.get("tipo_operacao", "Refinanciamento")
        self._grupo_convenio: str = extras.get("grupo_convenio", "3")
        self._conveniada: str = extras.get("conveniada", "000086")
        self._secretaria: str | None = extras.get("secretaria", None)
        self._form_ready: bool = False

    def authenticate(self, session: BrowserSession) -> None:
        page = session.page
        page.goto(self._login_url, wait_until="domcontentloaded")
        with contextlib.suppress(Exception):
            page.wait_for_load_state("networkidle", timeout=10_000)

        if not self._needs_login(page):
            logger.info("BIB: sessão já ativa")
            return

        logger.info("BIB: preenchendo credenciais")
        logger.debug("BIB: clicando campo usuário ({})", sel.LOGIN_USER)
        page.click(sel.LOGIN_USER)
        logger.debug("BIB: digitando usuário")
        page.keyboard.type(self.system.auth.email.upper())
        logger.debug("BIB: clicando campo senha ({})", sel.LOGIN_PASS)
        page.click(sel.LOGIN_PASS)
        logger.debug("BIB: digitando senha")
        page.keyboard.type(self.system.auth.password.get_secret_value())
        logger.debug("BIB: campos preenchidos, registrando handler de dialog")

        alert_message: list[str] = []

        def _capture_dialog(dialog) -> None:
            alert_message.append(dialog.message)
            dialog.accept()

        page.once("dialog", _capture_dialog)
        logger.debug("BIB: submetendo formulário via prototype nativo")
        # HTMLFormElement.prototype.submit bypassa sobrescrita JS do form.submit
        with contextlib.suppress(Exception):
            with page.expect_navigation(wait_until="domcontentloaded", timeout=15_000):
                page.evaluate("""() => {
                    const form = document.forms[0];
                    form.__EVENTTARGET.value = 'lnkEntrar';
                    form.__EVENTARGUMENT.value = '';
                    HTMLFormElement.prototype.submit.call(form);
                }""")
        logger.debug("BIB: aguardando networkidle pós-submit")
        with contextlib.suppress(Exception):
            page.wait_for_load_state("networkidle", timeout=15_000)
        logger.debug("BIB: URL pós-login: {}", page.url)

        if alert_message:
            msg = alert_message[0]
            # Aviso de expiração de senha NÃO é rejeição — o login completou,
            # o site só está alertando que a senha vai expirar em N dias.
            if "expira" in msg.lower():
                logger.warning("BIB: aviso ignorado (login OK): {}", msg)
            else:
                raise AuthenticationError(f"BIB recusou o login: {msg}")

        if self._needs_login(page):
            raise AuthenticationError(
                f"Login BIB não confirmado. URL atual: {page.url}"
            )
        logger.info("BIB: autenticado")

    def process_row(self, session: BrowserSession, row: BibInputRow) -> BibResult:  # type: ignore[override]
        page = session.page
        cpf_masked = mask_cpf(row.cpf)
        logger.info("BIB: consultando linha {} ({})", row.row_index, cpf_masked)

        if not row.cpf or len(row.cpf) != 11:
            return self._error_result(row, "erro", f"CPF inválido: {row.cpf!r}")

        if not self._form_ready:
            # 1. Navegar para proposta e preencher selects em cascata (apenas na 1ª vez)
            page.goto(self._proposta_url, wait_until="domcontentloaded")
            with contextlib.suppress(Exception):
                page.wait_for_load_state("networkidle", timeout=15_000)
            self._fill_form_setup(page)
            self._form_ready = True
            logger.debug("BIB: formulário inicializado")
        else:
            logger.debug("BIB: reutilizando formulário já inicializado")

        # 3. Preencher CPF (formato mascarado) e disparar postback
        cpf_fmt = f"{row.cpf[:3]}.{row.cpf[3:6]}.{row.cpf[6:9]}-{row.cpf[9:11]}"
        cpf_alert: list[str] = []

        def _capture_cpf_dialog(dialog) -> None:
            cpf_alert.append(dialog.message)
            logger.warning("BIB: alerta após CPF {}: {}", cpf_masked, dialog.message)
            dialog.accept()

        page.once("dialog", _capture_cpf_dialog)
        page.fill(sel.CPF_INPUT, cpf_fmt)
        page.keyboard.press("Tab")
        with contextlib.suppress(Exception):
            page.wait_for_load_state("networkidle", timeout=15_000)

        # 4. Lidar com popup de cliente
        try:
            nome = self._handle_client_popup(page, row)
        except NotFoundError:
            raise
        except Exception as exc:
            raise ParseError(f"Erro no popup de cliente: {exc}") from exc

        # 5. Clicar em Atualizar Lista de Contratos
        try:
            page.wait_for_selector(sel.BTN_ATUALIZAR, state="visible", timeout=15_000)
            page.click(sel.BTN_ATUALIZAR)
            with contextlib.suppress(Exception):
                page.wait_for_load_state("networkidle", timeout=15_000)
        except Exception as exc:
            raise ParseError(f"Botão 'Atualizar Lista de Contratos' não encontrado: {exc}") from exc

        # 6. Extrair contratos
        contracts = parsers.parse_contracts_table(page)
        logger.info("BIB: linha {} — {} contratos", row.row_index, len(contracts))

        observacao = "" if contracts else "Contrato não encontrado"
        status: Any = "ok" if contracts else "nao_encontrado"

        return BibResult(
            row_index=row.row_index,
            cpf=row.cpf,
            nome=nome,
            contracts=contracts,
            status_consulta=status,
            observacao=observacao,
            data_consulta=now_str(),
        )

    def output_columns(self) -> list[str]:
        return [
            "CPF", "Nome", "Contrato", "Matrícula", "Taxa a.m.",
            "Qtd.Parc. Total", "Qtd.Parc. Vencidas", "Qtd.Parc. Em Aberto",
            "Vlr.Parc.", "Saldo Total", "Status Consulta", "Observação", "Data Consulta",
        ]

    def center_columns(self) -> list[str]:
        return [
            "Contrato", "Matrícula", "Taxa a.m.",
            "Qtd.Parc. Total", "Qtd.Parc. Vencidas", "Qtd.Parc. Em Aberto",
            "Vlr.Parc.", "Saldo Total",
        ]

    def expand_result(self, result: BibResult) -> list[dict[str, Any]]:  # type: ignore[override]
        base = {
            "CPF": result.cpf, "Nome": result.nome,
            "Status Consulta": result.status_consulta,
            "Observação": result.observacao, "Data Consulta": result.data_consulta,
        }
        if not result.contracts:
            return [{**base, "Contrato": "", "Matrícula": "", "Taxa a.m.": "",
                     "Qtd.Parc. Total": "", "Qtd.Parc. Vencidas": "",
                     "Qtd.Parc. Em Aberto": "", "Vlr.Parc.": "", "Saldo Total": ""}]
        return [{
            **base,
            "Contrato": c.contrato, "Matrícula": c.matricula, "Taxa a.m.": c.taxa_am,
            "Qtd.Parc. Total": c.qtd_parc_total, "Qtd.Parc. Vencidas": c.qtd_parc_vencidas,
            "Qtd.Parc. Em Aberto": c.qtd_parc_em_aberto,
            "Vlr.Parc.": c.vlr_parcela, "Saldo Total": c.saldo_total,
        } for c in result.contracts]

    # ---- helpers -----------------------------------------------------------

    def _needs_login(self, page) -> bool:
        url = page.url.lower()
        return "login" in url or page.locator(sel.LOGIN_BTN).count() > 0

    def _fill_form_setup(self, page) -> None:
        """Preenche os 4 selects em cascata (cada um dispara postback ASP.NET)."""
        page.select_option(sel.TIPO_OPERACAO, self._tipo_operacao)
        with contextlib.suppress(Exception):
            page.wait_for_load_state("networkidle", timeout=12_000)

        page.select_option(sel.GRUPO_CONVENIO, self._grupo_convenio)
        with contextlib.suppress(Exception):
            page.wait_for_load_state("networkidle", timeout=12_000)

        page.select_option(sel.CONVENIADA, self._conveniada)
        with contextlib.suppress(Exception):
            page.wait_for_load_state("networkidle", timeout=12_000)

        # Aguarda Secretaria ter opções carregadas (postback em cascata popula o select)
        with contextlib.suppress(Exception):
            page.wait_for_function(
                f"""() => {{
                    const s = document.querySelector('{sel.SECRETARIA}');
                    return s && Array.from(s.options).some(o => o.value.trim());
                }}""",
                timeout=12_000,
            )
        secretaria = self._secretaria or parsers.parse_first_secretaria(page)
        if secretaria:
            page.select_option(sel.SECRETARIA, secretaria)
            with contextlib.suppress(Exception):
                page.wait_for_load_state("networkidle", timeout=12_000)
        else:
            logger.warning("BIB: select Secretaria sem opções após aguardar")

    def _handle_client_popup(self, page, row: BibInputRow) -> str:
        """Aguarda popup iframe, extrai nome, clica no link do cliente."""
        try:
            page.wait_for_selector(sel.POPUP_FRAME_SEL, state="visible", timeout=4_000)
        except Exception:
            raise NotFoundError(f"Popup não apareceu em 4s — CPF não encontrado: {mask_cpf(row.cpf)}")
        popup_frame = page.frame(name=sel.POPUP_FRAME_ID)

        if popup_frame is not None:
            with contextlib.suppress(Exception):
                popup_frame.wait_for_load_state("networkidle", timeout=10_000)
            popup_frame.wait_for_selector(sel.CLIENT_GRID, state="visible", timeout=12_000)

            if popup_frame.locator(sel.CLIENT_ROW).count() == 0:
                raise NotFoundError(f"Cliente não encontrado para CPF {mask_cpf(row.cpf)}")

            nome = parsers.parse_client_name(popup_frame)
            page.once("dialog", lambda d: d.accept())
            # click() trava aguardando navegação do iframe que nunca acontece (UpdatePanel)
            # — usar evaluate + HTMLFormElement.prototype.submit nativo
            popup_frame.evaluate("""() => {
                const link = document.querySelector(
                    '#ctl00_cph_FIJanela1_FIJanelaPanel1_grvHomo tr.normal td:first-child a'
                );
                if (!link) return;
                const m = (link.getAttribute('href') || '').match(/__doPostBack\\(['"]([^'"]+)['"]/);
                if (m) {
                    const form = document.forms[0];
                    form.__EVENTTARGET.value = m[1];
                    form.__EVENTARGUMENT.value = '';
                    HTMLFormElement.prototype.submit.call(form);
                }
            }""")
        else:
            # FrameLocator fallback
            fl = page.frame_locator(sel.POPUP_FRAME_SEL)
            fl.locator(sel.CLIENT_GRID).wait_for(state="visible", timeout=12_000)
            if fl.locator(sel.CLIENT_ROW).count() == 0:
                raise NotFoundError(f"Cliente não encontrado para CPF {mask_cpf(row.cpf)}")
            nome = fl.locator(f"{sel.CLIENT_ROW} td:nth-child(2)").first.inner_text().strip()
            page.once("dialog", lambda d: d.accept())
            fl.locator(sel.CLIENT_LINK).first.evaluate("""el => {
                const m = (el.getAttribute('href') || '').match(/__doPostBack\\(['"]([^'"]+)['"]/);
                if (m) {
                    const form = document.forms[0];
                    form.__EVENTTARGET.value = m[1];
                    form.__EVENTARGUMENT.value = '';
                    HTMLFormElement.prototype.submit.call(form);
                }
            }""")

        with contextlib.suppress(Exception):
            page.wait_for_load_state("networkidle", timeout=15_000)
        return nome

    def _error_result(self, row: BibInputRow, status: str, observacao: str) -> BibResult:
        return BibResult(
            row_index=row.row_index, cpf=row.cpf, nome=row.nome,
            contracts=[], status_consulta=status,  # type: ignore[arg-type]
            observacao=observacao, data_consulta=now_str(),
        )

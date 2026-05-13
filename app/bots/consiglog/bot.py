"""ConsigLogBot — ConsigLog automation (saec.consiglog.com.br)."""
from __future__ import annotations

import contextlib
import time
from typing import Any, ClassVar

from loguru import logger

from app.bots.consiglog import parsers, selectors as sel
from app.bots.consiglog.schema import ConsigLogInputRow, ConsigLogResult
from app.core.base_bot import BaseBot
from app.core.browser import BrowserSession
from app.core.exceptions import AuthenticationError, NotFoundError, ParseError, SessionExpired
from app.core.registry import register_bot
from app.utils.dates import now_filename_ts, now_str
from app.utils.paths import ensure_dir, get_app_root


_LOGIN_URL_DEFAULT = "https://saec.consiglog.com.br/Login.aspx"
_SELECAO_URL_DEFAULT = "https://saec.consiglog.com.br/LoginSelecao.aspx"
_CONSULTA_URL_DEFAULT = "https://saec.consiglog.com.br/Margem/ConsultaMargem.aspx"
_CONVENIO_LABEL_DEFAULT = "PREFEITURA GOIÂNIA"


@register_bot
class ConsigLogBot(BaseBot):
    key: ClassVar[str] = "consiglog"
    display_name: ClassVar[str] = "ConsigLog"
    InputRowModel: ClassVar[type[ConsigLogInputRow]] = ConsigLogInputRow
    ResultModel: ClassVar[type[ConsigLogResult]] = ConsigLogResult

    def __init__(self, config) -> None:
        super().__init__(config)
        extras = self.system.extras or {}
        self._login_url: str = extras.get("login_url", _LOGIN_URL_DEFAULT)
        self._selecao_url: str = extras.get("selecao_url", _SELECAO_URL_DEFAULT)
        self._consulta_url: str = extras.get("consulta_url", _CONSULTA_URL_DEFAULT)
        self._convenio_label: str = extras.get("convenio_label", _CONVENIO_LABEL_DEFAULT).upper()

    # ---- BaseBot interface --------------------------------------------------

    def authenticate(self, session: BrowserSession) -> None:
        page = session.page
        logger.info("ConsigLog: navegando para login ({})", self._login_url)
        self._safe_goto(page, self._login_url)

        # Se já estiver na seleção de convênio, sessão ativa
        if self._is_on_selecao(page):
            logger.info("ConsigLog: sessão ativa — pulando login")
        elif self._needs_login(page):
            self._do_login(page)
        else:
            logger.info("ConsigLog: já autenticado (sem form de login nem seleção)")

        # Resolver seleção de convênio se aplicável (o site navega sozinho após o clique)
        if self._is_on_selecao(page):
            self._select_convenio(page)

        # Aguarda a navegação pós-login/seleção assentar antes de qualquer verificação.
        # NÃO forçar goto aqui — o ASP.NET pode estar no meio de um postback,
        # e um goto concorrente dispara net::ERR_ABORTED.
        with contextlib.suppress(Exception):
            page.wait_for_load_state("load", timeout=15_000)
        with contextlib.suppress(Exception):
            page.wait_for_load_state("networkidle", timeout=10_000)

        # Popup pode aparecer em qualquer momento pós-login
        self._handle_popup_confirmacao(page)

        if self._needs_login(page) or self._is_on_selecao(page):
            art = self._save_failure_artifacts(page, label="auth_failed")
            lines = [
                "ConsigLog: login não confirmado após sequência completa.",
                f"URL: {art.get('url', '?')}",
            ]
            if art.get("body_snippet"):
                lines.append(f"\nTexto da página:\n{art['body_snippet']}")
            if "screenshot" in art:
                lines.append(f"\nScreenshot: {art['screenshot']}")
            if "html" in art:
                lines.append(f"HTML: {art['html']}")
            raise AuthenticationError("\n".join(lines))
        logger.info("ConsigLog: autenticado (URL atual: {})", page.url)

    def process_row(self, session: BrowserSession, row: ConsigLogInputRow) -> ConsigLogResult:  # type: ignore[override]
        page = session.page
        matricula = row.matricula
        logger.info("ConsigLog: consultando linha {} (matrícula={})", row.row_index, matricula)

        if not matricula:
            return self._error_result(row, "erro", "Matrícula vazia")

        # Garante que estamos na página de consulta
        if self._consulta_url.split("?")[0].lower() not in page.url.lower():
            self._safe_goto(page, self._consulta_url)

        if self._needs_login(page) or self._is_on_selecao(page):
            raise SessionExpired("ConsigLog: redirecionado para login/seleção durante consulta")

        # Aguarda input de matrícula visível
        try:
            page.wait_for_selector(sel.MATRICULA_INPUT, state="visible", timeout=10_000)
        except Exception as exc:
            raise ParseError(f"ConsigLog: campo matrícula não apareceu: {exc}") from exc

        # Preenche, dispara onblur (Tab) para adicionar zeros, depois clica Pesquisar
        page.fill(sel.MATRICULA_INPUT, matricula)
        page.locator(sel.MATRICULA_INPUT).press("Tab")
        with contextlib.suppress(Exception):
            page.wait_for_load_state("networkidle", timeout=5_000)

        page.click(sel.PESQUISAR_BTN)
        with contextlib.suppress(Exception):
            page.wait_for_load_state("networkidle", timeout=15_000)

        # Popup "CPF/Matrícula não encontrado" — dismiss + NotFoundError
        popup_msg = self._handle_popup_resultado(page)
        if popup_msg:
            raise NotFoundError(popup_msg)

        # Detecta erro (label/span fora de popup)
        erro = parsers.parse_erro_consulta(page)
        if erro:
            raise NotFoundError(erro)

        # Aguarda campo nome ter valor (postback completou)
        try:
            page.wait_for_function(
                f"() => {{ const el = document.querySelector('{sel.NOME_INPUT}'); return el && el.value && el.value.trim().length > 0; }}",
                timeout=10_000,
            )
        except Exception:
            # Sem nome após pesquisar → matrícula não encontrada
            raise NotFoundError(f"Matrícula {matricula} não retornou resultado")

        nome = parsers.parse_nome(page)
        cpf = parsers.parse_cpf(page)
        margens = parsers.parse_margens(page)

        return ConsigLogResult(
            row_index=row.row_index,
            matricula=matricula,
            nome=nome,
            cpf=cpf,
            margens=margens,
            status_consulta="ok",
            observacao="" if margens else "Tabela de margens não encontrada",
            data_consulta=now_str(),
        )

    def output_columns(self) -> list[str]:
        return [
            "Matrícula", "Nome", "CPF",
            "Margem Empréstimo", "Margem Cartão",
            "Status Consulta", "Observação", "Data Consulta",
        ]

    def center_columns(self) -> list[str]:
        return ["Matrícula", "CPF", "Margem Empréstimo", "Margem Cartão"]

    def expand_result(self, result: ConsigLogResult) -> list[dict[str, Any]]:  # type: ignore[override]
        m = result.margens
        return [{
            "Matrícula":         result.matricula,
            "Nome":              result.nome,
            "CPF":               result.cpf,
            "Margem Empréstimo": m.margem_emprestimo if m else "",
            "Margem Cartão":     m.margem_cartao if m else "",
            "Status Consulta":   result.status_consulta,
            "Observação":        result.observacao,
            "Data Consulta":     result.data_consulta,
        }]

    # ---- helpers -------------------------------------------------------------

    def _safe_goto(self, page, url: str) -> None:
        """goto tolerante a postbacks ASP.NET em curso.

        Antes do goto, aguarda qualquer navegação em andamento assentar. Em caso
        de net::ERR_ABORTED (postback concorrente), retenta uma vez após pausa.
        """
        with contextlib.suppress(Exception):
            page.wait_for_load_state("load", timeout=10_000)
        with contextlib.suppress(Exception):
            page.wait_for_load_state("networkidle", timeout=5_000)

        try:
            page.goto(url, wait_until="domcontentloaded")
        except Exception as exc:
            msg = str(exc)
            if "ERR_ABORTED" not in msg and "frame was detached" not in msg.lower():
                raise
            logger.debug("ConsigLog: goto abortado ({}) — retentando após settle", msg.splitlines()[0])
            with contextlib.suppress(Exception):
                page.wait_for_load_state("load", timeout=10_000)
            with contextlib.suppress(Exception):
                page.wait_for_load_state("networkidle", timeout=5_000)
            page.goto(url, wait_until="domcontentloaded")

        with contextlib.suppress(Exception):
            page.wait_for_load_state("networkidle", timeout=10_000)

    def _needs_login(self, page) -> bool:
        url = page.url.lower()
        if "login.aspx" in url and "loginselecao" not in url:
            return True
        return page.locator(sel.LOGIN_USER).count() > 0

    def _is_on_selecao(self, page) -> bool:
        if "loginselecao" in page.url.lower():
            return True
        return page.locator(sel.CONVENIO_TABLE).count() > 0

    def _do_login(self, page) -> None:
        logger.info("ConsigLog: preenchendo usuário")
        page.wait_for_selector(sel.LOGIN_USER, state="visible", timeout=10_000)
        page.fill(sel.LOGIN_USER, self.system.auth.email)
        try:
            with page.expect_navigation(wait_until="domcontentloaded", timeout=15_000):
                page.click(sel.LOGIN_NEXT)
        except Exception as exc:
            logger.debug("ConsigLog: expect_navigation pós-Próxima falhou ({}) — seguindo", exc)
        with contextlib.suppress(Exception):
            page.wait_for_load_state("networkidle", timeout=10_000)
        logger.debug("ConsigLog: URL pós-Próxima: {}", page.url)

        # Senha + Entrar
        logger.info("ConsigLog: preenchendo senha")
        try:
            page.wait_for_selector(sel.LOGIN_PASS, state="visible", timeout=10_000)
        except Exception as exc:
            raise AuthenticationError(f"Campo de senha não apareceu: {exc}") from exc
        page.fill(sel.LOGIN_PASS, self.system.auth.password.get_secret_value())

        initial_url = page.url
        logger.info("ConsigLog: clicando Entrar (DOM click)")
        # DOM click direto bypassa actionability check do playwright e overlays.
        # O button id="Entrar" é submit type, então .click() dispara form submission.
        try:
            page.evaluate("document.getElementById('Entrar').click()")
        except Exception as exc:
            raise AuthenticationError(f"Falha ao disparar click Entrar: {exc}") from exc

        # Aguarda mudança real: navegação OU popup visível, com poll de 100ms
        deadline = time.monotonic() + 15.0
        outcome = "timeout"
        while time.monotonic() < deadline:
            if page.url != initial_url:
                outcome = "nav"
                break
            try:
                if page.evaluate(
                    "(() => { const lbl = document.getElementById"
                    "('ucAjaxModalPopupConfirmacao1_lblMensagemPopup');"
                    " if (!lbl) return false;"
                    " return (lbl.innerText || lbl.textContent || '').trim().length > 0; })()"
                ):
                    outcome = "popup"
                    break
            except Exception:
                pass
            time.sleep(0.1)
        logger.debug("ConsigLog: pós-Entrar outcome={}, URL={}", outcome, page.url)

        with contextlib.suppress(Exception):
            page.wait_for_load_state("networkidle", timeout=10_000)

        # Se o popup "usuário já logado" aparecer, clica Confirmar
        self._handle_popup_confirmacao(page)

    def _select_convenio(self, page) -> None:
        logger.info("ConsigLog: selecionando convênio '{}'", self._convenio_label)
        try:
            page.wait_for_selector(sel.CONVENIO_TABLE, state="visible", timeout=10_000)
        except Exception:
            logger.info("ConsigLog: tabela de convênio ausente — provavelmente já selecionado")
            return

        xpath = sel.convenio_button_xpath(self._convenio_label)
        loc = page.locator(xpath)
        if loc.count() == 0:
            raise AuthenticationError(
                f"Convênio '{self._convenio_label}' não encontrado na lista do ConsigLog."
            )
        loc.first.click()
        with contextlib.suppress(Exception):
            page.wait_for_load_state("networkidle", timeout=15_000)

    def _handle_popup_confirmacao(self, page) -> bool:
        """Trata modal 'Usuário já logado'. Retorna True se o popup foi tratado.

        Detecção: o label de mensagem do popup é populado pelo servidor SOMENTE
        quando o popup está aberto. Vazio = fechado, com texto = aberto. Mais
        confiável que checar display/rect (o foregroundElement tem layout
        estranho que faz getBoundingClientRect retornar 0).
        """
        try:
            popup_msg = page.evaluate(
                """() => {
                    const lbl = document.getElementById(
                        'ucAjaxModalPopupConfirmacao1_lblMensagemPopup'
                    );
                    if (!lbl) return '';
                    return (lbl.innerText || lbl.textContent || '').trim();
                }"""
            )
        except Exception as exc:
            logger.debug("ConsigLog: erro checando popup: {}", exc)
            popup_msg = ""

        if not popup_msg:
            logger.debug("ConsigLog: popup confirmacao NÃO está aberto — pulando")
            return False

        logger.info("ConsigLog: popup ABERTO ({!r}) — submetendo Confirmar", popup_msg[:80])
        # Injeta hidden input com name/value do botão e submete o form via
        # HTMLFormElement.prototype.submit. O .click() do JS no submit dentro
        # do modal AjaxControlToolkit não dispara form submission; essa
        # abordagem força o postback corretamente.
        btn_name = "ucAjaxModalPopupConfirmacao1$btnConfirmarPopup"
        submit_js = f"""() => {{
            const form = document.forms[0];
            if (!form) return false;
            let inp = form.querySelector(
                'input[type="hidden"][name="{btn_name}"]'
            );
            if (!inp) {{
                inp = document.createElement('input');
                inp.type = 'hidden';
                inp.name = '{btn_name}';
                form.appendChild(inp);
            }}
            inp.value = 'Confirmar';
            HTMLFormElement.prototype.submit.call(form);
            return true;
        }}"""
        try:
            # expect_navigation captura a navegação async disparada por submit()
            with page.expect_navigation(wait_until="domcontentloaded", timeout=20_000):
                page.evaluate(submit_js)
        except Exception as exc:
            logger.warning("ConsigLog: navegação pós-Confirmar não detectada: {}", exc)
        with contextlib.suppress(Exception):
            page.wait_for_load_state("networkidle", timeout=10_000)
        logger.info("ConsigLog: URL pós-Confirmar popup: {}", page.url)
        return True

    def _handle_popup_resultado(self, page) -> str | None:
        """Trata popup de resultado/erro da consulta (ex: 'CPF/Matrícula não encontrado').

        Lê a mensagem, clica OK para fechar, e retorna o texto. Retorna None se
        não houver popup visível.
        """
        loc = page.locator(sel.POPUP_RESULTADO_PANEL).first
        if loc.count() == 0:
            return None
        try:
            if not loc.is_visible(timeout=1000):
                return None
        except Exception:
            return None

        msg = ""
        try:
            msg_loc = page.locator(sel.POPUP_RESULTADO_MSG).first
            if msg_loc.count() > 0:
                msg = (msg_loc.inner_text(timeout=1500) or "").strip()
        except Exception:
            msg = ""

        logger.info("ConsigLog: popup de resultado detectado: {}", msg or "(sem texto)")
        btn_name = "ctl00$body$ucAjaxModalPopup1$btnConfirmarPopup"
        submit_js = f"""() => {{
            const form = document.forms[0];
            if (!form) return false;
            let inp = form.querySelector(
                'input[type="hidden"][name="{btn_name}"]'
            );
            if (!inp) {{
                inp = document.createElement('input');
                inp.type = 'hidden';
                inp.name = '{btn_name}';
                form.appendChild(inp);
            }}
            inp.value = 'OK';
            HTMLFormElement.prototype.submit.call(form);
            return true;
        }}"""
        try:
            with page.expect_navigation(wait_until="domcontentloaded", timeout=15_000):
                page.evaluate(submit_js)
        except Exception as exc:
            logger.debug("ConsigLog: navegação pós-OK não detectada: {}", exc)
        with contextlib.suppress(Exception):
            page.wait_for_load_state("networkidle", timeout=10_000)
        return msg or "Resultado não encontrado"

    def _save_failure_artifacts(self, page, label: str = "failure") -> dict[str, str]:
        """Captura URL + texto do body sempre; screenshot + HTML apenas em debug."""
        artifacts: dict[str, str] = {"url": page.url}
        try:
            text = page.locator("body").inner_text(timeout=1500).strip()
            artifacts["body_snippet"] = text[:600] + ("..." if len(text) > 600 else "")
        except Exception:
            artifacts["body_snippet"] = ""

        if not self.config.bot.debug:
            return artifacts

        out_dir = ensure_dir(get_app_root() / "checkpoint" / "screenshots" / self.key)
        ts = now_filename_ts()
        try:
            shot = out_dir / f"{label}_{ts}.png"
            page.screenshot(path=str(shot), full_page=True)
            artifacts["screenshot"] = str(shot)
        except Exception as exc:
            logger.warning("ConsigLog: falha ao salvar screenshot: {}", exc)
        try:
            html = out_dir / f"{label}_{ts}.html"
            html.write_text(page.content(), encoding="utf-8")
            artifacts["html"] = str(html)
        except Exception as exc:
            logger.warning("ConsigLog: falha ao salvar HTML: {}", exc)
        return artifacts

    def _error_result(self, row: ConsigLogInputRow, status: str, observacao: str) -> ConsigLogResult:
        return ConsigLogResult(
            row_index=row.row_index,
            matricula=row.matricula,
            nome=row.nome,
            cpf=row.cpf,
            margens=None,
            status_consulta=status,  # type: ignore[arg-type]
            observacao=observacao,
            data_consulta=now_str(),
        )

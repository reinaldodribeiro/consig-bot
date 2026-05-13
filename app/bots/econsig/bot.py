"""EconsigBot — Econsig automation (portal.econsig.com.br) with manual captcha input."""
from __future__ import annotations

import contextlib
import time
from typing import Any, ClassVar

from loguru import logger

from app.bots.econsig import parsers, selectors as sel
from app.bots.econsig.schema import EconsigInputRow, EconsigResult
from app.core.base_bot import BaseBot
from app.core.browser import BrowserSession
from app.core.exceptions import AuthenticationError, ParseError, SessionExpired
from app.core.registry import register_bot
from app.services.captcha_solver import prompt_image_captcha
from app.utils.dates import now_str

_LOGIN_URL_DEFAULT = "https://portal.econsig.com.br/issa/v3/autenticarUsuario#no-back"
_CONSULTA_URL_DEFAULT = "https://portal.econsig.com.br/issa/v3/consultarMargem#no-back"


@register_bot
class EconsigBot(BaseBot):
    key: ClassVar[str] = "econsig"
    display_name: ClassVar[str] = "Econsig"
    InputRowModel: ClassVar[type[EconsigInputRow]] = EconsigInputRow
    ResultModel: ClassVar[type[EconsigResult]] = EconsigResult

    def __init__(self, config) -> None:
        super().__init__(config)
        extras = self.system.extras or {}
        self._login_url: str = extras.get("login_url", _LOGIN_URL_DEFAULT)
        self._consulta_url: str = extras.get("consulta_url", _CONSULTA_URL_DEFAULT)
        self._captcha_max_attempts: int = int(extras.get("captcha_max_attempts", 5))

    # ---- BaseBot interface --------------------------------------------------

    def authenticate(self, session: BrowserSession) -> None:
        page = session.page
        logger.info("Econsig: navegando para login ({})", self._login_url)
        page.goto(self._login_url, wait_until="domcontentloaded")
        with contextlib.suppress(Exception):
            page.wait_for_load_state("networkidle", timeout=10_000)

        # If already inside the app (matricula input visible), skip login
        if page.locator(sel.MATRICULA_INPUT).count() > 0:
            logger.info("Econsig: sessão ativa — pulando login")
            return

        last_error: str = ""
        for attempt in range(1, self._captcha_max_attempts + 1):
            logger.info("Econsig: tentativa de captcha {}/{}", attempt, self._captcha_max_attempts)

            # Ensure we're on the password+captcha step. If the site bounced us back
            # to the username screen (typical after a rejected captcha), redo step 1.
            if not self._is_on_password_step(page):
                self._login_step1(page)

            # Get captcha image bytes via Playwright screenshot
            try:
                captcha_bytes = page.locator(sel.CAPTCHA_IMG).screenshot()
            except Exception as exc:
                logger.warning("Econsig: screenshot captcha falhou: {}", exc)
                continue

            # Show the image to the user and ask them to type the code
            solution = prompt_image_captcha(captcha_bytes, label=f"econsig_attempt{attempt}")
            logger.info("Econsig: captcha tentativa {} solution={!r}", attempt, solution)

            if not solution:
                logger.info("Econsig: usuário enviou código vazio, atualizando captcha")
                self._click_captcha_refresh(page)
                continue

            # Submit
            page.fill(sel.LOGIN_PASS, self.system.auth.password.get_secret_value())
            page.fill(sel.CAPTCHA_INPUT, solution)

            initial_url = page.url
            try:
                page.click(sel.LOGIN_SUBMIT_BTN)
            except Exception as exc:
                logger.debug("Econsig: click btnOK falhou: {}", exc)

            # Poll: nav away (success), error message, or bounce back to username (captcha rejected)
            deadline = time.monotonic() + 10.0
            outcome = "timeout"
            while time.monotonic() < deadline:
                current_url = page.url
                if current_url != initial_url and "autenticar" not in current_url.lower():
                    outcome = "nav"
                    break
                err = parsers.parse_error_message(page)
                if err:
                    last_error = err
                    outcome = "error"
                    break
                # The site may silently throw us back to step 1 (username field visible again)
                if page.locator(sel.LOGIN_USER).count() > 0 and page.locator(sel.LOGIN_USER).first.is_visible():
                    outcome = "bounce_to_step1"
                    break
                time.sleep(0.1)

            logger.debug("Econsig: pós-submit outcome={}, URL={}", outcome, page.url)

            if outcome == "nav":
                logger.info("Econsig: autenticado com sucesso")
                with contextlib.suppress(Exception):
                    page.wait_for_load_state("networkidle", timeout=10_000)
                return

            if outcome == "error":
                cls = parsers.classify_error(last_error)
                if cls == "captcha_invalid":
                    logger.info("Econsig: captcha inválido ({!r}), retentando do step 1", solution)
                    continue  # next iteration runs step 1 again because password field is gone
                raise AuthenticationError(f"Econsig: erro de login: {last_error}")

            if outcome == "bounce_to_step1":
                logger.info("Econsig: site retornou ao step 1 (captcha rejeitado silenciosamente), retentando")
                continue

            logger.warning("Econsig: timeout aguardando resultado do login, retentando")
            self._click_captcha_refresh(page)

        raise AuthenticationError(
            f"Econsig: captcha não resolvido após {self._captcha_max_attempts} tentativas. "
            f"Último erro: {last_error or 'nenhum'}"
        )

    # ---- login helpers ------------------------------------------------------

    def _click_captcha_refresh(self, page) -> None:
        """Click the visible 'Atualizar' icon to reload the captcha. Falls back to JS src refresh."""
        try:
            loc = page.locator(sel.CAPTCHA_REFRESH_BTN).first
            if loc.count() > 0 and loc.is_visible(timeout=500):
                loc.click()
                logger.debug("Econsig: clicou no botão de atualizar captcha")
                time.sleep(0.4)
                return
        except Exception as exc:
            logger.debug("Econsig: click no refresh button falhou: {}", exc)

        # Fallback: trigger img src reload via JS (keeps the current base URL)
        try:
            page.evaluate(
                "(() => { const i = document.querySelector(\"img[name='captcha_img']\"); "
                "if (!i) return; const base = (i.src || '').split('?')[0]; "
                "i.src = base + '?t=' + Date.now(); })()"
            )
            time.sleep(0.3)
            logger.debug("Econsig: fallback JS refresh executado")
        except Exception as exc:
            logger.debug("Econsig: fallback JS refresh falhou: {}", exc)

    def _is_on_consulta_page(self, page) -> bool:
        """Detect if the matricula input is already visible (= we're on consultar-margem)."""
        loc = page.locator(sel.MATRICULA_INPUT)
        if loc.count() == 0:
            return False
        try:
            return loc.first.is_visible(timeout=500)
        except Exception:
            return False

    def _navigate_to_consulta(self, page) -> None:
        """Navigate to Consultar Margem via menu clicks (site rejects direct GET)."""
        logger.info("Econsig: navegando via menu Operacional > Consultar Margem")

        # 1) Click "Operacional" to expand the submenu
        try:
            op = page.locator(sel.MENU_OPERACIONAL_TOGGLE).first
            op.wait_for(state="visible", timeout=10_000)
            op.click()
        except Exception as exc:
            raise ParseError(f"Econsig: menu Operacional não disponível: {exc}") from exc

        # 2) Click "Consultar Margem" inside the submenu
        try:
            cm = page.locator(sel.MENU_CONSULTAR_MARGEM).first
            cm.wait_for(state="visible", timeout=5_000)
            cm.click()
        except Exception as exc:
            raise ParseError(f"Econsig: item Consultar Margem não disponível: {exc}") from exc

        with contextlib.suppress(Exception):
            page.wait_for_load_state("networkidle", timeout=15_000)

        # 3) Wait for matricula input to appear (confirms postData succeeded)
        try:
            page.wait_for_selector(sel.MATRICULA_INPUT, state="visible", timeout=15_000)
        except Exception as exc:
            raise ParseError(
                f"Econsig: campo matrícula não apareceu após navegar pelo menu: {exc}"
            ) from exc

    def _is_on_password_step(self, page) -> bool:
        loc = page.locator(sel.LOGIN_PASS)
        if loc.count() == 0:
            return False
        try:
            return loc.first.is_visible(timeout=500)
        except Exception:
            return False

    def _login_step1(self, page) -> None:
        """Goto login URL (if needed) and complete the username step."""
        if page.locator(sel.LOGIN_USER).count() == 0:
            page.goto(self._login_url, wait_until="domcontentloaded")
            with contextlib.suppress(Exception):
                page.wait_for_load_state("networkidle", timeout=10_000)

        try:
            page.wait_for_selector(sel.LOGIN_USER, state="visible", timeout=10_000)
        except Exception as exc:
            raise AuthenticationError(f"Econsig: campo usuário não apareceu: {exc}") from exc

        page.fill(sel.LOGIN_USER, self.system.auth.email)
        logger.info("Econsig: preenchendo usuário")

        try:
            with page.expect_navigation(wait_until="domcontentloaded", timeout=15_000):
                page.click(sel.LOGIN_NEXT_BTN)
        except Exception as exc:
            logger.debug("Econsig: expect_navigation pós-Próxima falhou ({}) — seguindo", exc)
        with contextlib.suppress(Exception):
            page.wait_for_load_state("networkidle", timeout=10_000)

        try:
            page.wait_for_selector(sel.LOGIN_PASS, state="visible", timeout=10_000)
        except Exception as exc:
            raise AuthenticationError(f"Econsig: campo senha não apareceu: {exc}") from exc

    def process_row(self, session: BrowserSession, row: EconsigInputRow) -> EconsigResult:  # type: ignore[override]
        page = session.page
        matricula = row.matricula
        logger.info("Econsig: consultando linha {} (matrícula={})", row.row_index, matricula)

        if not matricula:
            return self._error_result(row, "erro", "Matrícula vazia")

        # If we're already on consultar-margem (subsequent rows), reuse it.
        # Otherwise navigate via menu (the site rejects direct GET with "Acesso Negado").
        if not self._is_on_consulta_page(page):
            self._navigate_to_consulta(page)

        # Check for session expiry (redirect to login)
        if "autenticar" in page.url.lower():
            raise SessionExpired("Econsig: redirecionado para login durante consulta")

        # Wait for matricula input
        try:
            page.wait_for_selector(sel.MATRICULA_INPUT, state="visible", timeout=10_000)
        except Exception as exc:
            raise ParseError(f"Econsig: campo matrícula não apareceu: {exc}") from exc

        # Clear stale result spans from a previous query so wait_for_function
        # below blocks until the NEW response renders (not the old text).
        with contextlib.suppress(Exception):
            page.evaluate(
                "(() => { ['idMsgSuccessSession','idMsgErrorSession'].forEach(id => { "
                "const el = document.getElementById(id); if (el) el.textContent = ''; }); })()"
            )

        page.fill(sel.MATRICULA_INPUT, matricula)
        # Press Tab to trigger onblur validators (fout/ValidaMascaraV4/vfRseMatricula),
        # otherwise validaSubmit(false) called by the search anchor may silently abort.
        page.locator(sel.MATRICULA_INPUT).press("Tab")
        with contextlib.suppress(Exception):
            page.wait_for_load_state("networkidle", timeout=5_000)

        # Click via DOM evaluate — the search element is an <a onclick="validaSubmit(false)">
        # which is more reliably triggered with a direct DOM .click() than Playwright actionability.
        try:
            clicked = page.evaluate(
                "(() => { const b = document.getElementById('btnEnvia'); "
                "if (!b) return false; b.click(); return true; })()"
            )
            if not clicked:
                page.click(sel.PESQUISAR_BTN)
        except Exception as exc:
            logger.debug("Econsig: DOM click btnEnvia falhou ({}), tentando Playwright click", exc)
            page.click(sel.PESQUISAR_BTN)

        with contextlib.suppress(Exception):
            page.wait_for_load_state("networkidle", timeout=15_000)

        # Wait until either an error span has content OR the data-list <dl> appears (success)
        try:
            page.wait_for_function(
                """() => {
                    const e = document.querySelector('span#idMsgErrorSession');
                    const eText = e ? (e.textContent || '').trim() : '';
                    const dl = document.querySelector('dl.data-list');
                    return eText.length > 0 || (dl && dl.children.length > 0);
                }""",
                timeout=10_000,
            )
        except Exception as exc:
            logger.debug("Econsig: timeout aguardando resultado: {}", exc)

        # Check for session expiry after search
        if "autenticar" in page.url.lower():
            raise SessionExpired("Econsig: sessão expirou durante consulta")

        # Check error message
        err = parsers.parse_error_message(page)
        if err:
            cls = parsers.classify_error(err)
            # Return a row-bound result so matricula/nome/cpf are preserved in Excel
            if cls == "not_found":
                return EconsigResult(
                    row_index=row.row_index,
                    matricula=matricula,
                    nome=row.nome,
                    cpf=row.cpf,
                    margens=None,
                    status_consulta="nao_encontrado",
                    observacao=err,
                    data_consulta=now_str(),
                )
            if cls == "server_excluded":
                return EconsigResult(
                    row_index=row.row_index,
                    matricula=matricula,
                    nome=row.nome,
                    cpf=row.cpf,
                    margens=None,
                    status_consulta="servidor_excluido",
                    observacao=err,
                    data_consulta=now_str(),
                )
            raise ParseError(err)

        # Parse success result from the data-list <dl>
        data = parsers.parse_consulta_success(page)
        if data is None:
            return EconsigResult(
                row_index=row.row_index,
                matricula=matricula,
                nome=row.nome,
                cpf=row.cpf,
                margens=None,
                status_consulta="erro",
                observacao="Lista de dados não encontrada no resultado",
                data_consulta=now_str(),
            )
        return EconsigResult(
            row_index=row.row_index,
            matricula=matricula,
            nome=row.nome,
            cpf=data["cpf"] or row.cpf,
            data_nascimento=data["data_nascimento"],
            margens=data["margens"],
            status_consulta="ok",
            observacao="",
            data_consulta=now_str(),
        )

    def output_columns(self) -> list[str]:
        return [
            "Matrícula", "Nome", "CPF", "Data Nascimento",
            "Margem Empréstimo", "Margem Cartão",
            "Status Consulta", "Observação", "Data Consulta",
        ]

    def center_columns(self) -> list[str]:
        return ["Matrícula", "CPF", "Data Nascimento", "Margem Empréstimo", "Margem Cartão"]

    def expand_result(self, result: EconsigResult) -> list[dict[str, Any]]:  # type: ignore[override]
        m = result.margens
        return [{
            "Matrícula":         result.matricula,
            "Nome":              result.nome,
            "CPF":               result.cpf,
            "Data Nascimento":   result.data_nascimento,
            "Margem Empréstimo": m.margem_emprestimo if m else "",
            "Margem Cartão":     m.margem_cartao if m else "",
            "Status Consulta":   result.status_consulta,
            "Observação":        result.observacao,
            "Data Consulta":     result.data_consulta,
        }]

    # ---- helpers -------------------------------------------------------------

    def _error_result(self, row: EconsigInputRow, status: str, observacao: str) -> EconsigResult:
        return EconsigResult(
            row_index=row.row_index,
            matricula=row.matricula,
            nome=row.nome,
            cpf=row.cpf,
            margens=None,
            status_consulta=status,  # type: ignore[arg-type]
            observacao=observacao,
            data_consulta=now_str(),
        )

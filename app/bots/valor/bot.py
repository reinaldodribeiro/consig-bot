"""ValorBot — Valor Financiamentos automation."""
from __future__ import annotations

import contextlib
from typing import Any, ClassVar

from loguru import logger

from app.bots.valor import parsers
from app.bots.valor import selectors as sel
from app.bots.valor.schema import ValorContract, ValorInputRow, ValorResult
from app.core.base_bot import BaseBot
from app.core.browser import BrowserSession
from app.core.exceptions import (
    AuthenticationError,
    NotFoundError,
    ParseError,
)
from app.core.registry import register_bot
from app.services.captcha_solver import CaptchaSolver, build_captcha_solver
from app.utils.cpf import mask_cpf
from app.utils.dates import now_filename_ts, now_str
from app.utils.paths import ensure_dir, get_app_root

_VALID_STATUS_DEFAULT = ("DEFERIDO",)
_IGNORE_STATUS_DEFAULT = ("FINALIZADO", "CANCELADO")


@register_bot
class ValorBot(BaseBot):
    key: ClassVar[str] = "valor"
    display_name: ClassVar[str] = "Valor Financiamentos"
    InputRowModel: ClassVar[type[ValorInputRow]] = ValorInputRow
    ResultModel: ClassVar[type[ValorResult]] = ValorResult

    def __init__(self, config) -> None:
        super().__init__(config)
        self._captcha: CaptchaSolver = build_captcha_solver(config.bot.captcha)
        extras = self.system.extras or {}
        self._login_url: str = extras.get(
            "login_url", "https://www.valorscm.com.br/webagente+/index.php"
        )
        self._dashboard_url: str = extras.get(
            "dashboard_url", "https://www.valorscm.com.br/webagente+/dashboard.php"
        )
        self._valid_status: tuple[str, ...] = tuple(
            s.upper() for s in extras.get("valid_status", _VALID_STATUS_DEFAULT)
        )
        self._ignore_status: tuple[str, ...] = tuple(
            s.upper() for s in extras.get("ignore_status", _IGNORE_STATUS_DEFAULT)
        )
        # URL base para parcelas.php (mesmo domínio/caminho que dashboard)
        _base = self._dashboard_url.rsplit("/", 1)[0]
        self._parcelas_base_url: str = extras.get("parcelas_url", f"{_base}/parcelas.php")

    # ---- BaseBot interface --------------------------------------------------

    def authenticate(self, session: BrowserSession) -> None:
        page = session.page
        logger.info("Valor: tentando dashboard direto ({})", self._dashboard_url)
        page.goto(self._dashboard_url, wait_until="domcontentloaded")

        if self._needs_login(page):
            logger.info("Valor: redirecionado p/ login — preenchendo credenciais")
            if "/index.php" not in page.url and "/login" not in page.url.lower():
                page.goto(self._login_url, wait_until="domcontentloaded")
            self._fill_login(page)
            self._handle_captcha_if_present(page, "login Valor")
            page.click(sel.BTLOGIN)
            with contextlib.suppress(Exception):
                page.wait_for_load_state("networkidle", timeout=15_000)

            # Após o login (mesmo se mostrar "Acesso Negado: Fora do horário"),
            # navega direto pro dashboard — o site bloqueia o form mas continua
            # aceitando o dashboard com a sessão recém-criada.
            logger.info("Valor: navegando para dashboard após login")
            page.goto(self._dashboard_url, wait_until="domcontentloaded")
            with contextlib.suppress(Exception):
                page.wait_for_load_state("networkidle", timeout=10_000)

        if self._needs_login(page):
            art = self._save_failure_artifacts(page, label="auth_failed")
            lines = ["Login não confirmado.", "", f"URL atual: {art.get('url', '?')}"]
            if "screenshot" in art:
                lines.append(f"Screenshot: {art['screenshot']}")
            if "html" in art:
                lines.append(f"HTML: {art['html']}")
            lines.extend([
                "",
                f"Texto da página:\n{art.get('body_snippet', '(vazio)')}",
                "",
                "Causas comuns: credenciais erradas, captcha não resolvido, "
                "site fora do horário, ou seletor incorreto.",
            ])
            raise AuthenticationError("\n".join(lines))
        logger.info("Valor: autenticado")

    def _save_failure_artifacts(self, page, label: str = "failure") -> dict[str, str]:
        """Capture page context for diagnosis. Files only saved if debug=True."""
        artifacts: dict[str, str] = {"url": page.url}

        # Always capture body snippet (small, included in the error message)
        try:
            text = page.locator("body").inner_text(timeout=1500).strip()
            artifacts["body_snippet"] = text[:400] + ("..." if len(text) > 400 else "")
        except Exception:
            artifacts["body_snippet"] = ""

        # Heavy artifacts (PNG + HTML) only when debug mode — usuário vê na tela
        if not self.config.bot.debug:
            return artifacts

        out_dir = ensure_dir(get_app_root() / "checkpoint" / "screenshots" / self.key)
        ts = now_filename_ts()

        try:
            shot = out_dir / f"{label}_{ts}.png"
            page.screenshot(path=str(shot), full_page=True)
            artifacts["screenshot"] = str(shot)
        except Exception as exc:
            logger.warning("Falha ao salvar screenshot: {}", exc)

        try:
            html = out_dir / f"{label}_{ts}.html"
            html.write_text(page.content(), encoding="utf-8")
            artifacts["html"] = str(html)
        except Exception as exc:
            logger.warning("Falha ao salvar HTML: {}", exc)

        return artifacts

    def process_row(self, session: BrowserSession, row: ValorInputRow) -> ValorResult:  # type: ignore[override]
        page = session.page
        cpf_masked = mask_cpf(row.cpf)
        logger.info("Valor: consultando linha {} ({})", row.row_index, cpf_masked)

        if not row.cpf or len(row.cpf) != 11:
            return self._error_result(row, "ok", f"CPF inválido: {row.cpf!r}")

        if not page.locator(sel.CSSENHA_INPUT).is_visible():
            page.click(sel.MENU_CONSULTA_SALDO)
            try:
                page.wait_for_selector(sel.CSSENHA_INPUT, state="visible", timeout=10_000)
            except Exception as exc:
                self._save_failure_artifacts(page, label="menu_open_fail")
                raise ParseError(f"Campo CPF não apareceu após abrir menu: {exc}") from exc

        page.fill(sel.CSSENHA_INPUT, row.cpf)
        page.click(sel.BTCONSULTASALDO)

        # Aguarda o iframe de resultado aparecer na página principal
        try:
            page.wait_for_selector(sel.IFRAME_RESULT, timeout=20_000)
        except Exception as exc:
            self._save_failure_artifacts(page, label="iframe_timeout")
            raise ParseError(f"iframe de resultado não apareceu após consulta: {exc}") from exc

        # Entra no contexto do iframe
        frame = page.frame(name=sel.IFRAME_RESULT_NAME)
        if frame is None:
            self._save_failure_artifacts(page, label="iframe_none")
            raise ParseError("frame 'rbmcont' não encontrado após iframe aparecer na DOM")

        with contextlib.suppress(Exception):
            frame.wait_for_load_state("networkidle", timeout=10_000)

        # Aguarda tabela ou toast dentro do iframe
        try:
            frame.wait_for_selector(sel.CONTRACTS_TABLE_OR_TOAST, timeout=15_000)
        except Exception as exc:
            self._save_failure_artifacts(page, label="table_timeout")
            raise ParseError(f"Tabela ou toast não apareceu dentro do iframe: {exc}") from exc

        with contextlib.suppress(Exception):
            frame.wait_for_selector(sel.CONTRACTS_TABLE, state="visible", timeout=8_000)

        # Aguarda ao menos uma linha carregar na tabela
        try:
            frame.wait_for_selector(sel.CONTRACTS_TABLE_ROWS, timeout=15_000)
        except Exception:
            pass  # pode ser que só tenha toast de erro — segue para verificar

        if self._has_captcha(page):
            self._handle_captcha_if_present(page, "consulta saldo")

        toast = parsers.parse_error_toast(frame)
        if toast and sel.NO_INFO_MESSAGE_TEXT.lower() in toast.lower():
            raise NotFoundError(toast)

        contracts = parsers.parse_contracts_table(frame)
        logger.info("Valor: linha {} — {} contratos", row.row_index, len(contracts))

        for c in contracts:
            c.data_vencimento = self._fetch_first_vencimento(frame, c.contrato)

        return ValorResult(
            row_index=row.row_index,
            cpf=row.cpf,
            nome=row.nome,
            contracts=contracts,
            status_consulta="ok",
            observacao=toast or ("" if contracts else "sem contratos"),
            data_consulta=now_str(),
        )

    def output_columns(self) -> list[str]:
        return [
            "CPF", "Nome", "Contrato", "Data Vencimento", "Parcelas",
            "Convenio", "Status Contrato", "Status Consulta", "Observacao", "Data Consulta",
        ]

    def expand_result(self, result: ValorResult) -> list[dict[str, Any]]:  # type: ignore[override]
        if not result.contracts:
            return [{
                "CPF": result.cpf, "Nome": result.nome,
                "Contrato": "", "Data Vencimento": "", "Parcelas": "", "Convenio": "",
                "Status Contrato": "",
                "Status Consulta": result.status_consulta,
                "Observacao": result.observacao,
                "Data Consulta": result.data_consulta,
            }]
        return [{
            "CPF": result.cpf, "Nome": result.nome,
            "Contrato": c.contrato,
            "Data Vencimento": c.data_vencimento or "",
            "Parcelas": c.parcelas, "Convenio": c.convenio,
            "Status Contrato": c.status,
            "Status Consulta": result.status_consulta,
            "Observacao": result.observacao,
            "Data Consulta": result.data_consulta,
        } for c in result.contracts]

    # ---- helpers -------------------------------------------------------------

    def _needs_login(self, page) -> bool:
        url = page.url.lower()
        if "index.php" in url or "/login" in url or "/auth" in url:
            return True
        return (
            page.locator(sel.LOGIN_INPUT).count() > 0
            and page.locator(sel.BTLOGIN).count() > 0
        )

    def _fill_login(self, page) -> None:
        page.fill(sel.LOGIN_INPUT, self.system.auth.email)
        page.fill(sel.SENHA_INPUT, self.system.auth.password.get_secret_value())

    def _has_captcha(self, page) -> bool:
        try:
            return page.locator(sel.RECAPTCHA_IFRAME).count() > 0
        except Exception:
            return False

    def _handle_captcha_if_present(self, page, reason: str) -> None:
        if self._has_captcha(page):
            self._captcha.solve(page, reason=reason)

    def _fetch_first_vencimento(self, frame, contrato: str) -> str | None:
        """Navega o frame rbmcont para parcelas.php?codoper=XXXXX e extrai NDoc=1.

        O JS da página (parcelasJSLoad) carrega as linhas dinamicamente;
        por isso é necessário navegar o frame real em vez de fazer HTTP GET.
        """
        codoper = contrato.lstrip("0").zfill(11)
        url = f"{self._parcelas_base_url}?codoper={codoper}"
        try:
            # parcelas.php carrega dados via JS — navega o próprio frame para executar o JS
            frame.goto(url, wait_until="domcontentloaded", timeout=15_000)
            with contextlib.suppress(Exception):
                frame.wait_for_load_state("networkidle", timeout=10_000)
            frame.wait_for_selector(
                '#pn_parcelas_table_detail tr[id^="cronograma_"]',
                state="visible", timeout=12_000,
            )
            vencimento = parsers.parse_first_due_date(frame)
            logger.debug("_fetch_first_vencimento {}: {}", codoper, vencimento)
            return vencimento
        except Exception as exc:
            logger.debug("_fetch_first_vencimento {} erro: {}", codoper, exc)
            return None

    def _error_result(self, row: ValorInputRow, status: str, observacao: str) -> ValorResult:
        return ValorResult(
            row_index=row.row_index,
            cpf=row.cpf,
            nome=row.nome,
            contracts=[],
            status_consulta=status,  # type: ignore[arg-type]
            observacao=observacao,
            data_consulta=now_str(),
        )

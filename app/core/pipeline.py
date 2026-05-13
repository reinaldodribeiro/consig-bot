"""Pipeline — generic orchestrator: read rows → process → write."""
from __future__ import annotations

import contextlib
import time
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING

from loguru import logger
from rich.console import Console
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeRemainingColumn,
)

from app.core.exceptions import (
    AuthenticationError,
    BotError,
    CaptchaRequired,
    NotFoundError,
    RateLimited,
    SessionExpired,
)
from app.utils.dates import now_str
from app.utils.screenshots import save_screenshot

if TYPE_CHECKING:
    from app.core.base_bot import BaseBot
    from app.core.browser import BrowserSession
    from app.models.input_row import BaseInputRow
    from app.services.checkpoint import CheckpointManager
    from app.services.excel_writer import ExcelWriter

_console = Console()


class Pipeline:
    """Drives one bot through a list of input rows.

    `concurrency` is reserved for v0.5 (multi-page workers); MVP uses serial loop.
    """

    def __init__(
        self,
        bot: BaseBot,
        session: BrowserSession,
        writer: ExcelWriter,
        checkpoint: CheckpointManager,
        screenshots_dir: Path,
        concurrency: int = 1,
    ) -> None:
        if concurrency != 1:
            logger.warning("concurrency>1 ainda não suportado — caindo para serial.")
        self.bot = bot
        self.session = session
        self.writer = writer
        self.checkpoint = checkpoint
        self.screenshots_dir = screenshots_dir

    def run(self, rows: Iterable[BaseInputRow]) -> dict[str, int]:
        all_rows = list(rows)
        max_rows = self.bot.config.bot.max_rows
        pending = [r for r in all_rows if not self.checkpoint.is_processed(r.row_index)]
        if max_rows:
            pending = pending[:max_rows]

        skipped = self.checkpoint.processed_count()
        if skipped > 0:
            _console.print(
                f"[yellow]Retomando: {skipped} já processadas, {len(pending)} pendentes.[/yellow]"
            )

        stats: dict[str, int] = {}
        delay = self.bot.config.bot.delay_between_queries_seconds

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            MofNCompleteColumn(),
            TaskProgressColumn(),
            TimeRemainingColumn(),
            console=_console,
            transient=False,
        ) as progress:
            task = progress.add_task(f"{self.bot.display_name}", total=len(pending))
            for i, row in enumerate(pending, 1):
                desc = self._describe_row(row, i, len(pending))
                progress.update(task, description=desc)
                result = self._process_one(row, progress)
                self.writer.append_result(result)
                status = getattr(result, "status_consulta", "ok")
                self.checkpoint.mark_done(row.row_index, str(status))
                stats[str(status)] = stats.get(str(status), 0) + 1
                progress.advance(task)
                if delay > 0 and i < len(pending):
                    time.sleep(delay)
        return stats

    def _process_one(self, row: BaseInputRow, progress: Progress):
        result_cls = self.bot.ResultModel
        cpf = getattr(row, "cpf", "")
        nome = getattr(row, "nome", "")
        try:
            return self.bot.process_row(self.session, row)
        except NotFoundError as exc:
            logger.info("row {}: não encontrado ({})", row.row_index, exc)
            return result_cls.model_validate({
                "row_index": row.row_index, "cpf": cpf, "nome": nome,
                "status_consulta": "nao_encontrado",
                "observacao": str(exc)[:200], "data_consulta": now_str(),
            })
        except RateLimited as exc:
            logger.warning("row {}: rate limit ({})", row.row_index, exc)
            return result_cls.model_validate({
                "row_index": row.row_index, "cpf": cpf, "nome": nome,
                "status_consulta": "rate_limit",
                "observacao": str(exc)[:200], "data_consulta": now_str(),
            })
        except SessionExpired:
            with _suspend(progress, "Sessão expirada — refazendo login"):
                try:
                    self.bot.authenticate(self.session)
                except Exception as login_exc:
                    logger.error("Falha ao re-autenticar: {}", login_exc)
                    return result_cls.model_validate({
                        "row_index": row.row_index, "cpf": cpf, "nome": nome,
                        "status_consulta": "auth_error",
                        "observacao": str(login_exc)[:200], "data_consulta": now_str(),
                    })
            try:
                return self.bot.process_row(self.session, row)
            except Exception as exc2:
                self._snap("session_retry_fail", row)
                return result_cls.model_validate({
                    "row_index": row.row_index, "cpf": cpf, "nome": nome,
                    "status_consulta": "erro",
                    "observacao": str(exc2)[:200], "data_consulta": now_str(),
                })
        except CaptchaRequired as exc:
            logger.warning("row {}: captcha ({})", row.row_index, exc)
            return result_cls.model_validate({
                "row_index": row.row_index, "cpf": cpf, "nome": nome,
                "status_consulta": "captcha",
                "observacao": str(exc)[:200], "data_consulta": now_str(),
            })
        except AuthenticationError as exc:
            logger.error("row {}: auth error ({})", row.row_index, exc)
            self._snap("auth_error", row)
            raise BotError("Falha de autenticação fatal — abortando run") from exc
        except Exception as exc:
            logger.exception("row {}: erro inesperado: {}", row.row_index, exc)
            self._snap("unexpected", row)
            return result_cls.model_validate({
                "row_index": row.row_index, "cpf": cpf, "nome": nome,
                "status_consulta": "erro",
                "observacao": str(exc)[:200], "data_consulta": now_str(),
            })

    def _describe_row(self, row: BaseInputRow, i: int, total: int) -> str:
        nome = str(getattr(row, "nome", ""))[:24]
        return f"[{i}/{total}] {nome}"

    def _snap(self, label: str, row: BaseInputRow) -> None:
        if not self.bot.config.bot.debug:
            return
        with contextlib.suppress(Exception):
            save_screenshot(self.session.page, f"row{row.row_index}_{label}", self.screenshots_dir)


@contextmanager
def _suspend(progress: Progress, reason: str) -> Iterator[None]:
    progress.stop()
    if reason:
        _console.print(f"\n[yellow]{reason}[/yellow]")
    try:
        yield
    finally:
        progress.start()

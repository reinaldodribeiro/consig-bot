"""Consig Bot — main entrypoint. Run: python -m app  OR  python main.py"""
from __future__ import annotations

import sys
import traceback

from rich.console import Console
from rich.panel import Panel

_console = Console()


def run() -> int:
    """Returns process exit code."""
    # Configure logging FIRST so all subsequent logs are captured
    from app.utils.logger import configure_loguru
    from app.utils.paths import ensure_dir, get_app_root

    root = get_app_root()
    logs_dir = ensure_dir(root / "logs")
    configure_loguru(logs_dir)

    from loguru import logger

    from app.cli.menu import confirm, select_bot, select_input_file, show_banner
    from app.core.browser import BrowserSession
    from app.core.exceptions import BotError, ConfigError
    from app.core.pipeline import Pipeline
    from app.core.registry import BotRegistry
    from app.models.config import AppConfig
    from app.services.checkpoint import CheckpointManager
    from app.services.excel_reader import ExcelReader
    from app.services.excel_writer import ExcelWriter
    from app.utils.dates import now_filename_ts

    trace_path = None  # populated below; surfaced in finally for user reference

    try:
        show_banner()

        config_path = root / "config.json"
        config = AppConfig.load(config_path)
        # Reconfigure logger now that we know the user's debug preference
        configure_loguru(logs_dir, debug=config.bot.debug)
        logger.info("Config carregada de {}", config_path.name)
        if config.bot.debug:
            _console.print("[dim](modo debug ativo — logs detalhados no console)[/dim]\n")

        BotRegistry.discover()
        available = BotRegistry.list_available(config)
        bot_key = select_bot(available, config)
        bot = BotRegistry.create(bot_key, config)
        logger.info("Bot selecionado: {} ({})", bot.display_name, bot.key)

        input_folder = root / config.bot.input_folder
        input_file = select_input_file(input_folder)

        rows = ExcelReader(input_file, bot).read()
        if not rows:
            _console.print("[yellow]Planilha sem linhas válidas. Encerrando.[/yellow]")
            return 0
        _console.print(f"[dim]{len(rows)} linhas lidas de {input_file.name}[/dim]")

        if not confirm(f"Processar {len(rows)} linhas com {bot.display_name}?", default=True):
            _console.print("[yellow]Cancelado pelo usuário.[/yellow]")
            return 0

        output_dir = ensure_dir(root / config.bot.output_folder / bot.key)
        checkpoint_dir = ensure_dir(root / "checkpoint" / bot.key)
        screenshots_dir = ensure_dir(root / "checkpoint" / "screenshots" / bot.key)

        if config.bot.debug:
            import shutil
            shutil.rmtree(screenshots_dir, ignore_errors=True)
            screenshots_dir.mkdir(parents=True, exist_ok=True)
            shutil.rmtree(checkpoint_dir, ignore_errors=True)
            checkpoint_dir.mkdir(parents=True, exist_ok=True)
            _console.print("[dim](debug: screenshots e checkpoint limpos)[/dim]")

        writer = ExcelWriter(output_dir, bot)
        checkpoint = CheckpointManager(checkpoint_dir, bot.key)

        _console.print(f"\n[cyan]Abrindo navegador (headless={config.bot.headless})...[/cyan]")
        if config.bot.debug:
            trace_path = ensure_dir(root / "checkpoint" / bot.key) / f"trace_{now_filename_ts()}.zip"
        with BrowserSession(config.bot, trace_path=trace_path) as session:
            _console.print(f"[cyan]Autenticando em {bot.display_name}...[/cyan]")
            bot.authenticate(session)
            _console.print("[green]Autenticado.[/green]\n")
            pipeline = Pipeline(bot, session, writer, checkpoint, screenshots_dir)
            stats = pipeline.run(rows)

        writer.close()
        _console.print(Panel.fit(
            "\n".join(f"[cyan]{k}[/cyan]: {v}" for k, v in stats.items()) or "[dim]sem estatísticas[/dim]",
            title="Resumo da execução",
            border_style="green",
        ))
        if writer.has_data:
            _console.print(f"[green]Saída: {writer.file_path}[/green]")
        else:
            _console.print("[yellow]Nenhuma linha processada — arquivo de saída não gerado.[/yellow]")
        return 0

    except KeyboardInterrupt:
        _console.print("\n[yellow]Interrompido pelo usuário (Ctrl+C).[/yellow]")
        return 130
    except ConfigError as exc:
        _console.print(Panel(f"[red]{exc}[/red]", title="Erro de configuração", border_style="red"))
        return 2
    except BotError as exc:
        _console.print(Panel(f"[red]{exc}[/red]", title="Erro do bot", border_style="red"))
        return 3
    except Exception as exc:
        _console.print(Panel(
            f"[red]{exc}[/red]\n[dim]{traceback.format_exc()}[/dim]",
            title="Erro inesperado",
            border_style="red",
        ))
        return 1
    finally:
        if trace_path is not None and trace_path.exists():
            _console.print(
                f"\n[dim]Trace para inspeção:[/dim]\n"
                f"[cyan]poetry run playwright show-trace {trace_path}[/cyan]"
            )


if __name__ == "__main__":
    sys.exit(run())

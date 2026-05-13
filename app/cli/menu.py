"""CLI menus — bot selection and input file selection (Rich-based)."""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from rich.console import Console
from rich.panel import Panel
from rich.prompt import IntPrompt, Prompt
from rich.table import Table

from app.core.exceptions import BotError
from app.models.config import AppConfig

if TYPE_CHECKING:
    from app.core.base_bot import BaseBot

_console = Console()


def show_banner() -> None:
    _console.print(Panel.fit(
        "[bold cyan]Consig Bot[/bold cyan]\n"
        "[dim]Automação de consultas — múltiplos sistemas[/dim]",
        border_style="cyan",
    ))


def select_bot(available: list[type[BaseBot]], config: AppConfig) -> str:
    if not available:
        raise BotError(
            "Nenhum bot disponível. Verifique se há sistemas em config.json e bots em app/bots/."
        )
    if len(available) == 1:
        only = available[0]
        _console.print(f"[green]Único sistema disponível: {only.display_name} ({only.key})[/green]")
        return only.key

    table = Table(title="Sistemas disponíveis", show_header=True, header_style="bold cyan")
    table.add_column("#", justify="right")
    table.add_column("Key", style="cyan")
    table.add_column("Nome", style="white")
    for i, cls in enumerate(available, 1):
        table.add_row(str(i), cls.key, cls.display_name)
    _console.print(table)

    choice = IntPrompt.ask(
        "[cyan]Escolha o sistema[/cyan]",
        choices=[str(i) for i in range(1, len(available) + 1)],
        default=1,
    )
    return available[choice - 1].key


def select_input_file(input_folder: Path) -> Path:
    if not input_folder.exists():
        raise BotError(f"Pasta de entrada não encontrada: {input_folder}")
    files = sorted([p for p in input_folder.glob("*.xlsx") if not p.name.startswith("~$")])
    if not files:
        raise BotError(f"Nenhum .xlsx encontrado em {input_folder}/. Coloque planilhas e tente novamente.")
    if len(files) == 1:
        _console.print(f"[green]Único arquivo: {files[0].name}[/green]")
        return files[0]

    table = Table(title=f"Planilhas em {input_folder.name}/", show_header=True, header_style="bold cyan")
    table.add_column("#", justify="right")
    table.add_column("Arquivo", style="white")
    table.add_column("Tamanho", justify="right", style="dim")
    for i, p in enumerate(files, 1):
        kb = p.stat().st_size / 1024
        table.add_row(str(i), p.name, f"{kb:.1f} KB")
    _console.print(table)

    choice = IntPrompt.ask(
        "[cyan]Escolha o arquivo[/cyan]",
        choices=[str(i) for i in range(1, len(files) + 1)],
        default=1,
    )
    return files[choice - 1]


def confirm(message: str, default: bool = True) -> bool:
    suffix = "[Y/n]" if default else "[y/N]"
    answer = Prompt.ask(f"[cyan]{message}[/cyan] {suffix}", default="y" if default else "n")
    return answer.strip().lower() in ("y", "yes", "s", "sim", "1", "true")

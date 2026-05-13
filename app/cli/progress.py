"""Rich Progress factory + suspend context (re-exported for convenience)."""
from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

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

_console = Console()


def make_progress() -> Progress:
    return Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TaskProgressColumn(),
        TimeRemainingColumn(),
        console=_console,
        transient=False,
    )


@contextmanager
def suspend_progress(progress: Progress, reason: str = "") -> Iterator[None]:
    progress.stop()
    if reason:
        _console.print(f"\n[yellow]{reason}[/yellow]")
    try:
        yield
    finally:
        progress.start()

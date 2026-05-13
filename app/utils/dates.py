"""Date/time helpers — pt-BR formats."""
from __future__ import annotations

from datetime import datetime

_BR_FORMATS = ("%d/%m/%Y", "%d/%m/%y", "%Y-%m-%d")


def now_str() -> str:
    return datetime.now().strftime("%d/%m/%Y %H:%M:%S")


def now_filename_ts() -> str:
    return datetime.now().strftime("%Y-%m-%d_%H-%M-%S")


def parse_br_date(value: str | None) -> datetime | None:
    if not value:
        return None
    value = value.strip()
    for fmt in _BR_FORMATS:
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None

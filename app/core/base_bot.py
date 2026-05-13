"""BaseBot — Strategy contract for every system supported by Consig Bot."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, ClassVar

from pydantic import BaseModel

from app.models.config import AppConfig, SystemConfig
from app.models.input_row import BaseInputRow

if TYPE_CHECKING:
    from app.core.browser import BrowserSession


class BaseBot(ABC):
    """Each supported site implements one subclass.

    Subclasses MUST set the class-vars and implement the four abstract methods.
    """

    key: ClassVar[str]                            # short identifier, e.g. "valor"
    display_name: ClassVar[str]                   # human-readable name
    InputRowModel: ClassVar[type[BaseInputRow]]   # Pydantic class for input rows
    ResultModel: ClassVar[type[BaseModel]]        # Pydantic class for the per-row result

    def __init__(self, config: AppConfig) -> None:
        self.config = config
        if self.key not in config.sistemas:
            raise KeyError(
                f"Sistema '{self.key}' ausente em config.json — "
                f"sistemas disponíveis: {list(config.sistemas.keys())}"
            )
        self.system: SystemConfig = config.sistemas[self.key]

    @abstractmethod
    def authenticate(self, session: BrowserSession) -> None:
        """Log into the site. Must leave the session in a ready-to-query state."""

    @abstractmethod
    def process_row(self, session: BrowserSession, row: BaseInputRow) -> BaseModel:
        """Process one input row → return one result instance of `ResultModel`."""

    @abstractmethod
    def output_columns(self) -> list[str]:
        """Ordered list of Excel column names this bot writes."""

    @abstractmethod
    def expand_result(self, result: BaseModel) -> list[dict[str, Any]]:
        """Flatten one result into 1+ Excel rows (dicts keyed by output_columns)."""

    def center_columns(self) -> list[str]:
        """Column names that should be center-aligned in the output sheet."""
        return []

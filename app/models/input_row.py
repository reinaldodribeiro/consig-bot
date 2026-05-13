"""Base DTO for an input Excel row. Bots subclass with their own fields."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class BaseInputRow(BaseModel):
    model_config = ConfigDict(extra="allow")
    row_index: int
    raw: dict[str, Any] = Field(default_factory=dict)

"""Base DTO for a query result. Bots define their own ResultModel."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

QueryStatus = Literal["ok", "nao_encontrado", "erro", "rate_limit", "captcha", "auth_error"]


class BaseQueryResult(BaseModel):
    model_config = ConfigDict(extra="allow")
    row_index: int
    status_consulta: QueryStatus = "ok"
    observacao: str = ""
    data_consulta: str = ""

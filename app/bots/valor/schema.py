"""Pydantic models for the Valor Financiamentos bot."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.input_row import BaseInputRow
from app.utils.cpf import normalize_cpf

ValorStatus = Literal["ok", "nao_encontrado", "erro", "rate_limit", "captcha", "auth_error"]


class ValorInputRow(BaseInputRow):
    cpf: str = ""
    nome: str = ""

    @field_validator("cpf", mode="before")
    @classmethod
    def _normalize(cls, v: object) -> str:
        return normalize_cpf(str(v) if v is not None else "")


class ValorContract(BaseModel):
    model_config = ConfigDict(extra="ignore")
    contrato: str = ""
    parcelas: str = ""
    status: str = ""
    convenio: str = ""
    data_vencimento: str | None = None
    table_row: int = 0


class ValorResult(BaseModel):
    model_config = ConfigDict(extra="allow")
    row_index: int
    cpf: str = ""
    nome: str = ""
    contracts: list[ValorContract] = Field(default_factory=list)
    status_consulta: ValorStatus = "ok"
    observacao: str = ""
    data_consulta: str = ""

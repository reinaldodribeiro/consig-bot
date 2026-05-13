"""Pydantic models for the ConsigLog bot."""
from __future__ import annotations
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator
from app.models.input_row import BaseInputRow

ConsigLogStatus = Literal["ok", "nao_encontrado", "erro", "session_expired", "auth_error"]


class ConsigLogInputRow(BaseInputRow):
    matricula: str = ""
    cpf: str = ""
    nome: str = ""

    @field_validator("matricula", mode="before")
    @classmethod
    def _clean_matricula(cls, v: object) -> str:
        s = str(v) if v is not None else ""
        return "".join(ch for ch in s if ch.isdigit())


class ConsigLogMargens(BaseModel):
    model_config = ConfigDict(extra="ignore")
    margem_emprestimo: str = ""
    margem_cartao: str = ""


class ConsigLogResult(BaseModel):
    model_config = ConfigDict(extra="allow")
    row_index: int
    matricula: str = ""
    nome: str = ""
    cpf: str = ""
    margens: ConsigLogMargens | None = None
    status_consulta: ConsigLogStatus = "ok"
    observacao: str = ""
    data_consulta: str = ""

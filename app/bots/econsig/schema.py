"""Pydantic models for the Econsig bot."""
from __future__ import annotations
from typing import Literal
from pydantic import BaseModel, ConfigDict, field_validator
from app.models.input_row import BaseInputRow

EconsigStatus = Literal[
    "ok", "nao_encontrado", "servidor_excluido",
    "erro", "session_expired", "auth_error",
]


class EconsigInputRow(BaseInputRow):
    matricula: str = ""
    cpf: str = ""
    nome: str = ""

    @field_validator("matricula", mode="before")
    @classmethod
    def _clean_matricula(cls, v: object) -> str:
        s = str(v) if v is not None else ""
        return "".join(ch for ch in s if ch.isdigit())


class EconsigMargens(BaseModel):
    model_config = ConfigDict(extra="ignore")
    margem_emprestimo: str = ""
    margem_cartao: str = ""


class EconsigResult(BaseModel):
    model_config = ConfigDict(extra="allow")
    row_index: int
    matricula: str = ""
    nome: str = ""
    cpf: str = ""
    data_nascimento: str = ""
    margens: EconsigMargens | None = None
    status_consulta: EconsigStatus = "ok"
    observacao: str = ""
    data_consulta: str = ""

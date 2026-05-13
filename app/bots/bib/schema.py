"""Pydantic models for the BIB Cred bot."""
from __future__ import annotations
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator
from app.models.input_row import BaseInputRow
from app.utils.cpf import normalize_cpf

BibStatus = Literal["ok", "nao_encontrado", "erro", "rate_limit", "captcha", "auth_error"]

class BibInputRow(BaseInputRow):
    cpf: str = ""
    nome: str = ""

    @field_validator("cpf", mode="before")
    @classmethod
    def _normalize(cls, v: object) -> str:
        return normalize_cpf(str(v) if v is not None else "")

class BibContract(BaseModel):
    model_config = ConfigDict(extra="ignore")
    contrato: str = ""
    matricula: str = ""
    taxa_am: str = ""
    qtd_parc_total: str = ""
    qtd_parc_vencidas: str = ""
    qtd_parc_em_aberto: str = ""
    vlr_parcela: str = ""
    saldo_total: str = ""

class BibResult(BaseModel):
    model_config = ConfigDict(extra="allow")
    row_index: int
    cpf: str = ""
    nome: str = ""
    contracts: list[BibContract] = Field(default_factory=list)
    status_consulta: BibStatus = "ok"
    observacao: str = ""
    data_consulta: str = ""

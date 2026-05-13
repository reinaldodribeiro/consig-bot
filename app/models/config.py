"""Pydantic schemas for config.json. Strict validation at the boundary."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator

from app.core.exceptions import ConfigError


class ProxyConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enabled: bool = False
    server: str | None = None
    username: str | None = None
    password: SecretStr | None = None


class CaptchaConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mode: Literal["manual", "2captcha", "anti-captcha", "tesseract"] = "manual"
    api_key: SecretStr | None = None


class BotRuntimeConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    headless: bool = True
    debug: bool = False
    delay_between_queries_seconds: float = Field(1.0, ge=0)
    max_retries: int = Field(2, ge=0, le=10)
    max_rows: int | None = Field(None, ge=1)
    input_folder: str = "entrada"
    output_folder: str = "saida"
    timeout_navigation_ms: int = Field(30_000, ge=1000)
    timeout_selector_ms: int = Field(15_000, ge=1000)
    proxy: ProxyConfig = Field(default_factory=ProxyConfig)
    captcha: CaptchaConfig = Field(default_factory=CaptchaConfig)


_PLACEHOLDERS = {"usuario@email.com", "senha", "", "user@example.com"}


class SystemAuthConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: str
    password: SecretStr

    @field_validator("email", mode="after")
    @classmethod
    def _reject_email_placeholder(cls, v: str) -> str:
        if v.strip().lower() in _PLACEHOLDERS:
            raise ValueError(f"email placeholder não preenchido: {v!r}")
        return v

    @field_validator("password", mode="after")
    @classmethod
    def _reject_password_placeholder(cls, v: SecretStr) -> SecretStr:
        if v.get_secret_value().strip().lower() in _PLACEHOLDERS:
            raise ValueError("senha placeholder não preenchida")
        return v


class SystemExcelConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    cpf_column: str | None = "cpf"
    name_column: str | None = "nome"
    matricula_column: str | None = None


class SystemConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    auth: SystemAuthConfig
    excel: SystemExcelConfig = Field(default_factory=SystemExcelConfig)
    extras: dict[str, Any] = Field(default_factory=dict)


class AppConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    bot: BotRuntimeConfig = Field(default_factory=BotRuntimeConfig)
    sistemas: dict[str, SystemConfig]

    @classmethod
    def load(cls, path: Path) -> AppConfig:
        if not path.exists():
            raise ConfigError(
                f"config.json não encontrado em: {path}\n"
                f"Copie config.example.json → config.json e preencha as credenciais."
            )
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ConfigError(f"config.json inválido (JSON malformado): {exc}") from exc
        try:
            return cls.model_validate(raw)
        except Exception as exc:
            raise ConfigError(f"config.json com erros de validação:\n{exc}") from exc

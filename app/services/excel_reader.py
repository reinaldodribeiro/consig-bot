"""ExcelReader — read input rows for a given bot."""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pandas as pd
from loguru import logger

from app.core.exceptions import BotError
from app.models.config import SystemExcelConfig
from app.models.input_row import BaseInputRow
from app.utils.cpf import normalize_cpf

if TYPE_CHECKING:
    from app.core.base_bot import BaseBot


class ExcelReader:
    def __init__(self, file_path: Path, bot: BaseBot) -> None:
        self.file_path = file_path
        self.bot = bot
        self.excel_config: SystemExcelConfig = bot.system.excel

    def read(self) -> list[BaseInputRow]:
        if not self.file_path.exists():
            raise BotError(f"Arquivo de entrada não encontrado: {self.file_path}")

        logger.info("Lendo planilha: {}", self.file_path.name)
        df = pd.read_excel(self.file_path, dtype=str, keep_default_na=False)
        df.columns = [str(c).strip().lower() for c in df.columns]

        cpf_col = self.excel_config.cpf_column.lower() if self.excel_config.cpf_column else None
        name_col = self.excel_config.name_column.lower() if self.excel_config.name_column else None
        matricula_col = (
            self.excel_config.matricula_column.lower()
            if self.excel_config.matricula_column
            else None
        )
        required_cols = [c for c in (cpf_col, name_col, matricula_col) if c is not None]
        missing = [c for c in required_cols if c not in df.columns]
        if missing:
            raise BotError(
                f"Planilha {self.file_path.name} sem colunas obrigatórias: {missing}. "
                f"Colunas encontradas: {list(df.columns)}"
            )

        model_cls = self.bot.InputRowModel
        rows: list[BaseInputRow] = []
        for idx, row in df.iterrows():
            raw = {k: ("" if pd.isna(v) else str(v).strip()) for k, v in row.items()}
            data: dict = {
                "row_index": int(idx) + 2,  # +2: header + 1-based excel
                "raw": raw,
                "cpf": normalize_cpf(raw.get(cpf_col, "")) if cpf_col else "",
                "nome": raw.get(name_col, "") if name_col else "",
            }
            if matricula_col is not None:
                data["matricula"] = raw.get(matricula_col, "").strip()
            rows.append(model_cls.model_validate(data))

        logger.info("{} linhas lidas de {}", len(rows), self.file_path.name)
        return rows

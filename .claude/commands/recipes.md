<!-- mustard:generated -->
# Recipes — consig-bot

Receitas step-by-step para as tarefas mais comuns de extensão do projeto.

---

## Receita 1 — Novo bot completo

Cria um novo bot para um sistema diferente (ex: `fgts`, `inss`, `siape`).

### Passo 1 — Criar a estrutura de pastas

```bash
mkdir -p app/bots/{nome}
touch app/bots/{nome}/__init__.py
touch app/bots/{nome}/bot.py
touch app/bots/{nome}/schema.py
touch app/bots/{nome}/selectors.py
touch app/bots/{nome}/parsers.py
```

### Passo 2 — Criar `schema.py`

```python
# app/bots/{nome}/schema.py
from __future__ import annotations
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator
from app.models.input_row import BaseInputRow
from app.utils.cpf import normalize_cpf

{Nome}Status = Literal["ok", "nao_encontrado", "erro", "rate_limit", "captcha", "auth_error"]

class {Nome}InputRow(BaseInputRow):
    cpf: str = ""
    nome: str = ""

    @field_validator("cpf", mode="before")
    @classmethod
    def _normalize(cls, v: object) -> str:
        return normalize_cpf(str(v) if v is not None else "")

# Modelo para cada item/contrato scrapeado (se o site retorna lista)
class {Nome}Item(BaseModel):
    model_config = ConfigDict(extra="ignore")
    campo1: str = ""
    campo2: str = ""

class {Nome}Result(BaseModel):
    model_config = ConfigDict(extra="allow")
    row_index: int
    cpf: str = ""
    nome: str = ""
    items: list[{Nome}Item] = Field(default_factory=list)
    status_consulta: {Nome}Status = "ok"
    observacao: str = ""
    data_consulta: str = ""
```

### Passo 3 — Criar `selectors.py`

```python
# app/bots/{nome}/selectors.py
"""Selectors for {Nome}. Tune during smoke testing — kept centralized here."""
from __future__ import annotations

# === Login ===
LOGIN_INPUT = "input#login"        # ajuste conforme o site
SENHA_INPUT = "input#password"
BTLOGIN = "button[type='submit']"

# === Detecção de captcha ===
RECAPTCHA_IFRAME = (
    "iframe[src*='recaptcha'], iframe[title*='reCAPTCHA'], "
    "iframe[src*='captcha'], [class*='captcha']"
)

# === Formulário de consulta ===
CPF_INPUT = "input#cpf"
BTCONSULTA = "button#btnConsultar"

# === Resultado ===
RESULT_TABLE = "table#resultado"
ERROR_MESSAGE = ".alert-danger, .error-message, .toast"
NO_INFO_TEXT = "Não encontrado"
```

### Passo 4 — Criar `parsers.py`

```python
# app/bots/{nome}/parsers.py
"""Parsers — DOM extraction for {Nome}. No navigation here."""
from __future__ import annotations
from typing import TYPE_CHECKING
from loguru import logger
from app.bots.{nome} import selectors as sel
from app.bots.{nome}.schema import {Nome}Item

if TYPE_CHECKING:
    from playwright.sync_api import Frame, Page


def parse_result_table(page: "Page | Frame") -> list[{Nome}Item]:
    table = page.locator(sel.RESULT_TABLE).first
    if table.count() == 0:
        logger.debug("parse_result_table: tabela ausente")
        return []
    items = []
    # ... lógica de extração
    return items


def parse_error_message(page: "Page | Frame") -> str | None:
    loc = page.locator(sel.ERROR_MESSAGE)
    if loc.count() == 0:
        return None
    try:
        text = loc.first.inner_text().strip()
        return text or None
    except Exception:
        return None
```

### Passo 5 — Criar `bot.py`

```python
# app/bots/{nome}/bot.py
from __future__ import annotations
from typing import Any, ClassVar
from loguru import logger
from app.bots.{nome} import parsers
from app.bots.{nome} import selectors as sel
from app.bots.{nome}.schema import {Nome}InputRow, {Nome}Item, {Nome}Result
from app.core.base_bot import BaseBot
from app.core.browser import BrowserSession
from app.core.exceptions import AuthenticationError, NotFoundError, ParseError
from app.core.registry import register_bot
from app.utils.cpf import mask_cpf
from app.utils.dates import now_str


@register_bot
class {Nome}Bot(BaseBot):
    key: ClassVar[str] = "{nome}"                    # deve bater com config.json sistemas.{nome}
    display_name: ClassVar[str] = "{Nome Completo}"
    InputRowModel: ClassVar[type[{Nome}InputRow]] = {Nome}InputRow
    ResultModel: ClassVar[type[{Nome}Result]] = {Nome}Result

    def __init__(self, config) -> None:
        super().__init__(config)
        extras = self.system.extras or {}
        self._login_url: str = extras.get("login_url", "https://site.gov.br/login")

    def authenticate(self, session: BrowserSession) -> None:
        page = session.page
        page.goto(self._login_url, wait_until="domcontentloaded")
        page.fill(sel.LOGIN_INPUT, self.system.auth.email)
        page.fill(sel.SENHA_INPUT, self.system.auth.password.get_secret_value())
        page.click(sel.BTLOGIN)
        page.wait_for_load_state("networkidle", timeout=15_000)
        # Valide que o login foi bem-sucedido; raise AuthenticationError se não
        if sel.LOGIN_INPUT in page.url:
            raise AuthenticationError("Login falhou — verifique credenciais.")
        logger.info("{nome}: autenticado")

    def process_row(self, session: BrowserSession, row: {Nome}InputRow) -> {Nome}Result:
        page = session.page
        logger.info("{nome}: consultando linha {} ({})", row.row_index, mask_cpf(row.cpf))

        page.fill(sel.CPF_INPUT, row.cpf)
        page.click(sel.BTCONSULTA)
        try:
            page.wait_for_selector(f"{sel.RESULT_TABLE}, {sel.ERROR_MESSAGE}", timeout=15_000)
        except Exception as exc:
            raise ParseError(f"resultado não apareceu após consulta: {exc}") from exc

        error = parsers.parse_error_message(page)
        if error and sel.NO_INFO_TEXT.lower() in error.lower():
            raise NotFoundError(error)

        items = parsers.parse_result_table(page)
        return {Nome}Result(
            row_index=row.row_index, cpf=row.cpf, nome=row.nome,
            items=items, status_consulta="ok",
            observacao=error or ("" if items else "sem resultados"),
            data_consulta=now_str(),
        )

    def output_columns(self) -> list[str]:
        return ["CPF", "Nome", "Campo1", "Campo2", "Status Consulta", "Observacao", "Data Consulta"]

    def expand_result(self, result: {Nome}Result) -> list[dict[str, Any]]:
        base = {"CPF": result.cpf, "Nome": result.nome,
                "Status Consulta": result.status_consulta,
                "Observacao": result.observacao, "Data Consulta": result.data_consulta}
        if not result.items:
            return [{**base, "Campo1": "", "Campo2": ""}]
        return [{**base, "Campo1": i.campo1, "Campo2": i.campo2} for i in result.items]
```

### Passo 6 — Adicionar ao config.json

```json
{
  "sistemas": {
    "{nome}": {
      "name": "{Nome Completo}",
      "auth": {
        "email": "usuario@email.com",
        "password": "senha"
      },
      "extras": {
        "login_url": "https://site.gov.br/login"
      }
    }
  }
}
```

O bot é descoberto automaticamente pelo `BotRegistry.discover()` — nenhum import
manual necessário em código existente.

---

## Receita 2 — Novo campo no output

Adiciona uma nova coluna à planilha de saída de um bot existente.

### Passo 1 — Adicionar o campo ao schema

```python
# app/bots/valor/schema.py

class ValorContract(BaseModel):
    # ... campos existentes ...
    novo_campo: str = ""        # adicionar aqui
```

### Passo 2 — Popular o campo no parser

```python
# app/bots/valor/parsers.py

def parse_contracts_table(page):
    # ...
    contracts.append(ValorContract(
        contrato=contrato,
        parcelas=_cell(i, 4),
        status=_cell(i, 5).upper(),
        convenio=_cell(i, 6),
        novo_campo=_cell(i, 7),   # adicionar extração
        table_row=i,
    ))
```

### Passo 3 — Adicionar à lista de colunas

```python
# app/bots/valor/bot.py

def output_columns(self) -> list[str]:
    return [
        "CPF", "Nome", "Contrato", "Data Vencimento", "Parcelas",
        "Convenio", "Status Contrato",
        "Novo Campo",                    # adicionar aqui
        "Status Consulta", "Observacao", "Data Consulta",
    ]
```

### Passo 4 — Incluir no expand_result

```python
# app/bots/valor/bot.py

def expand_result(self, result: ValorResult) -> list[dict[str, Any]]:
    return [{
        # ... campos existentes ...
        "Novo Campo": c.novo_campo,      # adicionar aqui
        # ...
    } for c in result.contracts]
```

A ordem em `output_columns()` determina a ordem das colunas Excel.

---

## Receita 3 — Novo seletor

Adiciona um novo seletor CSS/XPath a um bot.

### Passo 1 — Adicionar em selectors.py

```python
# app/bots/valor/selectors.py

# === Nova seção ===
NOVO_BOTAO = "button#novoId"

# Seletor com múltiplos fallbacks (recomendado para elementos instáveis)
NOVO_BOTAO_ROBUSTO = (
    "button#novoId, "
    "button.nova-classe, "
    "xpath=//button[normalize-space()='Texto Visível']"
)

# Seletor dinâmico (função)
def cell_by_position(row: int, col: int) -> str:
    return f"#Grid_cell_{row}_{col}"
```

### Passo 2 — Usar no bot.py (navegação) ou parsers.py (extração)

```python
# Navegação — em bot.py
page.click(sel.NOVO_BOTAO)
page.wait_for_selector(sel.NOVO_BOTAO_ROBUSTO, state="visible", timeout=10_000)

# Extração — em parsers.py
valor = page.locator(sel.NOVO_BOTAO).inner_text().strip()
```

Regra: se é uma ação (click, fill, goto) → no bot.py. Se é leitura de dados → no parsers.py.

---

## Receita 4 — Debug de navegação

### Opção A — Debug mode via config.json

```json
{ "bot": { "debug": true, "headless": false } }
```

Com `debug=true` + `headless=false`:
- Navegador fica visível
- Playwright trace salvo em `checkpoint/{bot_key}/trace_*.zip`
- Screenshots de erro salvos em `checkpoint/screenshots/{bot_key}/`
- Checkpoint e screenshots limpos a cada run

Inspecionar trace:
```bash
poetry run playwright show-trace checkpoint/valor/trace_20240101_120000.zip
```

### Opção B — Screenshot manual no bot.py

```python
# Em bot.py, temporariamente para debug
from app.utils.screenshots import save_screenshot
save_screenshot(session.page, "meu_label", self._screenshots_dir)
```

Nota: `screenshots_dir` não é passado para o bot por padrão. Para debug pontual, use:
```python
from pathlib import Path
session.page.screenshot(path="/tmp/debug_shot.png", full_page=True)
```

### Opção C — Pause interativo

```python
# Em bot.py ou parsers.py, temporariamente
session.page.pause()   # abre Playwright Inspector (não funciona em headless)
```

### Opção D — Inspecionar elemento pelo console

```python
# Executar JS no contexto da página
result = session.page.evaluate("() => document.querySelector('#meuId')?.textContent")
print(result)

# Listar todos os frames
for frame in session.page.frames:
    print(frame.name, frame.url)
```

### Opção E — Aumentar timeouts para debug

```json
{
  "bot": {
    "timeout_selector_ms": 60000,
    "timeout_navigation_ms": 60000,
    "headless": false,
    "debug": true
  }
}
```

### Artefatos de diagnóstico automáticos

Em modo debug, `ValorBot._save_failure_artifacts()` (`app/bots/valor/bot.py:98`)
captura automaticamente URL, body snippet, screenshot PNG e HTML completo para qualquer
falha de autenticação ou timeout crítico. Adapte esse padrão para seus bots.

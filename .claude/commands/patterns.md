<!-- mustard:generated -->
# Patterns — consig-bot

Padrões recorrentes identificados no código com referências de arquivo:linha.

---

## 1. Criar um novo bot (BaseBot + @register_bot)

**Referência:** `app/bots/valor/bot.py:29-34`

```python
from app.core.base_bot import BaseBot
from app.core.registry import register_bot

@register_bot
class ValorBot(BaseBot):
    key: ClassVar[str] = "valor"           # identificador único, usado em config.json
    display_name: ClassVar[str] = "Valor Financiamentos"
    InputRowModel: ClassVar[type[ValorInputRow]] = ValorInputRow
    ResultModel: ClassVar[type[ValorResult]] = ValorResult
```

O decorator `@register_bot` (`app/core/registry.py:15`) insere a classe em `_BOTS[key]`.
`BotRegistry.discover()` (`app/core/registry.py:29`) importa automaticamente `app/bots/{nome}/bot.py`
via `pkgutil.iter_modules` — nenhum registro manual é necessário.

O bot precisa implementar quatro métodos:
- `authenticate(session)` — login; deixa sessão pronta para consultas
- `process_row(session, row)` — consulta uma linha; retorna instância de `ResultModel`
- `output_columns()` — lista ordenada de colunas Excel
- `expand_result(result)` — achata um Result em 1+ `dict[coluna, valor]`

---

## 2. Definir InputRow e Result (Pydantic v2)

**Referência:** `app/bots/valor/schema.py:14-43`

```python
# InputRow sempre herda de BaseInputRow
class ValorInputRow(BaseInputRow):   # BaseInputRow tem row_index + raw + extra="allow"
    cpf: str = ""
    nome: str = ""

    @field_validator("cpf", mode="before")
    @classmethod
    def _normalize(cls, v: object) -> str:
        return normalize_cpf(str(v) if v is not None else "")

# Modelos intermediários (dados scrapeados) são BaseModel simples
class ValorContract(BaseModel):
    model_config = ConfigDict(extra="ignore")
    contrato: str = ""
    parcelas: str = ""
    status: str = ""
    convenio: str = ""
    data_vencimento: str | None = None
    table_row: int = 0

# Result sempre inclui campos obrigatórios do Pipeline
class ValorResult(BaseModel):
    model_config = ConfigDict(extra="allow")
    row_index: int
    cpf: str = ""
    nome: str = ""
    contracts: list[ValorContract] = Field(default_factory=list)
    status_consulta: ValorStatus = "ok"   # Literal dos status válidos
    observacao: str = ""
    data_consulta: str = ""
```

`ValorStatus = Literal["ok", "nao_encontrado", "erro", "rate_limit", "captcha", "auth_error"]`
(`app/bots/valor/schema.py:11`) — use o mesmo Literal em todos os bots.

---

## 3. Como o Pipeline orquestra process_row

**Referência:** `app/core/pipeline.py:67-105`

```
Pipeline.run(rows)
  ├── filtra linhas já processadas via checkpoint.is_processed(row_index)
  ├── para cada row pendente:
  │   ├── _process_one(row) → captura exceções por tipo
  │   │   ├── NotFoundError       → status="nao_encontrado"
  │   │   ├── RateLimited         → status="rate_limit"
  │   │   ├── SessionExpired      → re-autentica, retry
  │   │   ├── CaptchaRequired     → status="captcha"
  │   │   ├── AuthenticationError → raise BotError (aborta run)
  │   │   └── Exception genérica  → status="erro" + screenshot debug
  │   ├── writer.append_result(result)
  │   ├── checkpoint.mark_done(row_index, status)
  │   └── time.sleep(delay_between_queries_seconds)
  └── retorna stats: dict[status, count]
```

`_process_one` (`app/core/pipeline.py:107`) usa `result_cls.model_validate({...})` para criar
resultados de erro sem instanciar o bot — sempre com campos mínimos `row_index, cpf, nome,
status_consulta, observacao, data_consulta`.

---

## 4. Como BrowserSession gerencia o Playwright

**Referência:** `app/core/browser.py:22-119`

```python
# Uso sempre como context manager
with BrowserSession(config.bot, trace_path=trace_path) as session:
    bot.authenticate(session)
    pipeline = Pipeline(bot, session, ...)
    pipeline.run(rows)
# __exit__ chama _cleanup(): fecha page → context → browser → playwright
```

Parâmetros configuráveis via `BotRuntimeConfig` (`app/models/config.py:27`):
- `headless`, `timeout_selector_ms`, `timeout_navigation_ms`
- `proxy.enabled/server/username/password`
- `debug` → ativa Playwright tracing (`context.tracing.start(...)`)

`session.page` (`app/core/browser.py:38`) é a única `Page` ativa. Para o MVP
não há multi-page; `new_page()` pode ser adicionado para concorrência futura.

---

## 5. Como ExcelWriter gera saída

**Referência:** `app/services/excel_writer.py:31-88`

```python
writer = ExcelWriter(output_dir, bot)
# Arquivo criado imediatamente com cabeçalho colorido

writer.append_result(result)
# Chama bot.expand_result(result) → list[dict]
# Aplica cor de fundo por status_consulta (_STATUS_FILL)
# Salva o arquivo a cada linha (streaming, tolerante a crash)

writer.close()
# Se rows_written == 0: remove arquivo vazio
# Senão: salva final e loga caminho
```

Cores de status (`app/services/excel_writer.py:19`): verde=ok, amarelo=nao_encontrado,
vermelho=erro, laranja=rate_limit, lilás=captcha, cinza=auth_error.

Colunas definidas por `bot.output_columns()`, ordem importa. Largura automática:
`max(14, min(40, len(nome_coluna) + 6))`.

---

## 6. Como CheckpointManager faz resume

**Referência:** `app/services/checkpoint.py:13-52`

```python
checkpoint = CheckpointManager(checkpoint_dir, bot.key)
# Lê checkpoint/{bot_key}/{bot_key}_checkpoint.csv na inicialização

checkpoint.is_processed(row_index)  # True se já processado
checkpoint.mark_done(row_index, status)  # Append ao CSV
checkpoint.processed_count()  # Quantidade já feita

# No Pipeline.run():
pending = [r for r in all_rows if not checkpoint.is_processed(r.row_index)]
```

CSV tem colunas `row_index, status, timestamp`. Em modo debug, o checkpoint é
deletado antes de cada run (`__main__.py:73-78`) para forçar reprocessamento completo.

---

## 7. Como os seletores CSS/XPath são centralizados

**Referência:** `app/bots/valor/selectors.py:1-61`

Todos os seletores são constantes de módulo (strings) ou funções simples:

```python
# Constante simples
LOGIN_INPUT = "input#login"

# Multi-fallback com XPath | CSS combinados
MENU_CONSULTA_SALDO = (
    "xpath=//a[normalize-space()='Consulta Saldo'] | "
    "//a[contains(., 'Consulta Saldo')] | "
    "//*[@id='menuConsultaSaldo']"
)

# Função geradora de seletores dinâmicos
def contract_cell_by_row(row: int) -> str:
    return f"#JTPlatinumGrid2_cell_{row}_0"
```

Importação no bot e nos parsers: `from app.bots.valor import selectors as sel`
Uso: `page.click(sel.BTLOGIN)`, `frame.locator(sel.CONTRACTS_TABLE)`

---

## 8. Como os parsers extraem dados do DOM

**Referência:** `app/bots/valor/parsers.py:15-90`

Parsers são **funções puras** que recebem `Page | Frame` e retornam dados Python.
Não navegam (sem `goto`, sem `click`), não têm estado, não usam `self`.

```python
# Padrão: recebe page/frame, usa seletores de selectors.py, retorna model/str/None
def parse_contracts_table(page: Page | Frame) -> list[ValorContract]:
    table = page.locator(sel.CONTRACTS_TABLE).first
    if table.count() == 0:
        return []
    # ... extração via locator e inner_text()

def parse_error_toast(page: Page | Frame) -> str | None:
    locator = page.locator(sel.ERROR_TOAST)
    # ... verifica visibilidade antes de ler texto

def parse_first_due_date(frame: Page | Frame) -> str | None:
    # Usa frame.evaluate(JS) quando estrutura DOM é complexa demais para locators
    result = frame.evaluate("""() => { ... }""")
```

Quando usar `frame.evaluate()`: estruturas dinâmicas carregadas por JS, percorrer
NodeLists complexas, ou quando múltiplos `locator()` seriam mais lentos.

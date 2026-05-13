<!-- mustard:generated -->
# Guards — consig-bot

Regras DO/DON'T específicas do projeto. Violações quebram padrões ou causam bugs silenciosos.

---

## Threading / Async

**NUNCA** use `asyncio`, `threading`, `concurrent.futures`, ou `async def` em código de bot.
Playwright sync API não é thread-safe e não suporta event loops aninhados.

```python
# DON'T
import asyncio
async def process_row(...): ...
threading.Thread(target=bot.process_row).start()

# DO
# Loop serial no Pipeline.run() — já implementado
# Para concorrência futura: multi-process com uma BrowserSession por processo
```

Referência: `app/core/browser.py:22` — `BrowserSession` usa `sync_playwright()`.

---

## Seletores CSS/XPath

**SEMPRE** centralize seletores em `selectors.py` do bot. Nunca hardcode strings de seletor
dentro de `bot.py` ou `parsers.py`.

```python
# DON'T (em bot.py ou parsers.py)
page.click("button.btlogin")
frame.locator("table#JTPlatinumGrid2_IntTable")

# DO (em selectors.py)
BTLOGIN = "button.btlogin"
CONTRACTS_TABLE = "table#JTPlatinumGrid2_IntTable, ..."

# Em bot.py/parsers.py:
from app.bots.valor import selectors as sel
page.click(sel.BTLOGIN)
frame.locator(sel.CONTRACTS_TABLE)
```

Referência: `app/bots/valor/selectors.py:1-61`, `app/bots/valor/bot.py:9-10`.

---

## Responsabilidades: parsers vs bot.py

**Parsers** (`parsers.py`): APENAS extraem dados do DOM. Proibido navegar (goto, click, fill).

```python
# DON'T (em parsers.py)
def parse_something(page):
    page.click(sel.SOME_BUTTON)   # navegação — proibida em parser
    page.goto("http://...")        # idem

# DO (em parsers.py)
def parse_something(page):
    return page.locator(sel.SELECTOR).inner_text().strip()
```

**bot.py** (`process_row`): orquestra navegação. **Não** faz extração direta de DOM —
delega para funções em `parsers.py`.

```python
# DON'T (em bot.py)
def process_row(self, session, row):
    text = session.page.locator("#JTPlatinumGrid2_cell_0_0").inner_text()  # parse inline

# DO (em bot.py)
def process_row(self, session, row):
    contracts = parsers.parse_contracts_table(frame)  # delega ao parser
```

Referência: `app/bots/valor/bot.py:132`, `app/bots/valor/parsers.py:15`.

---

## Tratamento de erros

Use a hierarquia de exceções de `app/core/exceptions.py`. Nunca lance `Exception` genérica
em código de bot — o Pipeline captura por tipo para decidir o status da linha.

| Exceção | Quando usar | Efeito no Pipeline |
|---------|-------------|-------------------|
| `NotFoundError` | Site diz "não há informações" (esperado) | status="nao_encontrado", continua |
| `ParseError` | DOM não tem a estrutura esperada | status="erro", screenshot debug |
| `SessionExpired` | Cookie expirou, precisa re-login | re-autentica automaticamente |
| `CaptchaRequired` | Captcha detectado na página | pausa para resolução manual |
| `RateLimited` | Site bloqueou temporariamente | status="rate_limit", continua |
| `AuthenticationError` | Login falhou definitivamente | ABORTA o run inteiro |
| `ConfigError` | config.json inválido | aborta na inicialização |

```python
# DON'T
raise Exception("tabela não encontrada")

# DO
raise ParseError(f"tabela de contratos ausente após 15s: {exc}")
```

Referência: `app/core/exceptions.py:1-38`, `app/core/pipeline.py:107-165`.

---

## ResultModel — campos obrigatórios

Todo `ResultModel` (subclasse de `BaseModel` usada como `bot.ResultModel`) **DEVE** ter:
- `row_index: int`
- `cpf: str`
- `nome: str`
- `status_consulta` — string ou Literal (Pipeline usa `getattr(result, "status_consulta", "ok")`)
- `observacao: str`
- `data_consulta: str`

O Pipeline constrói resultados de erro via `result_cls.model_validate({...})` com esses campos
(`app/core/pipeline.py:115-119`). Se faltar qualquer campo, a validação falha em runtime.

---

## Naming conventions

| Elemento | Convenção | Exemplo |
|----------|-----------|---------|
| Bot class | `{Nome}Bot` (PascalCase) | `ValorBot`, `FgtsBot` |
| Bot key | snake_case curto, sem hífens | `"valor"`, `"fgts_cef"` |
| Seletores | UPPER_SNAKE_CASE | `BTLOGIN`, `CONTRACTS_TABLE` |
| Parsers | `parse_{o_que_extrai}` | `parse_contracts_table`, `parse_error_toast` |
| Schema models | `{Nome}InputRow`, `{Nome}Result`, `{Nome}Contract` | `ValorInputRow`, `ValorResult` |
| Status values | snake_case, consistente com Literal | `"nao_encontrado"`, `"rate_limit"` |
| Output columns | Português, Title Case, espaços | `"CPF"`, `"Data Vencimento"`, `"Status Consulta"` |

---

## config.json — chave do sistema

A chave do sistema em `config.json` (`sistemas.{chave}`) **deve ser idêntica** a `bot.key`.
O construtor de `BaseBot` valida isso explicitamente (`app/core/base_bot.py:29`).

```json
// config.json
{
  "sistemas": {
    "valor": { ... }   // deve bater com ValorBot.key = "valor"
  }
}
```

---

## Extras do sistema

Use `system.extras: dict[str, Any]` para configurações específicas do bot que não fazem parte
do schema global. Nunca adicione campos ao `SystemConfig` global — use extras.

```json
"extras": {
  "login_url": "https://...",
  "valid_status": ["DEFERIDO"],
  "ignore_status": ["FINALIZADO", "CANCELADO"]
}
```

Referência: `app/models/config.py:76`, `app/bots/valor/bot.py:39-54`.

---

## Debug mode

Em `config.bot.debug = true`:
- Checkpoint e screenshots são **limpos** antes de cada run
- Playwright tracing é ativado (`.zip` em `checkpoint/{bot_key}/trace_*.zip`)
- Screenshots são salvos em `checkpoint/screenshots/{bot_key}/` para erros
- Logs detalhados aparecem no console

**NUNCA** commite `config.json` com `debug: true` — é para desenvolvimento local apenas.

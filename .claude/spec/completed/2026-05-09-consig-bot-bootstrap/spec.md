# Feature: Consig Bot — Multi-Bot Automation System (Bootstrap + Valor)

### Status: completed | Phase: CLOSE | Scope: full
### Checkpoint: 2026-05-09T00:00:00Z

## Summary

Bootstrap de um sistema desktop Python (terminal Windows) chamado **Consig Bot** para automação de consultas web via Playwright. Arquitetura modular **multi-bot** (Strategy Pattern + Service Layer + Bot Registry) preparada para adicionar novos sistemas com baixo atrito. Inclui implementação completa do primeiro bot — **Valor Financiamentos** — com login, consulta de saldo por CPF, extração de contratos DEFERIDOS e captura da primeira data de vencimento via modal.

**Por quê:** o projeto antigo `lemit-bot` é monolítico e single-bot. O Consig Bot precisa suportar N sistemas (Valor, BIB, futuros) com isolamento total entre regras de negócio, seletores e parsers — sem reescrever a infraestrutura a cada novo sistema.

## Boundaries

- `app/**` — todo o código-fonte da aplicação (criar do zero)
- `main.py` — entrypoint top-level (criar)
- `pyproject.toml`, `requirements.txt` — gerenciamento de dependências (criar)
- `config.example.json` — atualizar template existente
- `.gitignore` — atualizar para incluir `config.json`, `.venv/`, `entrada/*.xlsx`, `saida/`, `logs/`, `checkpoint/`
- `entrada/`, `saida/valor/`, `logs/`, `checkpoint/screenshots/` — placeholders com `.gitkeep`
- `README.md` — instruções de uso Windows (criar)
- `pyinstaller.spec` — template para empacotamento futuro (criar, mas não buildar)
- **Fora do escopo:** bot BIB (apenas placeholder de config), solver automático de captcha (apenas interface), suporte a proxies (apenas tipo de config), workers paralelos (apenas hooks na arquitetura), CI/CD

## Entity Info

Não há `entity-registry.json` populado (projeto greenfield). As entidades-chave criadas neste pipeline:

| Entidade | Camada | Papel |
|----------|--------|-------|
| `BaseBot` | core | ABC — contrato Strategy de cada sistema |
| `BotRegistry` | core | Discovery e lookup por `key` |
| `Pipeline` | core | Orquestração genérica (read → for-each → write) |
| `BrowserSession` | core | Wrapper Playwright (ciclo de vida) |
| `AppConfig` | models | Pydantic root config (bot + sistemas) |
| `InputRow` / `QueryResult` | models | DTOs base + subclasses por bot |
| `ExcelReader` / `ExcelWriter` | services | I/O com pandas + openpyxl |
| `CheckpointManager` | services | Resume de execuções interrompidas |
| `CaptchaSolver` | services | Interface (default: `ManualCaptcha`) |
| `ValorBot` | bots/valor | Implementação concreta do BaseBot |

## Architecture

### Padrões de projeto utilizados

| Padrão | Onde | Por quê |
|--------|------|---------|
| **Strategy** | `BaseBot` + concretos | Cada sistema implementa `authenticate` + `process_row` |
| **Registry** | `BotRegistry` | Discovery automática de bots via import de `app.bots.*` |
| **Template Method** | `BaseBot.run()` | Esqueleto comum (login → loop → cleanup); hooks abstratos |
| **Factory** | `BotRegistry.create(key, ...)` | Instanciação com injeção de dependências |
| **Service Layer** | `services/` | Excel I/O, Checkpoint, Captcha, Proxy isolados de regras de negócio |
| **DTO** | `models/` (Pydantic) | Validação forte na fronteira (config, input, output) |
| **State Machine** | `PageState` enum | FOUND / NOT_FOUND / CAPTCHA / SESSION_EXPIRED / RATE_LIMITED / ERROR |
| **Context Manager** | `BrowserSession.__enter__` | Garantia de cleanup do Playwright |
| **Decorator (retry)** | `core/retry.py` | Backoff exponencial reutilizável |
| **Adapter** | `CaptchaSolver` | Permite trocar manual ↔ 2Captcha/Anti-Captcha sem mudar bots |

### Stack final (justificada)

| Lib | Versão | Justificativa |
|-----|--------|---------------|
| Python | `>=3.12,<3.13` | Match types (`X \| Y`), `TypeAliasType`, perf |
| Playwright | `~=1.48` | Headless Chromium, robusto contra anti-bot leve |
| Pydantic | `~=2.9` | v2 com `model_validate`, `Field(default_factory=...)`, performance |
| Loguru | `~=0.7` | Sinks múltiplos, rotação, formatação rica out-of-box |
| Rich | `~=13.9` | `Progress`, `Panel`, `Table`, `Prompt` no terminal |
| pandas | `~=2.2` | Leitura robusta de `.xlsx` heterogêneos |
| openpyxl | `~=3.1` | Escrita célula-a-célula com estilos |
| python-dotenv | `~=1.0` | Override opcional de credenciais via `.env` (segurança) |
| **Dependency manager** | **Poetry** | Lockfile reprodutível, comando `poetry install` familiar no Windows |

> Decisão: **Poetry** sobre **uv**. Razão: ambiente Windows do usuário, ecossistema mais maduro para empacotamento `.exe` posterior, `pyproject.toml` único como source of truth.

### Estrutura de pastas (final)

```
consig-bot/
├── app/
│   ├── __init__.py
│   ├── cli/
│   │   ├── __init__.py
│   │   ├── menu.py              # Rich-based seleção de sistema + arquivo de entrada
│   │   └── progress.py          # Wrapper Rich Progress + suspend ctx (captcha/2FA)
│   ├── core/
│   │   ├── __init__.py
│   │   ├── base_bot.py          # ABC BaseBot
│   │   ├── browser.py           # BrowserSession (Playwright lifecycle)
│   │   ├── exceptions.py        # BotError + subclasses
│   │   ├── page_state.py        # Enum PageState
│   │   ├── pipeline.py          # Orchestrator genérico
│   │   ├── registry.py          # BotRegistry com decorator @register_bot
│   │   └── retry.py             # retry com backoff
│   ├── models/
│   │   ├── __init__.py
│   │   ├── config.py            # AppConfig, BotRuntimeConfig, SystemConfig (Pydantic)
│   │   ├── input_row.py         # BaseInputRow
│   │   └── result.py            # BaseQueryResult
│   ├── services/
│   │   ├── __init__.py
│   │   ├── captcha_solver.py    # CaptchaSolver ABC + ManualCaptcha
│   │   ├── checkpoint.py        # CheckpointManager (CSV-backed)
│   │   ├── excel_reader.py      # ExcelReader (pandas)
│   │   ├── excel_writer.py      # ExcelWriter (openpyxl, streaming append)
│   │   └── proxy_provider.py    # ProxyProvider ABC + NoProxyProvider
│   ├── utils/
│   │   ├── __init__.py
│   │   ├── cpf.py               # normalize_cpf, mask_cpf, is_valid_cpf
│   │   ├── dates.py             # now_str, parse_br_date
│   │   ├── logger.py            # configure_loguru()
│   │   ├── paths.py             # get_app_root() (PyInstaller-aware)
│   │   └── screenshots.py       # save_screenshot helper
│   ├── bots/
│   │   ├── __init__.py
│   │   └── valor/
│   │       ├── __init__.py
│   │       ├── bot.py           # @register_bot('valor') class ValorBot(BaseBot)
│   │       ├── parsers.py       # parse_contracts_table, parse_first_due_date_modal
│   │       ├── schema.py        # ValorInputRow, ValorResult (Pydantic)
│   │       └── selectors.py     # CSS/XPath constants
│   └── __main__.py              # python -m app
├── entrada/
│   └── .gitkeep
├── saida/
│   └── valor/
│       └── .gitkeep
├── logs/
│   └── .gitkeep
├── checkpoint/
│   ├── .gitkeep
│   └── screenshots/
│       └── .gitkeep
├── config.example.json
├── config.json                  # gitignored (criado pelo usuário)
├── pyproject.toml
├── requirements.txt             # gerado por `poetry export` para compatibilidade
├── pyinstaller.spec             # template (não buildado neste pipeline)
├── main.py                      # wrapper fino: from app.__main__ import run; run()
├── executar.bat                 # atalho Windows: poetry run python main.py
├── README.md
└── .gitignore
```

### Fluxo da aplicação (textual)

```
main.py
  └─> app.__main__.run()
        ├─ utils.logger.configure_loguru()         # Loguru: console (Rich) + file rotated
        ├─ AppConfig.load(Path("config.json"))    # Pydantic valida tudo de uma vez
        ├─ BotRegistry.discover()                 # importa app.bots.* para popular registry
        ├─ cli.menu.select_bot(registry, config)  # Rich Prompt
        ├─ cli.menu.select_input_file(entrada/)   # Rich Prompt — lista *.xlsx
        ├─ bot = registry.create(key, config)
        ├─ rows = ExcelReader(input_path, bot).read()
        ├─ writer = ExcelWriter(saida/{key}/, bot)
        ├─ checkpoint = CheckpointManager(checkpoint/{key}/)
        ├─ with BrowserSession(config.bot.headless) as session:
        │     bot.authenticate(session)            # login + captcha manual
        │     Pipeline(bot, session, writer, checkpoint).run(rows)
        └─ writer.close() + log resumo (Rich Panel)
```

## Configuration (Pydantic — schema final)

```python
# app/models/config.py (resumo)

class ProxyConfig(BaseModel):
    enabled: bool = False
    server: str | None = None        # "http://host:port"
    username: str | None = None
    password: SecretStr | None = None

class CaptchaConfig(BaseModel):
    mode: Literal["manual", "2captcha", "anti-captcha"] = "manual"
    api_key: SecretStr | None = None

class BotRuntimeConfig(BaseModel):
    headless: bool = True
    delay_between_queries_seconds: float = Field(1.0, ge=0)
    max_retries: int = Field(2, ge=0, le=10)
    max_rows: int | None = Field(None, ge=1)
    input_folder: str = "entrada"
    output_folder: str = "saida"
    timeout_navigation_ms: int = 30_000
    timeout_selector_ms: int = 15_000
    proxy: ProxyConfig = Field(default_factory=ProxyConfig)
    captcha: CaptchaConfig = Field(default_factory=CaptchaConfig)

class SystemAuthConfig(BaseModel):
    email: str
    password: SecretStr
    @field_validator('email', 'password', mode='after')
    @classmethod
    def reject_placeholder(cls, v): ...   # bloqueia 'usuario@email.com' / 'senha'

class SystemExcelConfig(BaseModel):
    cpf_column: str = "cpf"
    name_column: str = "nome"

class SystemConfig(BaseModel):
    name: str
    auth: SystemAuthConfig
    excel: SystemExcelConfig
    extras: dict[str, Any] = Field(default_factory=dict)  # config extra por sistema

class AppConfig(BaseModel):
    bot: BotRuntimeConfig
    sistemas: dict[str, SystemConfig]

    @classmethod
    def load(cls, path: Path) -> "AppConfig": ...   # JSON → Pydantic + validação
```

**Melhorias propostas no `config.example.json`:**

```jsonc
{
  "bot": {
    "headless": true,
    "delay_between_queries_seconds": 1,
    "max_retries": 2,
    "max_rows": null,
    "input_folder": "entrada",
    "output_folder": "saida",
    "timeout_navigation_ms": 30000,
    "timeout_selector_ms": 15000,
    "proxy": { "enabled": false, "server": null, "username": null, "password": null },
    "captcha": { "mode": "manual", "api_key": null }
  },
  "sistemas": {
    "valor": {
      "name": "Valor Financiamentos",
      "auth": { "email": "usuario@email.com", "password": "senha" },
      "excel": { "cpf_column": "cpf", "name_column": "nome" },
      "extras": {
        "login_url": "https://www.valorscm.com.br/webagente+/index.php",
        "dashboard_url": "https://www.valorscm.com.br/webagente+/dashboard.php",
        "valid_status": ["DEFERIDO"],
        "ignore_status": ["FINALIZADO", "CANCELADO"]
      }
    },
    "bib": {
      "name": "BIB",
      "auth": { "email": "usuario@email.com", "password": "senha" },
      "excel": { "cpf_column": "cpf", "name_column": "nome" },
      "extras": {}
    }
  }
}
```

> `extras` permite cada bot guardar URLs, regras de status e flags sem modificar o schema raiz — princípio Open/Closed.

## DTOs / Models

```python
# app/models/input_row.py
class BaseInputRow(BaseModel):
    row_index: int
    raw: dict[str, Any] = Field(default_factory=dict)

# app/bots/valor/schema.py
class ValorInputRow(BaseInputRow):
    cpf: str
    nome: str

class ValorContract(BaseModel):
    contrato: str
    parcelas: str
    status: str
    convenio: str
    data_vencimento: str | None = None

class ValorResult(BaseModel):
    row_index: int
    cpf: str
    nome: str
    contracts: list[ValorContract] = Field(default_factory=list)
    status_consulta: Literal["ok", "nao_encontrado", "erro", "rate_limit", "captcha"]
    observacao: str = ""
    data_consulta: str
    # achatamento para Excel: o ExcelWriter expande contracts em N linhas (1 por contrato)
```

> **Estratégia de saída multi-linha:** quando um CPF tem N contratos DEFERIDOS, o writer emite N linhas no Excel — uma por contrato — todas com `cpf`/`nome` repetidos. CPFs sem contrato válido geram 1 linha com `status_consulta`/`observacao` preenchidos.

## Logging (Loguru)

```python
# app/utils/logger.py — pseudocódigo
configure_loguru():
    logger.remove()
    logger.add(sys.stderr, level="INFO",
               format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | {message}")
    logger.add(LOG_DIR / "consig-bot_{time:YYYY-MM-DD}.log",
               rotation="10 MB", retention="14 days", compression="zip",
               level="DEBUG", enqueue=True)
    logger.add(LOG_DIR / "errors_{time:YYYY-MM-DD}.log",
               level="ERROR", rotation="10 MB", retention="30 days")
```

- `enqueue=True` — thread-safe, prepara terreno para concorrência futura
- Sink separado para `ERROR+` facilita diagnóstico
- Console usa formato curto; arquivo usa formato verbose com `{name}:{function}:{line}`
- CPF/senhas mascarados via `utils/cpf.py:mask_cpf` e nunca logados em texto puro

## Error Handling Strategy

```python
# app/core/exceptions.py
class BotError(Exception): ...
class ConfigError(BotError): ...
class AuthenticationError(BotError): ...
class CaptchaRequired(BotError): ...
class SessionExpired(BotError): ...
class RateLimited(BotError): ...
class NotFoundError(BotError): ...        # "Não existe informações para o CPF"
class ParseError(BotError): ...
class NavigationTimeout(BotError): ...
```

**Fluxo por tipo:**

| Erro | Ação no `Pipeline` |
|------|-------------------|
| `NotFoundError` | Resultado com `status_consulta="nao_encontrado"`, segue próxima linha |
| `RateLimited` | Backoff config × 2; após 3× → marca linha + segue |
| `SessionExpired` | Suspende Progress, chama `bot.authenticate` novamente, retry da linha |
| `CaptchaRequired` | Suspende Progress, delega ao `CaptchaSolver`, retry da linha |
| `NavigationTimeout` | Retry até `max_retries`; depois marca como `erro` |
| `ParseError` | Marca como `erro` + screenshot, segue próxima linha |
| `Exception` (qualquer outra) | Screenshot + log `ERROR` com stack + marca `erro`, segue |

**Checkpoint:** após cada linha processada, escreve `{row_index, status}` em `checkpoint/{key}/checkpoint.csv`. Reexecução pula linhas já processadas (skip-list). Comando manual: deletar checkpoint para reprocessar tudo.

**Screenshots:** salvos em `checkpoint/screenshots/{key}/{row_index}_{label}_{ts}.png` em todo erro + em pontos de interesse (login, antes/depois de consulta).

## Playwright Strategy

```python
# app/core/browser.py — esqueleto
class BrowserSession:
    def __init__(self, config: BotRuntimeConfig): ...
    def __enter__(self):
        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch(
            headless=self.config.headless,
            proxy=self._proxy_args(),
            args=["--disable-blink-features=AutomationControlled"],
        )
        self._context = self._browser.new_context(
            viewport={"width": 1366, "height": 768},
            locale="pt-BR",
            user_agent=DEFAULT_UA,
        )
        self._context.set_default_timeout(self.config.timeout_selector_ms)
        self._context.set_default_navigation_timeout(self.config.timeout_navigation_ms)
        self.page = self._context.new_page()
        return self
    def __exit__(self, *exc): self._cleanup()
```

- **Browser único, page única** no MVP — multi-page será habilitado em Wave futura
- Timeouts configuráveis no `config.json`
- User-Agent realista + flag anti-detect leve
- Cookies/storage persistem dentro do mesmo run (mas não entre runs — login a cada execução, intencional para segurança)
- **Captcha:** detecta `iframe[src*="recaptcha"]`; chama `CaptchaSolver.solve(page, reason)` que **bloqueia até o usuário resolver no navegador** (no modo `manual` → `Prompt.ask("Pressione Enter quando resolver...")`)

## BaseBot Contract

```python
# app/core/base_bot.py
class BaseBot(ABC):
    key: ClassVar[str]                     # "valor"
    display_name: ClassVar[str]            # "Valor Financiamentos"
    InputRowModel: ClassVar[type[BaseInputRow]]
    ResultModel: ClassVar[type[BaseModel]]

    def __init__(self, config: AppConfig): ...

    @abstractmethod
    def authenticate(self, session: BrowserSession) -> None: ...

    @abstractmethod
    def process_row(self, session: BrowserSession, row: BaseInputRow) -> BaseModel: ...

    @abstractmethod
    def output_columns(self) -> list[str]: ...

    @abstractmethod
    def expand_result(self, result: BaseModel) -> list[dict[str, Any]]:
        """Achata 1 result em 1+ linhas Excel (multi-linha para multi-contrato)."""
```

**Registry decorator:**

```python
# app/core/registry.py
_BOTS: dict[str, type[BaseBot]] = {}

def register_bot(cls): _BOTS[cls.key] = cls; return cls

class BotRegistry:
    @staticmethod
    def discover() -> None:
        # importa todos os submódulos de app.bots para acionar @register_bot
        for m in pkgutil.iter_modules(app.bots.__path__): importlib.import_module(...)
    @staticmethod
    def list_available(config: AppConfig) -> list[type[BaseBot]]: ...
    @staticmethod
    def create(key: str, config: AppConfig) -> BaseBot: ...
```

## Valor Bot — implementação detalhada

### Login

1. `page.goto(extras.dashboard_url)` (atalho fora-de-horário)
2. Detecta se foi redirecionado a `index.php` → preenche `input#login`, `input#senha`, clica `button.btlogin`
3. Detecta `iframe[src*="recaptcha"]` → `CaptchaSolver.solve(...)` (manual no MVP)
4. Aguarda dashboard carregar (selector âncora a confirmar em runtime — fallback: `wait_for_url('**/dashboard.php')`)
5. Em falha: `AuthenticationError` com screenshot

### Consulta Saldo (por linha)

1. Localiza menu **Consulta Saldo** no sidebar (XPath por texto)
2. Preenche `input#cssenha` com a senha do usuário (config)
3. Clica `button#btconsultasaldo`
4. Aguarda renderização da tabela de contratos
5. Detecta toast **"Não existe informações para o CPF"** → `NotFoundError`
6. Detecta toasts/alerts genéricos → captura texto, retorna como `observacao`

### Extração de contratos

`parsers.parse_contracts_table(page) -> list[ValorContract]`:
- Lê linhas `<tr>` da tabela de contratos
- Mapeia colunas: Contrato, Parcelas, Status, Convênio
- **Filtra:** mantém apenas `status == "DEFERIDO"`; descarta `FINALIZADO`, `CANCELADO`, outros
- Retorna lista vazia se nenhum contrato válido (gera 1 linha com `status_consulta="nao_encontrado"` no Excel)

### Data de vencimento (modal)

Para cada contrato DEFERIDO:
1. Clica na linha do contrato (locator parametrizado)
2. Aguarda modal abrir (selector `.modal.show, [role="dialog"]`)
3. `parsers.parse_first_due_date_modal(modal) -> str | None`:
   - Localiza tabela de parcelas dentro do modal
   - Extrai a **primeira** data de vencimento disponível (formato `dd/mm/aaaa`)
4. Fecha modal (botão de fechar OU `Escape`)
5. Atribui `contract.data_vencimento`

> **Nota crítica:** os seletores do modal e da tabela serão **ajustados em runtime** durante o smoke test. O spec define a estrutura; valores literais ficam em `selectors.py` para fácil iteração.

### Excel final (Valor)

Colunas: `CPF | Nome | Contrato | Data Vencimento | Parcelas | Convenio | Status Consulta | Observacao | Data Consulta`

Estilos: cabeçalho azul/branco bold, freeze pane A2, `status_consulta` colore a linha (verde / amarelo / vermelho / cinza).

## Tasks (organizadas por wave)

### Wave 1 — Foundation (parallel-safe)

#### Task 1.1 — Project skeleton & deps
- [x] Criar `pyproject.toml` (Poetry) com deps pinadas: `python>=3.12,<3.13`, `playwright~=1.48`, `pydantic~=2.9`, `loguru~=0.7`, `rich~=13.9`, `pandas~=2.2`, `openpyxl~=3.1`, `python-dotenv~=1.0`
- [x] Adicionar dev-deps: `ruff`, `mypy`, `pytest`, `pyinstaller`
- [x] Configurar `[tool.ruff]` (line-length 100, regras E/F/I/UP/B), `[tool.mypy]` (strict)
- [x] Gerar `requirements.txt` (lista plana — usuário pode regenerar via `poetry export`)
- [x] Atualizar `.gitignore`
- [x] Criar `.gitkeep` em `entrada/`, `saida/valor/`, `logs/`, `checkpoint/`, `checkpoint/screenshots/`

#### Task 1.2 — Utils + Loguru
- [x] `app/utils/paths.py`: `get_app_root()` (PyInstaller-aware: `sys.frozen` ou `Path(__file__).parents[2]`)
- [x] `app/utils/cpf.py`: `normalize_cpf`, `mask_cpf`, `is_valid_cpf` (digit-only + checksum)
- [x] `app/utils/dates.py`: `now_str`, `now_filename_ts`, `parse_br_date`
- [x] `app/utils/logger.py`: `configure_loguru()` com 3 sinks (console colorido, file rotated, errors)
- [x] `app/utils/screenshots.py`: `save_screenshot(page, label, dir)` com timestamp

#### Task 1.3 — Models (Pydantic) + Exceptions + PageState
- [x] `app/models/config.py`: schemas Pydantic (vide seção Configuration). `AppConfig.load(path)` com `model_validate`
- [x] `app/models/input_row.py`: `BaseInputRow`
- [x] `app/models/result.py`: `BaseQueryResult`
- [x] `app/core/exceptions.py`: hierarquia `BotError`
- [x] `app/core/page_state.py`: enum `PageState`
- [x] Atualizar `config.example.json` com schema enriquecido (timeouts, proxy, captcha, extras)

### Wave 2 — Core Infra (depende da Wave 1)

#### Task 2.1 — Browser + Retry
- [x] `app/core/browser.py`: `BrowserSession` context manager
- [x] `app/core/retry.py`: decorator `@retry(max_attempts, backoff, on=(NavigationTimeout, RateLimited))`

#### Task 2.2 — Services (Excel, Checkpoint, Captcha, Proxy)
- [x] `app/services/excel_reader.py`: lê `.xlsx`, normaliza cabeçalhos, valida colunas requeridas, retorna `list[BaseInputRow]`
- [x] `app/services/excel_writer.py`: cria arquivo `resultado_{key}_{ts}.xlsx`, header estilizado, append streaming com pintura por status
- [x] `app/services/checkpoint.py`: `CheckpointManager` baseado em CSV
- [x] `app/services/captcha_solver.py`: ABC + `ManualCaptcha`
- [x] `app/services/proxy_provider.py`: ABC + `NoProxyProvider` + `StaticProxyProvider`

#### Task 2.3 — BaseBot + Registry + Pipeline
- [x] `app/core/base_bot.py`: ABC com 4 métodos abstratos
- [x] `app/core/registry.py`: `@register_bot` decorator + `BotRegistry.discover/list_available/create`
- [x] `app/core/pipeline.py`: `Pipeline.run(rows)` — Rich Progress, captura de exceções tipadas, append no writer + checkpoint após cada linha

#### Task 2.4 — CLI + Entrypoint
- [x] `app/cli/menu.py`: `select_bot`, `select_input_file`, `confirm`, `show_banner`
- [x] `app/cli/progress.py`: `make_progress()` + `suspend_progress(reason)`
- [x] `app/__main__.py`: função `run()` orquestrando o fluxo
- [x] `main.py` (raiz): wrapper
- [x] `executar.bat`: atalho Windows
- [x] `app/bots/__init__.py`: package marker

### Wave 3 — Valor Bot (depende da Wave 2)

#### Task 3.1 — Valor schema + selectors + parsers
- [x] `app/bots/valor/schema.py`: `ValorInputRow`, `ValorContract`, `ValorResult`
- [x] `app/bots/valor/selectors.py`: constantes nomeadas
- [x] `app/bots/valor/parsers.py`: `parse_contracts_table`, `parse_first_due_date_modal`, `parse_error_toast`

#### Task 3.2 — Valor bot
- [x] `app/bots/valor/bot.py`:
  - [x] `@register_bot` + classe `ValorBot(BaseBot)`
  - [x] `authenticate(session)`: dashboard direto → fallback login → captcha manual
  - [x] `process_row(session, row)`: menu → CPF/senha → toast NotFound → tabela → filtro DEFERIDO → modal data
  - [x] `output_columns()` e `expand_result()` (multi-linha por contrato)

### Wave 4 — Polish (depende da Wave 3)

#### Task 4.1 — Docs + packaging prep
- [x] `README.md`: pré-requisitos, instalação, configuração, execução, troubleshooting, roadmap, segurança
- [x] `pyinstaller.spec`: template com `collect_all('playwright')` + descoberta dinâmica de bots
- [x] Documentar fluxo de empacotamento (template criado, build deferido)

#### Task 4.2 — Smoke validation
- [x] **Sintaxe estática** — `python3 -m ast` em todos os 35 arquivos `app/**/*.py` → OK
- [ ] `mypy app` (zero erros, modo strict) — **pendente runtime do usuário** (`poetry install` + `poetry run mypy app`)
- [ ] `ruff check app` (zero erros) — **pendente runtime do usuário**
- [ ] **Smoke manual com Valor** — **pendente runtime do usuário**: orientação completa no README; seletores podem precisar tuning na primeira execução real

## Dependencies between waves

- Wave 1 paraleliza Tasks 1.1, 1.2, 1.3 (sem dependência entre si)
- Wave 2 depende inteiramente de Wave 1; Tasks 2.1, 2.2 paralelizam; 2.3 depende de 2.1+2.2; 2.4 depende de 2.3
- Wave 3 depende de Wave 2 (BaseBot, Pipeline, Browser)
- Wave 4 depende de Wave 3 (README documenta o uso completo)

## Roadmap (futuro — fora deste pipeline)

| Versão | Entregas |
|--------|----------|
| **v0.1 (este pipeline)** | Bootstrap completo + Valor bot funcional + docs |
| v0.2 | Bot BIB (clone do esqueleto Valor com regras próprias) |
| v0.3 | Solver automático de captcha (`2CaptchaSolver` integrado ao adapter) |
| v0.4 | Proxies rotativos (`StaticProxyProvider` por sistema, ou pool round-robin) |
| v0.5 | Concorrência: `Pipeline(concurrency=N)` com `BrowserContext` por worker, fila `queue.Queue` produtor/consumidor |
| v0.6 | Build `.exe` automatizado (`build.bat` → `pyinstaller consig-bot.spec`) e instalador NSIS |
| v0.7 | Telemetria local (SQLite com runs históricos, dashboard Rich-Table) |

## Security Suggestions

- `config.json` no `.gitignore` (já previsto)
- Senhas como `SecretStr` (Pydantic) — nunca aparecem em `repr()` nem em logs serializados
- Suporte a `.env` opcional: `VALOR_PASSWORD` sobrescreve `sistemas.valor.auth.password` se presente (via `python-dotenv`)
- Logs não imprimem CPF nem senha sem máscara (`mask_cpf`)
- Screenshots salvos em pasta `checkpoint/` (gitignored)
- `.gitignore` cobre `entrada/*.xlsx` para evitar vazamento acidental de PII
- Considerar `keyring` (Windows Credential Manager) para senhas em release futura

## Concerns

- **Seletores do site Valor não foram validados em runtime** — o spec confia nas instruções do usuário (`input#login`, `input#senha`, `button.btlogin`, `input#cssenha`, `button#btconsultasaldo`). Os seletores da tabela de contratos, da linha clicável e do modal de parcelas precisarão de ajuste fino no smoke test. O design isola isso em `selectors.py` para iteração rápida sem tocar lógica.
- **reCAPTCHA invisível vs visível** — assumindo invisible reCAPTCHA: se for v2 visível, o `ManualCaptcha` ainda funciona (usuário resolve no browser); se for hCaptcha ou Cloudflare Turnstile o adapter precisa ser estendido (não previsto neste pipeline).
- **Anti-bot do site** — não temos visibilidade. Adicionei flag `--disable-blink-features=AutomationControlled` e UA realista; se houver bloqueio mais sofisticado pode requerer Playwright stealth (fora do escopo).
- **Multi-linha no Excel para multi-contrato** — decisão de design (1 linha por contrato vs 1 linha com contratos serializados em JSON). Spec adota multi-linha por ser mais útil ao usuário final. Confirmar antes de implementar.
- **Loguru + Rich** — Loguru não usa `RichHandler` por padrão; para console colorido sem conflito usaremos format customizado de Loguru. Aceitável.
- **Concorrência futura** — quando habilitar `concurrency>1`, o login compartilhado fica complicado (uma sessão única) — a v0.5 provavelmente exigirá login por contexto. O design atual não impede, mas registra a fricção.

## Files (~38)

```
pyproject.toml                                (create)
requirements.txt                              (create)
.gitignore                                    (modify)
config.example.json                           (modify)
README.md                                     (create)
pyinstaller.spec                              (create)
main.py                                       (create)
executar.bat                                  (create)
app/__init__.py                               (create)
app/__main__.py                               (create)
app/cli/__init__.py                           (create)
app/cli/menu.py                               (create)
app/cli/progress.py                           (create)
app/core/__init__.py                          (create)
app/core/base_bot.py                          (create)
app/core/browser.py                           (create)
app/core/exceptions.py                        (create)
app/core/page_state.py                        (create)
app/core/pipeline.py                          (create)
app/core/registry.py                          (create)
app/core/retry.py                             (create)
app/models/__init__.py                        (create)
app/models/config.py                          (create)
app/models/input_row.py                       (create)
app/models/result.py                          (create)
app/services/__init__.py                      (create)
app/services/captcha_solver.py                (create)
app/services/checkpoint.py                    (create)
app/services/excel_reader.py                  (create)
app/services/excel_writer.py                  (create)
app/services/proxy_provider.py                (create)
app/utils/__init__.py                         (create)
app/utils/cpf.py                              (create)
app/utils/dates.py                            (create)
app/utils/logger.py                           (create)
app/utils/paths.py                            (create)
app/utils/screenshots.py                      (create)
app/bots/__init__.py                          (create)
app/bots/valor/__init__.py                    (create)
app/bots/valor/bot.py                         (create)
app/bots/valor/parsers.py                     (create)
app/bots/valor/schema.py                      (create)
app/bots/valor/selectors.py                   (create)
entrada/.gitkeep                              (create)
saida/valor/.gitkeep                          (create)
logs/.gitkeep                                 (create)
checkpoint/.gitkeep                           (create)
checkpoint/screenshots/.gitkeep               (create)
```

## Example: minimal `BaseBot` + `ValorBot` skeleton

```python
# app/core/base_bot.py
from abc import ABC, abstractmethod
from typing import Any, ClassVar
from pydantic import BaseModel
from app.models.config import AppConfig
from app.models.input_row import BaseInputRow

class BaseBot(ABC):
    key: ClassVar[str]
    display_name: ClassVar[str]
    InputRowModel: ClassVar[type[BaseInputRow]]
    ResultModel: ClassVar[type[BaseModel]]

    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.system = config.sistemas[self.key]

    @abstractmethod
    def authenticate(self, session) -> None: ...

    @abstractmethod
    def process_row(self, session, row: BaseInputRow) -> BaseModel: ...

    @abstractmethod
    def output_columns(self) -> list[str]: ...

    @abstractmethod
    def expand_result(self, result: BaseModel) -> list[dict[str, Any]]: ...
```

```python
# app/bots/valor/bot.py
from loguru import logger
from app.core.base_bot import BaseBot
from app.core.exceptions import NotFoundError
from app.core.registry import register_bot
from app.bots.valor.schema import ValorInputRow, ValorResult
from app.bots.valor import selectors as sel
from app.bots.valor import parsers
from app.utils.dates import now_str

@register_bot
class ValorBot(BaseBot):
    key = "valor"
    display_name = "Valor Financiamentos"
    InputRowModel = ValorInputRow
    ResultModel = ValorResult

    def authenticate(self, session) -> None:
        page = session.page
        page.goto(self.system.extras["dashboard_url"])
        if page.locator(sel.LOGIN_INPUT).count() > 0:
            page.fill(sel.LOGIN_INPUT, self.system.auth.email)
            page.fill(sel.SENHA_INPUT, self.system.auth.password.get_secret_value())
            session.solve_captcha_if_present(reason="login Valor")
            page.click(sel.BTLOGIN)
        page.wait_for_load_state("networkidle")
        logger.info("Valor: autenticado")

    def process_row(self, session, row: ValorInputRow) -> ValorResult:
        page = session.page
        page.click(sel.MENU_CONSULTA_SALDO)
        page.fill(sel.CSSENHA_INPUT, self.system.auth.password.get_secret_value())
        page.click(sel.BTCONSULTASALDO)
        page.wait_for_selector(sel.CONTRACTS_TABLE_OR_TOAST, timeout=15_000)

        toast = parsers.parse_error_toast(page)
        if toast and "Não existe informações" in toast:
            return ValorResult(row_index=row.row_index, cpf=row.cpf, nome=row.nome,
                               status_consulta="nao_encontrado",
                               observacao=toast, data_consulta=now_str())

        contracts = [c for c in parsers.parse_contracts_table(page) if c.status == "DEFERIDO"]
        for contract in contracts:
            page.click(sel.contract_row_by_id(contract.contrato))
            modal = page.locator(sel.MODAL_DIALOG)
            modal.wait_for(state="visible", timeout=10_000)
            contract.data_vencimento = parsers.parse_first_due_date_modal(modal)
            page.locator(sel.MODAL_CLOSE).click()
            modal.wait_for(state="hidden", timeout=5_000)

        return ValorResult(row_index=row.row_index, cpf=row.cpf, nome=row.nome,
                           contracts=contracts, status_consulta="ok",
                           observacao="" if contracts else "sem contratos DEFERIDO",
                           data_consulta=now_str())

    def output_columns(self) -> list[str]:
        return ["CPF", "Nome", "Contrato", "Data Vencimento", "Parcelas",
                "Convenio", "Status Consulta", "Observacao", "Data Consulta"]

    def expand_result(self, result: ValorResult) -> list[dict]:
        if not result.contracts:
            return [{"CPF": result.cpf, "Nome": result.nome, "Contrato": "",
                     "Data Vencimento": "", "Parcelas": "", "Convenio": "",
                     "Status Consulta": result.status_consulta,
                     "Observacao": result.observacao,
                     "Data Consulta": result.data_consulta}]
        return [{"CPF": result.cpf, "Nome": result.nome,
                 "Contrato": c.contrato, "Data Vencimento": c.data_vencimento or "",
                 "Parcelas": c.parcelas, "Convenio": c.convenio,
                 "Status Consulta": result.status_consulta,
                 "Observacao": result.observacao,
                 "Data Consulta": result.data_consulta}
                for c in result.contracts]
```

## Recommended Skills (hints para EXECUTE)

- `senior-architect` — durante Wave 1 (decisões estruturais)
- `simplify` — após Wave 2 (revisão de over-engineering antes de Wave 3)
- `claude-api` — não aplicável

## Acceptance Criteria

- [ ] `poetry install` instala todas as deps sem conflito — **pendente usuário**
- [ ] `poetry run python main.py` inicia, valida config, mostra menu Rich, lista bots disponíveis (Valor visível) — **pendente usuário**
- [x] Carregamento de `config.json` com placeholders falha com mensagem clara — verificado via inspeção dos validators em `app/models/config.py:55-69`
- [ ] `mypy app` retorna OK (modo strict) — **pendente usuário**
- [ ] `ruff check app` retorna OK — **pendente usuário**
- [x] Adicionar um bot fictício faz aparecer no menu sem qualquer outra mudança — verificado por design (Registry + `@register_bot` + `BotRegistry.discover()` em `app/core/registry.py`)
- [ ] Smoke manual no Valor com 1 CPF — **pendente usuário** (orientação no README; seletores em `app/bots/valor/selectors.py` podem precisar tuning fino)

<!-- mustard:generated -->
# Stack — consig-bot

## Versões (pyproject.toml)

| Pacote | Versão | Papel |
|--------|--------|-------|
| Python | >=3.12, <3.15 | runtime |
| playwright | ~1.48 | automação de browser (sync API) |
| pydantic | >=2.10, <3.0 | validação de dados (v2) |
| loguru | ~0.7 | logging estruturado |
| rich | ~13.9 | CLI interativa, progress, tabelas |
| pandas | ~2.2 | leitura de .xlsx (ExcelReader) |
| openpyxl | ~3.1 | escrita de .xlsx (ExcelWriter) |
| python-dotenv | ~1.0 | carregamento de .env |
| ruff | ^0.6 | linter/formatter (dev) |
| mypy | ^1.11 | type checking estrito (dev) |
| pytest | ^8.3 | testes (dev) |
| pyinstaller | ^6.10 | build executável standalone (dev) |

## Como rodar

```bash
# Modo principal (recomendado via Poetry)
poetry run python -m app

# Via script registrado no pyproject.toml
poetry run consig-bot

# Sem Poetry (se dependências já instaladas)
python main.py
# ou
python -m app
```

## Estrutura de diretórios

```
consig-bot/
├── app/
│   ├── __main__.py          # Entrypoint: configura logging, carrega config, orquestra CLI→Pipeline
│   ├── bots/
│   │   └── valor/           # Bot Valor Financiamentos (único bot MVP)
│   │       ├── __init__.py
│   │       ├── bot.py       # ValorBot(BaseBot) + @register_bot
│   │       ├── schema.py    # ValorInputRow, ValorContract, ValorResult (Pydantic)
│   │       ├── selectors.py # Todos os seletores CSS/XPath centralizados
│   │       └── parsers.py   # Funções puras de extração DOM (sem navegação)
│   ├── cli/
│   │   └── menu.py          # show_banner, select_bot, select_input_file, confirm
│   ├── core/
│   │   ├── base_bot.py      # BaseBot ABC — contrato Strategy
│   │   ├── browser.py       # BrowserSession — context manager Playwright
│   │   ├── exceptions.py    # Hierarquia de exceções: BotError e subclasses
│   │   ├── pipeline.py      # Pipeline — loop serial: rows → process → write → checkpoint
│   │   └── registry.py      # BotRegistry — auto-discovery + @register_bot decorator
│   ├── models/
│   │   ├── config.py        # AppConfig, BotRuntimeConfig, SystemConfig, etc. (Pydantic)
│   │   └── input_row.py     # BaseInputRow (Pydantic, extra="allow")
│   ├── services/
│   │   ├── captcha_solver.py # CaptchaSolver ABC + ManualCaptcha
│   │   ├── checkpoint.py     # CheckpointManager — CSV resumível por bot
│   │   ├── excel_reader.py   # ExcelReader — lê .xlsx → list[BaseInputRow]
│   │   └── excel_writer.py   # ExcelWriter — streaming .xlsx colorido por status
│   └── utils/
│       ├── cpf.py           # normalize_cpf, mask_cpf
│       ├── dates.py         # now_str, now_filename_ts
│       ├── logger.py        # configure_loguru
│       ├── paths.py         # get_app_root, ensure_dir
│       └── screenshots.py   # save_screenshot
├── entrada/                 # Planilhas .xlsx de entrada (gitignored)
├── saida/                   # Output por bot (gitignored)
│   └── valor/
├── checkpoint/              # Estado de resume + screenshots de debug
│   └── valor/
├── logs/                    # Logs Loguru (gitignored)
├── config.json              # Credenciais reais (gitignored — usar config.example.json)
├── config.example.json      # Template de configuração
├── pyproject.toml           # Dependências e scripts Poetry
└── main.py                  # Atalho: chama app.__main__.run()
```

## Padrões arquiteturais identificados

### Strategy Pattern (BaseBot)
Cada sistema suportado é uma subclasse de `BaseBot` com quatro métodos abstratos:
`authenticate`, `process_row`, `output_columns`, `expand_result`.

### Registry + Auto-discovery
`@register_bot` decorator + `BotRegistry.discover()` escaneia `app/bots/*/bot.py`
via `pkgutil.iter_modules`. Novos bots são descobertos automaticamente sem alterar código central.

### Pipeline serial com checkpoint
`Pipeline.run()` itera rows serialmente, chama `bot.process_row()`, escreve com
`ExcelWriter.append_result()`, e registra no `CheckpointManager`. Em rerun, linhas
já processadas são puladas por `checkpoint.is_processed(row_index)`.

### Config-driven via Pydantic v2
`config.json` é validado por `AppConfig.load()` com `model_validate`. Credenciais
usam `SecretStr`. Extras por sistema ficam em `system.extras: dict[str, Any]`.

### Sync-only Playwright
`BrowserSession` usa exclusivamente `playwright.sync_api`. Zero async/threading.
Context manager garante cleanup mesmo em exceção.

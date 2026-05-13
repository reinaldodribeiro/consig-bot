# Consig Bot

Automacao de consultas de margem consignavel em sistemas de financiamento via Playwright.

---

## Visao geral

O Consig Bot e uma ferramenta de automacao de navegador web que consulta portais de financiamento
consignado em nome do operador. A arquitetura e baseada no padrao **Strategy + Registry**:

- Cada sistema (ex.: Valor, BIB) e implementado como um **Bot** independente decorado com
  `@register_bot`, que herda de `BaseBot` e define seus proprios modelos de entrada/saida.
- O `BotRegistry` descobre automaticamente todos os bots presentes em `app/bots/` via
  `importlib` + `pkgutil` — nenhuma lista manual precisa ser mantida.
- A validacao de dados usa **Pydantic** (SecretStr para senhas, modelos de linha e resultado).
- A navegacao e feita com **Playwright** (modo headless configuravel).
- Logs estruturados sao emitidos por **Loguru** com tres sinks (console, arquivo, erros).
- O terminal exibe progresso em tempo real via **Rich**.

---

## Pre-requisitos

- Python >= 3.12
- [Poetry](https://python-poetry.org/) >= 1.8
- Windows 10 ou 11 (testado; Linux/macOS podem funcionar sem garantia)

---

## Instalacao

```bat
REM 1. Instalar dependencias Python
poetry install

REM 2. Baixar o navegador Chromium gerenciado pelo Playwright
poetry run playwright install chromium

REM 3. Criar o arquivo de configuracao a partir do exemplo
copy config.example.json config.json
```

Edite `config.json` conforme descrito na secao **Configuracao** abaixo.

---

## Configuracao

O arquivo `config.json` possui duas secoes principais.

### Secao `bot` — comportamento global

| Campo | Tipo | Descricao |
|-------|------|-----------|
| `headless` | bool | `true` = sem janela visivelv; `false` = janela visivel (necessario para captcha manual) |
| `delay_between_queries_seconds` | number | Pausa entre consultas consecutivas (segundos) |
| `max_retries` | int | Tentativas por linha antes de marcar como erro |
| `max_rows` | int ou null | Limite de linhas processadas por execucao (`null` = sem limite) |
| `input_folder` | string | Pasta de entrada dos arquivos `.xlsx` (padrao: `entrada`) |
| `output_folder` | string | Pasta de saida dos resultados (padrao: `saida`) |
| `timeout_navigation_ms` | int | Timeout de navegacao do Playwright (ms) |
| `timeout_selector_ms` | int | Timeout de seletores do Playwright (ms) |
| `proxy.enabled` | bool | Ativa uso de proxy |
| `proxy.server` | string | Endereco do proxy (ex.: `http://proxy:8080`) |
| `proxy.username` / `proxy.password` | string | Credenciais do proxy (opcional) |
| `captcha.mode` | string | `"manual"`, `"2captcha"` ou `"anti-captcha"` |
| `captcha.api_key` | string | Chave da API do servico de captcha (quando nao manual) |

### Secao `sistemas` — configuracao por bot

Cada chave (ex.: `"valor"`) corresponde ao `key` de um bot registrado.

| Campo | Descricao |
|-------|-----------|
| `auth.email` | Login do portal |
| `auth.password` | Senha do portal — use o valor real aqui; o Pydantic a trata como `SecretStr` em memoria, impedindo que apareca em logs |
| `excel.cpf_column` | Nome da coluna CPF no arquivo `.xlsx` de entrada |
| `excel.name_column` | Nome da coluna de nome do cliente |
| `extras.*` | Campos opcionais especificos do bot (URLs, listas de status validos etc.) |

> **Importante:** o `config.json` contem senhas em texto claro no disco. Mantenha-o fora do
> controle de versao (ja incluso no `.gitignore`). Nunca compartilhe o arquivo.

---

## Execucao

### Via terminal

```bat
poetry run python main.py
```

### Via duplo clique

Execute `executar.bat` (Windows) — abre o terminal e inicia o bot automaticamente.

### Fluxo de trabalho

1. Coloque um ou mais arquivos `.xlsx` na pasta `entrada/`.
   - Cada arquivo deve conter as colunas configuradas em `excel.cpf_column` e `excel.name_column`.
2. Execute o bot (veja acima).
3. Selecione o sistema desejado no menu interativo.
4. Os resultados sao gravados em:

```
saida/{sistema}/resultado_{chave}_{YYYYMMDD_HHMMSS}.xlsx
```

Exemplo: `saida/valor/resultado_valor_20240315_143022.xlsx`

---

## Bots disponiveis

| Chave (`key`) | Sistema | Status |
|---------------|---------|--------|
| `valor` | Valor Financiamentos | Implementado |
| `bib` | BIB | Placeholder (sem automacao ainda) |

---

## Adicionar um novo bot

Siga os quatro passos abaixo para integrar um novo sistema:

**Passo 1 — Criar o modulo do bot**

```
app/bots/{chave}/
    __init__.py
    bot.py        <- implementacao principal
    schema.py     <- InputRowModel e ResultModel
    selectors.py  <- seletores CSS/XPath
    parsers.py    <- logica de parsing do HTML
```

**Passo 2 — Implementar `bot.py`**

```python
from app.core.base_bot import BaseBot
from app.core.registry import register_bot

@register_bot
class MeuBot(BaseBot):
    key          = "meu-sistema"      # deve coincidir com a chave em config.json
    display_name = "Meu Sistema SA"
    InputRowModel = MeuInputRow
    ResultModel   = MeuResult

    def authenticate(self, session): ...
    def process_row(self, session, row): ...
    def output_columns(self): ...
    def expand_result(self, result): ...
```

O decorador `@register_bot` registra o bot automaticamente — nenhuma outra alteracao no
framework e necessaria.

**Passo 3 — Definir schema em `schema.py`**

Herde de `BaseInputRow` e `BaseResult` (ou use Pydantic puro) para definir os campos de
entrada e saida especificos do sistema.

**Passo 4 — Adicionar entrada em `config.json > sistemas`**

```json
"meu-sistema": {
  "name": "Meu Sistema SA",
  "auth": { "email": "...", "password": "..." },
  "excel": { "cpf_column": "cpf", "name_column": "nome" },
  "extras": {}
}
```

---

## Estrutura de pastas

```
consig-bot/
├── main.py                    # entrypoint
├── config.json                # configuracao local (nao versionado)
├── config.example.json        # template de configuracao
├── executar.bat               # atalho Windows
├── pyinstaller.spec           # template de empacotamento (futuro)
├── entrada/                   # arquivos .xlsx de entrada
├── saida/                     # resultados gerados
│   └── {sistema}/
│       └── resultado_{key}_{timestamp}.xlsx
├── logs/                      # arquivos de log
├── checkpoint/                # estado de retomada
└── app/
    ├── __main__.py
    ├── cli/                   # menu e barra de progresso (Rich)
    ├── core/                  # BaseBot, BotRegistry, BrowserSession, Pipeline
    ├── models/                # AppConfig, InputRow, Result (Pydantic)
    ├── services/              # ExcelReader, ExcelWriter, Checkpoint, CaptchaSolver
    ├── utils/                 # paths, cpf, dates, logger, screenshots
    └── bots/
        ├── valor/             # Valor Financiamentos (implementado)
        └── bib/               # BIB (placeholder)
```

---

## Logs

| Arquivo | Nivel | Retencao |
|---------|-------|----------|
| `logs/consig-bot_{data}.log` | DEBUG (tudo) | 14 dias, rotacao a cada 10 MB, compressao ZIP |
| `logs/errors_{data}.log` | ERROR (so erros) | 30 dias, rotacao a cada 10 MB |
| Console (stderr) | INFO | Tempo real, colorido via Rich/Loguru |

CPFs sao mascarados nos logs (`***.***.***-**`) antes de qualquer escrita.

---

## Checkpoint e retomada

Ao processar um lote, o bot grava o progresso em:

```
checkpoint/{chave}_checkpoint.csv
```

Se a execucao for interrompida (erro, queda de energia, fechamento manual), na proxima
execucao o bot le o checkpoint e **pula automaticamente as linhas ja processadas**.

Para reprocessar todo o arquivo do zero, basta apagar o arquivo de checkpoint correspondente:

```bat
del checkpoint\valor_checkpoint.csv
```

---

## Captcha

Atualmente o modo padrao e `"manual"`: quando um captcha e detectado, o bot **pausa** a
execucao e exibe uma mensagem no console solicitando que o usuario resolva o captcha
diretamente no navegador. Apos a resolucao, o bot retoma automaticamente.

Para resolver captchas manualmente, certifique-se de que `headless: false` esta definido em
`config.json` — caso contrario o navegador nao sera visivel.

Os modos `"2captcha"` e `"anti-captcha"` estao planejados para versoes futuras (v0.3).

---

## Troubleshooting

**"Login nao confirmado"**

Verifique as credenciais em `config.json > sistemas > {chave} > auth`. Alguns portais so
aceitam login em horario comercial — acesse a `dashboard_url` configurada no bloco `extras`
para confirmar o status do portal.

**"Captcha detectado"**

Configure `headless: false` em `config.json > bot` para que a janela do navegador fique
visivel e voce possa resolver o captcha manualmente.

**"Sessao expirada"**

O bot detecta redirecionamentos para a pagina de login e tenta re-autenticar automaticamente
antes de reprocessar a linha corrente.

**"Tabela ou toast nao apareceu"**

Os seletores CSS/XPath podem ter sido alterados pelo portal. Edite o arquivo
`app/bots/valor/selectors.py` (ou o equivalente do sistema afetado) para atualizar os
seletores conforme o HTML atual do site.

---

## Desenvolvimento

```bat
REM Verificacao de estilo e tipos
poetry run ruff check app
poetry run mypy app

REM Testes
poetry run pytest
```

---

## Empacotamento (futuro)

O arquivo `pyinstaller.spec` na raiz do projeto contem um template para gerar um executavel
Windows standalone (`dist/consig-bot.exe`) via PyInstaller. Este template **nao foi validado
em build real** e esta disponivel para uso futuro (v0.6 do roadmap).

Para usar quando o momento chegar:

```bat
pip install pyinstaller
poetry run playwright install chromium
pyinstaller pyinstaller.spec --clean --noconfirm
```

Apos o build, copie manualmente para o lado do `.exe`:
`config.example.json`, `executar.bat` (ajustado), e as pastas vazias `entrada/`, `saida/`,
`logs/`, `checkpoint/`.

---

## Roadmap

| Versao | Objetivo |
|--------|----------|
| v0.2 | Implementar automacao do bot BIB |
| v0.3 | Suporte a captcha automatico (`2captcha` / `anti-captcha`) |
| v0.4 | Suporte completo a proxies rotativos |
| v0.5 | Processamento concorrente (multiplos bots em paralelo) |
| v0.6 | Empacotamento como `.exe` standalone via PyInstaller |

---

## Seguranca

- `config.json` esta listado no `.gitignore` e **nunca deve ser versionado**.
- Senhas sao armazenadas como `pydantic.SecretStr` em memoria — nao aparecem em logs, tracebacks
  ou representacoes de objeto (`__repr__`).
- CPFs sao mascarados em todos os logs antes da escrita (`***.***.***-**`).
- Nao compartilhe `config.json`, arquivos `.xlsx` de entrada ou logs com terceiros sem
  remover dados sensiveis.

---

## Licenca

A definir pelo proprietario do projeto.

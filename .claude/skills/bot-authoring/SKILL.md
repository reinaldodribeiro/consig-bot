---
name: bot-authoring
description: Use when creating a new bot, adding a new system (financeira, convênio), implementing a new scraping target, or adding automation for a new website. Covers BaseBot subclass, schema, selectors, parsers wiring.
---
<!-- mustard:generated -->
# Skill — bot-authoring

Guia completo para criar um novo bot no consig-bot do zero.

## Arquitetura obrigatória

Todo bot deve ter exatamente esta estrutura:

```
app/bots/{nome}/
├── __init__.py      (vazio)
├── bot.py           ({Nome}Bot — @register_bot + BaseBot)
├── schema.py        ({Nome}InputRow, {Nome}Result, modelos intermediários)
├── selectors.py     (todas as strings CSS/XPath — NUNCA inline)
└── parsers.py       (funções puras de extração DOM — NUNCA navegam)
```

## Checklist de implementação

### 1. schema.py

- [ ] `{Nome}InputRow(BaseInputRow)` com campos `cpf: str` e `nome: str`
- [ ] `@field_validator("cpf", mode="before")` chamando `normalize_cpf`
- [ ] `{Nome}Result(BaseModel)` com campos obrigatórios do Pipeline:
  - `row_index: int`, `cpf: str`, `nome: str`
  - `status_consulta: Literal[...]`
  - `observacao: str`, `data_consulta: str`
- [ ] Modelos intermediários com `extra="ignore"` (tolerantes a campos extras do site)

### 2. selectors.py

- [ ] Todas as strings de seletor são constantes de módulo (UPPER_SNAKE_CASE)
- [ ] Seletores instáveis usam múltiplos fallbacks: `"css1, css2, xpath=//..."`
- [ ] Seletores dinâmicos são funções: `def cell(row, col): return f"#{row}_{col}"`
- [ ] Nenhuma lógica de navegação ou extração aqui — apenas strings/funções retornando strings

### 3. parsers.py

- [ ] Todas as funções são `parse_{o_que_extrai}(page: Page | Frame) -> tipo`
- [ ] Nenhuma chamada de `goto`, `click`, `fill` — apenas leitura
- [ ] Verificam `locator.count() == 0` antes de acessar elementos
- [ ] Usam `frame.evaluate(JS)` apenas quando locators são insuficientes
- [ ] Retornam valores neutros (lista vazia, None) quando elemento ausente

### 4. bot.py

- [ ] `@register_bot` decorator imediatamente antes de `class`
- [ ] Quatro ClassVar: `key`, `display_name`, `InputRowModel`, `ResultModel`
- [ ] `key` idêntico à chave em `config.json sistemas`
- [ ] `__init__` chama `super().__init__(config)`, lê `self.system.extras` para configs extras
- [ ] `authenticate`: navega → preenche credenciais → valida login → `raise AuthenticationError` se falhar
- [ ] `process_row`: navega → consulta → delega parse aos parsers → retorna Result
- [ ] `output_columns`: lista ordenada de strings (nomes das colunas Excel)
- [ ] `expand_result`: transforma Result em `list[dict[coluna, valor]]`, 1+ linha por resultado
- [ ] Usa exceções tipadas: `NotFoundError`, `ParseError`, `SessionExpired`, etc.

## Exemplos reais do código (ValorBot)

### Autenticação com re-login detection

```python
# app/bots/valor/bot.py:58-95
def authenticate(self, session: BrowserSession) -> None:
    page = session.page
    page.goto(self._dashboard_url, wait_until="domcontentloaded")

    if self._needs_login(page):
        self._fill_login(page)
        self._handle_captcha_if_present(page, "login Valor")
        page.click(sel.BTLOGIN)
        with contextlib.suppress(Exception):
            page.wait_for_load_state("networkidle", timeout=15_000)
        page.goto(self._dashboard_url, wait_until="domcontentloaded")

    if self._needs_login(page):
        raise AuthenticationError("Login não confirmado.")
    logger.info("Valor: autenticado")

def _needs_login(self, page) -> bool:
    url = page.url.lower()
    if "index.php" in url or "/login" in url:
        return True
    return (page.locator(sel.LOGIN_INPUT).count() > 0
            and page.locator(sel.BTLOGIN).count() > 0)
```

### process_row com iframe

```python
# app/bots/valor/bot.py:132-204
def process_row(self, session: BrowserSession, row: ValorInputRow) -> ValorResult:
    page = session.page

    # Navegar para o formulário de consulta
    if not page.locator(sel.CSSENHA_INPUT).is_visible():
        page.click(sel.MENU_CONSULTA_SALDO)
        page.wait_for_selector(sel.CSSENHA_INPUT, state="visible", timeout=10_000)

    page.fill(sel.CSSENHA_INPUT, row.cpf)
    page.click(sel.BTCONSULTASALDO)

    # Aguardar iframe de resultado
    page.wait_for_selector(sel.IFRAME_RESULT, timeout=20_000)
    frame = page.frame(name=sel.IFRAME_RESULT_NAME)
    if frame is None:
        raise ParseError("frame não encontrado")

    # Verificar erro antes de parsear dados
    toast = parsers.parse_error_toast(frame)
    if toast and sel.NO_INFO_MESSAGE_TEXT.lower() in toast.lower():
        raise NotFoundError(toast)

    contracts = parsers.parse_contracts_table(frame)
    return ValorResult(
        row_index=row.row_index, cpf=row.cpf, nome=row.nome,
        contracts=contracts, status_consulta="ok",
        observacao=toast or ("" if contracts else "sem contratos"),
        data_consulta=now_str(),
    )
```

### Parser de tabela com extração por ID de célula

```python
# app/bots/valor/parsers.py:15-44
def parse_contracts_table(page: Page | Frame) -> list[ValorContract]:
    table = page.locator(sel.CONTRACTS_TABLE).first
    if table.count() == 0:
        return []

    def _cell(row: int, col: int) -> str:
        loc = page.locator(f"#JTPlatinumGrid2_cell_{row}_{col}").first
        return loc.inner_text().strip() if loc.count() > 0 else ""

    contracts = []
    i = 0
    while True:
        contrato = _cell(i, 0)
        if not contrato:   # linha vazia = fim da tabela
            break
        contracts.append(ValorContract(
            contrato=contrato, parcelas=_cell(i, 4),
            status=_cell(i, 5).upper(), convenio=_cell(i, 6),
        ))
        i += 1
    return contracts
```

### Parser com JavaScript evaluate (estrutura JS-dinâmica)

```python
# app/bots/valor/parsers.py:47-72
def parse_first_due_date(frame: Page | Frame) -> str | None:
    try:
        result = frame.evaluate("""() => {
            const rows = document.querySelectorAll(
                '#pn_parcelas_table_detail tr[id^="cronograma_"]'
            );
            for (const row of rows) {
                const divs = row.querySelectorAll('td > div.linha > div');
                if (divs.length < 3) continue;
                if ((divs[1].textContent || '').trim() !== '1') continue;
                const venc = (divs[2].textContent || '').trim();
                if (/\\d{2}\\/\\d{2}\\/\\d{4}/.test(venc)) return venc;
            }
            return null;
        }""")
        return result or None
    except Exception as exc:
        logger.debug("parse_first_due_date erro: {}", exc)
        return None
```

### expand_result com 1 linha por contrato (one-to-many)

```python
# app/bots/valor/bot.py:212-231
def expand_result(self, result: ValorResult) -> list[dict[str, Any]]:
    if not result.contracts:
        # Linha sem contratos: uma linha no Excel com campos de contrato vazios
        return [{
            "CPF": result.cpf, "Nome": result.nome,
            "Contrato": "", "Data Vencimento": "", "Parcelas": "", "Convenio": "",
            "Status Contrato": "",
            "Status Consulta": result.status_consulta,
            "Observacao": result.observacao,
            "Data Consulta": result.data_consulta,
        }]
    # Um contrato = uma linha Excel
    return [{
        "CPF": result.cpf, "Nome": result.nome,
        "Contrato": c.contrato, "Data Vencimento": c.data_vencimento or "",
        "Parcelas": c.parcelas, "Convenio": c.convenio,
        "Status Contrato": c.status,
        "Status Consulta": result.status_consulta,
        "Observacao": result.observacao,
        "Data Consulta": result.data_consulta,
    } for c in result.contracts]
```

## Registro em config.json

```json
{
  "bot": {
    "headless": true,
    "debug": false,
    "delay_between_queries_seconds": 1.5
  },
  "sistemas": {
    "{nome}": {
      "name": "{Nome Completo do Sistema}",
      "auth": {
        "email": "usuario@sistema.gov.br",
        "password": "senha_real"
      },
      "excel": {
        "cpf_column": "cpf",
        "name_column": "nome"
      },
      "extras": {
        "login_url": "https://sistema.gov.br/login",
        "parametro_especifico": "valor"
      }
    }
  }
}
```

## Hierarquia de exceções — quando usar cada uma

| Exceção | Uso | Efeito no Pipeline |
|---------|-----|--------------------|
| `NotFoundError` | Site confirma "sem dados" para o CPF | status=nao_encontrado, próxima linha |
| `ParseError` | DOM inesperado, elemento não encontrado | status=erro, screenshot se debug |
| `SessionExpired` | Sessão expirou (redirect para login) | re-autentica e retenta |
| `CaptchaRequired` | Captcha detectado | pausa para resolução manual |
| `RateLimited` | Site bloqueou temporariamente | status=rate_limit, próxima linha |
| `AuthenticationError` | Login falhou definitivamente | ABORTA todo o run |

## Dicas de estabilidade

1. **Aguarde estados explícitos**: prefira `wait_for_selector(state="visible")` a `time.sleep()`
2. **Multi-fallback em seletores**: `"css1, css2, xpath=//..."` aumenta resiliência a mudanças no site
3. **Verifique antes de acessar**: `if locator.count() == 0: return []` evita TimeoutError
4. **Use `contextlib.suppress`** para operações opcionais (wait_for_load_state networkidle)
5. **Loguem com `logger.debug`** em parsers e `logger.info` em bot.py para rastreabilidade
6. **Salve artefatos de falha** via `page.screenshot()` + `page.content()` quando em modo debug

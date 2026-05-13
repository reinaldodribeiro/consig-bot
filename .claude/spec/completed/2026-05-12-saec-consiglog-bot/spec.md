# Feature: Saec ConsigLog Bot (PREFEITURA GOIÂNIA)

### Status: completed | Phase: CLOSE | Scope: full
### Completed: 2026-05-12T00:00:00Z
### Checkpoint: 2026-05-12T00:00:00Z
### Approved: 2026-05-12T00:00:00Z

## Summary
Novo bot **SaecBot** para automatizar consulta de margem no portal `saec.consiglog.com.br` (convênio padrão: PREFEITURA GOIÂNIA). Diferente dos bots existentes (`valor`, `bib`), a planilha de entrada contém apenas a coluna `matricula` — o nome do servidor, o CPF e as margens são extraídos do próprio site. Por isso, além de adicionar a pasta `app/bots/saec/`, é necessário ampliar `SystemExcelConfig` e `ExcelReader` para suportar input baseado em matrícula (CPF/Nome opcionais).

## Entity Info
- **Bot key:** `saec`
- **Display name:** `Saec ConsigLog`
- **Convênio padrão:** `PREFEITURA GOIÂNIA` (configurável via `extras.convenio_sigla`)
- **URLs:**
  - Login: `https://saec.consiglog.com.br/Login.aspx`
  - Seleção de convênio (sessão ativa): `https://saec.consiglog.com.br/LoginSelecao.aspx`
  - Consulta: `https://saec.consiglog.com.br/Margem/ConsultaMargem.aspx`
- **Input planilha:** coluna `matricula` (string, será preenchida com zeros à esquerda até 11 dígitos no campo do site via `onblur=adicionaZeros`)
- **Output planilha:** `Matrícula`, `Nome`, `CPF`, `Margem Empréstimo`, `Margem Cartão`, `Status Consulta`, `Observação`, `Data Consulta`
- **Status do bot:** `Literal["ok", "nao_encontrado", "erro", "session_expired", "auth_error"]`

## Files (~9)
- `app/bots/saec/__init__.py` (create) — pacote vazio
- `app/bots/saec/schema.py` (create) — `SaecInputRow`, `SaecResult`, `SaecMargens`
- `app/bots/saec/selectors.py` (create) — seletores CSS/IDs do site
- `app/bots/saec/parsers.py` (create) — extração DOM pura (nome, CPF, margens)
- `app/bots/saec/bot.py` (create) — `SaecBot(BaseBot)` com `@register_bot`
- `app/models/config.py` (modify) — `SystemExcelConfig`: torna `cpf_column`/`name_column` opcionais; adiciona `matricula_column`
- `app/services/excel_reader.py` (modify) — input baseado em matrícula quando `matricula_column` configurado; cpf/nome opcionais
- `config.example.json` (modify) — adiciona bloco `sistemas.saec`
- `app/bots/saec/__init__.py` — registrar (vazio, registry usa `@register_bot`)

## Boundaries
- `app/bots/saec/` — toda a pasta do novo bot
- `app/models/config.py` — apenas `SystemExcelConfig`
- `app/services/excel_reader.py` — apenas método `read()` (suporte a matricula + cpf/nome opcionais)
- `config.example.json` — adiciona apenas o bloco `saec` em `sistemas`

## Dependencies
- Wave 1 (paralelo): **Backend (Saec bot)** + **Backend (Core: config + excel reader)** — bot depende do schema da config, mas como ambos rodam serialmente em Wave 1 (mesmo agente backend), o agente sequencia internamente.
- Não há frontend nem DB. Tudo backend.

## Tasks

### Backend Agent (Wave 1)

#### Core: tornar input flexível
- [x] `app/models/config.py` — Em `SystemExcelConfig`: mudar `cpf_column: str = "cpf"` para `cpf_column: str | None = "cpf"` e `name_column: str = "nome"` para `name_column: str | None = "nome"`. Adicionar `matricula_column: str | None = None`.
- [x] `app/services/excel_reader.py` — Em `ExcelReader.read()`:
  - `cpf_col`/`name_col` só validados como obrigatórios quando `not None`.
  - Se `excel_config.matricula_column` definido, validar presença e adicionar `"matricula": raw.get(matricula_col, "")` ao dict passado para `model_validate`.
  - Não normalizar `cpf` quando `cpf_column is None` (passar string vazia).

#### Bot Saec: schema
- [x] `app/bots/saec/__init__.py` — arquivo vazio.
- [x] `app/bots/saec/schema.py`:
  - `SaecStatus = Literal["ok", "nao_encontrado", "erro", "session_expired", "auth_error"]`
  - `SaecInputRow(BaseInputRow)` com `matricula: str = ""`, `cpf: str = ""`, `nome: str = ""`. Validator que faz `strip()` e remove não-dígitos da matrícula.
  - `SaecMargens(BaseModel)` com `margem_emprestimo: str`, `margem_cartao: str` (`extra="ignore"`).
  - `SaecResult(BaseModel)` com `model_config = ConfigDict(extra="allow")`, campos: `row_index: int`, `matricula: str`, `nome: str`, `cpf: str`, `margens: SaecMargens | None`, `status_consulta: SaecStatus`, `observacao: str`, `data_consulta: str`.

#### Bot Saec: selectors
- [x] `app/bots/saec/selectors.py` — Constantes:
  - **Login passo 1:** `LOGIN_USER = "#txtLogin"`, `LOGIN_NEXT = "#Entrar"` (botão "Próxima" na página inicial).
  - **Login passo 2:** `LOGIN_PASS = "#txtSenha"`, `LOGIN_SUBMIT = "#Entrar"` (mesmo id, contexto diferente).
  - **Seleção de convênio:** `CONVENIO_TABLE = "#gvOrgao"`, `CONVENIO_ROWS = "#gvOrgao tbody tr"`, função `convenio_button_xpath(label)` que retorna XPath para `//tr[td[normalize-space()='{label}']]//input[@type='image']`.
  - **Consulta:** `MATRICULA_INPUT = "#body_matriculaTextBox"`, `PESQUISAR_BTN = "#body_pesquisarButton"`.
  - **Resultado:** `NOME_INPUT = "#body_clienteTextBox"`, `CPF_INPUT = "#body_cpf_nascimentoTextBox"`, `MARGENS_TABLE = "table.grid.grid-detalhe"`, `MARGEM_HEADER_ROW = "tr[id^='body_rptMargens_headerservico_']"`.

#### Bot Saec: parsers
- [x] `app/bots/saec/parsers.py`:
  - `parse_nome(page)` → `inner_value` de `NOME_INPUT` (atributo `value`).
  - `parse_cpf(page)` → `value` de `CPF_INPUT`.
  - `parse_margens(page) -> SaecMargens | None` — via `page.evaluate(JS)`: percorre `tr[id^='body_rptMargens_headerservico_']`, pega `td[0].innerText` (nome do serviço — "MARGEM EMPRÉSTIMO" / "MARGEM CARTÃO") e `td[3].innerText` (coluna "Margem Disponível"). Mapeia para `margem_emprestimo` / `margem_cartao`. Limpa "R$ " + espaços do valor. Retorna `None` se tabela não existir.
  - `parse_erro_consulta(page)` — detecta mensagem de erro (ex: "matrícula não encontrada"); retorna string ou `None`.

#### Bot Saec: classe
- [x] `app/bots/saec/bot.py` — `SaecBot(BaseBot)`:
  - `@register_bot`, `key="saec"`, `display_name="Saec ConsigLog"`.
  - `__init__`: lê `extras.login_url`, `extras.selecao_url`, `extras.consulta_url`, `extras.convenio_label` (default `"PREFEITURA GOIÂNIA"`).
  - `authenticate(session)`:
    1. `page.goto(login_url)`
    2. Se `txtLogin` visível → preenche usuário, clica `LOGIN_NEXT`, aguarda `txtSenha`, preenche senha, clica `LOGIN_SUBMIT`, aguarda navegação.
    3. Se URL atual contém `LoginSelecao.aspx` (ou após login) → resolve seleção de convênio via `_select_convenio(page)`.
    4. Após seleção, aguarda navegação para `ConsultaMargem.aspx` ou página default. Se ainda em login → `raise AuthenticationError`.
  - `_select_convenio(page)`: aguarda `CONVENIO_TABLE`, clica no botão (input image) da linha cujo `td` contém o label configurado. Usa `page.locator(xpath=...)`. Se não encontrar → `raise AuthenticationError("Convênio '{label}' não encontrado na lista")`.
  - `process_row(session, row)`:
    1. Se URL atual ≠ `consulta_url` → `page.goto(consulta_url, wait_until="domcontentloaded")`.
    2. Se redirecionou para login/seleção → `raise SessionExpired`.
    3. Preenche `MATRICULA_INPUT` com `row.matricula` (sem zeros — site preenche via `onblur`). `page.fill(...)`.
    4. Clica `PESQUISAR_BTN`. `wait_for_load_state("networkidle", timeout=15_000)` com `contextlib.suppress`.
    5. Detecta erro: se `parse_erro_consulta` retornar mensagem ou `NOME_INPUT` ficar vazio → `raise NotFoundError`.
    6. Parse nome, CPF, margens.
    7. Retorna `SaecResult(...)` com `status_consulta="ok"`, `margens=<parsed>`.
  - `output_columns()` → `["Matrícula", "Nome", "CPF", "Margem Empréstimo", "Margem Cartão", "Status Consulta", "Observação", "Data Consulta"]`.
  - `center_columns()` → `["Matrícula", "CPF", "Margem Empréstimo", "Margem Cartão"]`.
  - `expand_result(result)` → uma linha por result. CPF formatado via `format_cpf` (se utilitário existir) ou apenas dígitos. Margens vazias quando `margens is None`.

#### Config
- [x] `config.example.json` — adicionar bloco `sistemas.saec`:
  ```json
  "saec": {
    "name": "Saec ConsigLog",
    "auth": { "email": "usuario", "password": "senha" },
    "excel": { "cpf_column": null, "name_column": null, "matricula_column": "matricula" },
    "extras": {
      "login_url": "https://saec.consiglog.com.br/Login.aspx",
      "selecao_url": "https://saec.consiglog.com.br/LoginSelecao.aspx",
      "consulta_url": "https://saec.consiglog.com.br/Margem/ConsultaMargem.aspx",
      "convenio_label": "PREFEITURA GOIÂNIA"
    }
  }
  ```

#### Validação final
- [x] Importar `app.bots.saec.bot` sem erros (`python -c "from app.bots.saec import bot"`).
- [x] Rodar `python -c "from app.models.config import AppConfig; import json; AppConfig.model_validate(json.load(open('config.example.json')))"` para garantir que o schema aceita o novo bloco e que `valor`/`bib` não quebraram (cpf/name still default).
- [x] Type-check (se houver — `mypy` ou `pyright`): garantir `cpf_column: str | None` consistente em todos os usos.

## Recipes / Skill References
- `bot-authoring` (SKILL.md) — arquitetura obrigatória de bot.
- `app/bots/bib/` — referência direta para ASP.NET WebForms (postbacks via clique de submit, leitura via `evaluate` JS).
- `app/bots/valor/` — referência para `_needs_login`, captura de artefatos de falha, e re-login em `SessionExpired`.

## Riscos & Concerns
- **Pipeline fallback de cpf/nome:** `Pipeline._process_one` faz `getattr(row, "cpf", "")` e usa esse valor em resultados de erro. Para Saec, o cpf no input é sempre `""` (vem do site). Em erro, o `SaecResult` registrado pelo pipeline terá `cpf=""` e `nome=""`, mas `matricula` ficará vazio também (pipeline não conhece o campo). Isso é aceitável: a linha de erro mostrará `row_index` + `observação`. Matrícula pode ser recuperada visualmente cruzando com a planilha original. Alternativa (não adotada nesta versão para limitar escopo): estender `Pipeline._process_one` para repassar `row.raw` ao result.
- **Site ASP.NET `__doPostBack`:** o botão "Próxima" e "Entrar" usam `type="submit"`, então `page.click` deve disparar o postback. Sem necessidade de `HTMLFormElement.prototype.submit` (truque do BIB), exceto se observarmos congelamento.
- **`onblur=adicionaZeros`:** o campo de matrícula adiciona zeros à esquerda automaticamente. Usar `page.fill` + `page.keyboard.press("Tab")` (ou apenas click out) para disparar o `onblur` antes de clicar `Pesquisar`.
- **Detecção de sessão ativa vs. login fresh:** quando há sessão ativa, o site pode redirecionar diretamente para `LoginSelecao.aspx`. O `authenticate` deve cobrir ambos os caminhos (form de login OU tabela de convênio).
- **Convênio único:** se houver só um convênio na conta, o site pode pular `LoginSelecao.aspx` automaticamente. Tratar `CONVENIO_TABLE` ausente como "convênio já selecionado".

## Elegance Check
O usuário pediu para "pegar só a coluna Margem Disponível". Em vez de mapear cada tipo de margem para uma coluna separada na planilha, preservamos apenas "MARGEM EMPRÉSTIMO" e "MARGEM CARTÃO" (conforme pedido explícito do usuário). Demais margens (benefício compra/saque/eventuais) são ignoradas. Caso o usuário queira incluí-las depois, basta adicionar campos em `SaecMargens` — o parser já itera sobre todas as linhas.

A mudança em `SystemExcelConfig` é minimamente invasiva: torna campos atuais opcionais (com defaults antigos) e adiciona um novo campo opcional. Bots existentes não precisam alterar configuração.

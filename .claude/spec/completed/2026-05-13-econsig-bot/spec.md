# Feature: Econsig Bot (com CAPTCHA Tesseract)

### Status: completed | Phase: CLOSE | Scope: full
### Checkpoint: 2026-05-13T00:00:00Z

## Review Concerns (não-bloqueantes — APPROVED)
1. `bot.py:16` — Reviewer alertou para top-level import de `tesseract_solve`. **Falso positivo**: `ocr.py` faz import lazy de `pytesseract`/`Pillow` *dentro* de `tesseract_solve()`. Importar a função em si não dispara o import das deps.
2. `ocr.py:29-37` — `except Exception` largo pode mascarar erros de decode do PIL (`UnidentifiedImageError`). Comportamento atual gera retry — não catastrófico, mas vale apertar.
3. `bot.py:83-88` — Refresh do captcha usa path relativo `'../captcha.jpg?t='`. Mais robusto seria reutilizar o `src` atual: `img.src.split('?')[0] + '?t=' + Date.now()`. Mudança de 2 linhas se necessário.
4. `config.example.json:19` — `bot.captcha.mode` permanece `"manual"`. O bot Econsig usa Tesseract direto via `app/services/ocr.py` (não lê `bot.captcha.mode`), então funciona com o exemplo atual. Documentar essa relação reduz confusão para usuários futuros.
5. Pre-existente (não causado por este PR): divergência de versão de `pydantic` entre `pyproject.toml` e `requirements.txt`.

## Summary
Novo bot **Econsig** (`portal.econsig.com.br`) seguindo o padrão dos bots existentes (BaseBot + register_bot). Login em 2 etapas: usuário → senha+CAPTCHA. CAPTCHA resolvido localmente via Tesseract (pytesseract), com retry loop quando o site rejeita o código. Consulta margem (empréstimo + cartão + data carga) por matrícula, tratando 3 estados: sucesso, NÃO ENCONTRADO, e SERVIDOR EXCLUÍDO.

## Entity Info
- **Bot key**: `econsig`
- **Display name**: `Econsig`
- **Não está no registry** — entidade nova
- **Padrão de referência**: `app/bots/consiglog/` (matrícula → margem_emprestimo + margem_cartao)
- **Diferenças vs consiglog**:
  - Login com CAPTCHA (consiglog não tem)
  - Sem seleção de convênio (consiglog tem)
  - Campo extra: `data_carga` no resultado de margem
  - Status extra: `servidor_excluido` (consiglog não tem)

## Boundaries
- `app/bots/econsig/` — diretório completo do novo bot (criar)
- `app/services/ocr.py` — novo módulo para função pura de OCR Tesseract (criar)
- `app/services/captcha_solver.py` — extensão: adicionar mode `tesseract` no `build_captcha_solver` (opcional — ver Nota Arquitetural abaixo)
- `app/models/config.py` — adicionar `"tesseract"` ao Literal de `CaptchaConfig.mode`
- `config.example.json` — adicionar bloco `sistemas.econsig`
- `pyproject.toml` — adicionar dependências `pytesseract`, `Pillow`
- `requirements.txt` — espelhar dependências
- `mustard.json` — atualizar lista de entidades (se aplicável)

## Nota Arquitetural — onde mora o Tesseract

A função de OCR pura (bytes → string) vai em `app/services/ocr.py`, **não dentro do bot**. Razão: mantém o bot focado em fluxo de página e permite reuso por outros bots no futuro. O `captcha_solver.py` atual segue inalterado em essência (a classe `ManualCaptcha` é para pausar e pedir resolução humana, semântica diferente). A invocação do OCR e o retry loop ficam dentro de `EconsigBot._do_login` — site-specific.

`CaptchaConfig.mode` recebe `"tesseract"` como opção válida para refletir no config, mas o solver atual não muda — o bot lê `self.config.bot.captcha.mode` para decidir o caminho de resolução.

## Files (~9 criados/modificados)

### Criar
- `app/bots/econsig/__init__.py` (vazio)
- `app/bots/econsig/bot.py` (~250 linhas — EconsigBot + login 2 etapas + captcha retry)
- `app/bots/econsig/schema.py` (~40 linhas — InputRow, Margens com `data_carga`, Result)
- `app/bots/econsig/selectors.py` (~30 linhas — todas strings DOM como constantes)
- `app/bots/econsig/parsers.py` (~60 linhas — parse_margens_success, parse_error_message, parse_data_carga)
- `app/services/ocr.py` (~30 linhas — função pura `tesseract_solve(image_bytes: bytes) -> str` com pré-processamento)

### Modificar
- `app/models/config.py` — Literal de mode: adicionar `"tesseract"`
- `config.example.json` — bloco `sistemas.econsig`
- `pyproject.toml` — dependências `pytesseract>=0.3.10`, `Pillow>=10.0`
- `requirements.txt` — mesmas dependências

## Dependencies
- **Externas (novo)**: `pytesseract`, `Pillow`
- **Binário sistema**: `tesseract` deve estar no PATH (documentar no README)
- **Internas**: `app.core.base_bot.BaseBot`, `app.core.registry.register_bot`, `app.core.browser.BrowserSession`, `app.core.exceptions.*`, `app.utils.dates.now_str`, `app.utils.paths.*`

## Checklist

### Library Agent (Wave 1 — Foundation)
- [x] Adicionar `pytesseract>=0.3.10` e `Pillow>=10.0` em `pyproject.toml` (na seção `[project.dependencies]` ou equivalente)
- [x] Espelhar as duas dependências em `requirements.txt`
- [x] Em `app/models/config.py`, estender o Literal de `CaptchaConfig.mode` para incluir `"tesseract"`
- [x] Criar `app/services/ocr.py` com `tesseract_solve(image_bytes: bytes, *, allowlist: str | None = None) -> str`:
  - Aceita bytes JPG/PNG
  - Abre via `PIL.Image.open(BytesIO(image_bytes))`
  - Pré-processamento básico: converter para grayscale + binarizar (threshold)
  - Chama `pytesseract.image_to_string` com `--psm 7` (single text line) e `tessedit_char_whitelist` quando allowlist é dado
  - Sanitiza: remove whitespace e caracteres não-alfanuméricos
  - Levanta `RuntimeError` se Tesseract binário não estiver disponível (catch `pytesseract.TesseractNotFoundError` e re-raise com mensagem clara)

### Library Agent (Wave 2 — Bot Module)
- [x] Criar `app/bots/econsig/__init__.py` (vazio)
- [x] Criar `app/bots/econsig/schema.py`:
  - `EconsigStatus = Literal["ok", "nao_encontrado", "servidor_excluido", "erro", "session_expired", "auth_error"]`
  - `EconsigInputRow(BaseInputRow)` com `matricula: str = ""`, `cpf: str = ""`, `nome: str = ""` (mesmo `_clean_matricula` validator do consiglog)
  - `EconsigMargens(BaseModel)` com `margem_emprestimo: str`, `margem_cartao: str`, `data_carga: str`, todos defaultando para `""`
  - `EconsigResult(BaseModel)` com `row_index`, `matricula`, `nome`, `cpf`, `margens: EconsigMargens | None`, `status_consulta`, `observacao`, `data_consulta`
- [x] Criar `app/bots/econsig/selectors.py` (constantes UPPER_SNAKE_CASE):
  - `LOGIN_USER = "input#username[name='username']"`
  - `LOGIN_NEXT_BTN = "button.btn.btn-primary[type='submit']"`
  - `LOGIN_PASS = "input[name='senha']"`
  - `CAPTCHA_IMG = "img[name='captcha_img']"`
  - `CAPTCHA_INPUT = "input#captcha[name='captcha']"`
  - `LOGIN_SUBMIT_BTN = "button#btnOK"`
  - `MATRICULA_INPUT = "input#RSE_MATRICULA[name='RSE_MATRICULA']"`
  - `PESQUISAR_BTN` — texto "Pesquisar" (verificar HTML real durante implementação; fallback por XPath se necessário)
  - `MSG_SUCCESS = "span#idMsgSuccessSession"`
  - `MSG_ERROR = "span#idMsgErrorSession"`
  - Constantes de texto: `CAPTCHA_INVALID_TEXT`, `NOT_FOUND_TEXT_FRAGMENT`, `SERVER_EXCLUDED_TEXT_FRAGMENT`
- [x] Criar `app/bots/econsig/parsers.py` (funções puras, nunca navegam):
  - `parse_success_margens(page) -> EconsigMargens | None` — lê `MSG_SUCCESS` innerHTML, parseia `MARGEM EMPRÉSTIMO`, `MARGEM CARTÃO`, `Data da Carga das Margens` via regex
  - `parse_error_message(page) -> str | None` — retorna texto de `MSG_ERROR` se presente
  - `classify_error(msg: str) -> Literal["not_found", "server_excluded", "other"]` — heurística por substring
- [x] Criar `app/bots/econsig/bot.py`:
  - `@register_bot` + `EconsigBot(BaseBot)` com ClassVars `key="econsig"`, `display_name="Econsig"`, `InputRowModel`, `ResultModel`
  - `__init__`: lê `extras.login_url`, `extras.consulta_url`, `extras.captcha_max_attempts` (default 5), `extras.captcha_allowlist` (default `"abcdefghijklmnopqrstuvwxyz0123456789"`)
  - `authenticate(session)`:
    - Goto `login_url`
    - Se já dentro do app, pula
    - Senão: preenche usuário → clica "Próxima" → aguarda senha aparecer
    - Loop de captcha (até N tentativas):
      - Baixa imagem do captcha via `page.locator(sel.CAPTCHA_IMG).screenshot()` OU `page.request.get(img.src)` (preferir o segundo para nitidez)
      - Chama `tesseract_solve(bytes, allowlist=...)`
      - Preenche senha + captcha → clica Entrar
      - Aguarda navegação ou mensagem de erro
      - Se mensagem == `CAPTCHA_INVALID_TEXT` → recarrega imagem do captcha (refresh src com timestamp) e retenta
      - Se autenticou → break
    - Se esgotar tentativas → `raise AuthenticationError`
  - `process_row(session, row)`:
    - Goto `consulta_url`
    - Preenche `MATRICULA_INPUT` com `row.matricula` → clica "Pesquisar"
    - Detecta `MSG_ERROR`:
      - texto contém "Nenhum registro encontrado" → `raise NotFoundError`
      - texto contém "Servidor não pode fazer novas reservas pois foi excluído" → retorna `EconsigResult(status_consulta="servidor_excluido", observacao=msg, margens=None)`
      - outro → `raise ParseError(msg)`
    - Detecta `MSG_SUCCESS` → chama `parse_success_margens` → retorna `EconsigResult(status_consulta="ok", margens=...)`
    - Sessão expirou (redirect login) → `raise SessionExpired`
  - `output_columns`: `["Matrícula", "Nome", "CPF", "Margem Empréstimo", "Margem Cartão", "Data Carga", "Status Consulta", "Observação", "Data Consulta"]`
  - `center_columns`: `["Matrícula", "CPF", "Margem Empréstimo", "Margem Cartão", "Data Carga"]`
  - `expand_result`: 1 linha por result, mesma estrutura do consiglog + coluna Data Carga

### Library Agent (Wave 3 — Config + Validação)
- [x] Adicionar bloco `sistemas.econsig` em `config.example.json` com chaves: `name`, `auth.email`, `auth.password`, `excel.matricula_column`, `extras.login_url`, `extras.consulta_url`, `extras.captcha_max_attempts: 5`, `extras.captcha_allowlist`
- [x] Definir `bot.captcha.mode = "tesseract"` no exemplo (ou deixar `"manual"` como default — manter `"manual"` para não forçar dep)
- [x] Smoke test de import: `python -c "from app.bots.econsig.bot import EconsigBot; print(EconsigBot.key)"` deve imprimir `econsig`
- [x] Smoke test de registry: `python -c "from app.core.registry import BotRegistry; BotRegistry.discover(); print([c.key for c in BotRegistry.list_all()])"` deve incluir `econsig`
- [x] Verificar que o restante dos bots (valor, bib, consiglog) ainda importam sem erro

## Risks & Concerns
- **Tesseract acerta CAPTCHA distorcido?** Taxa esperada 30-50% mesmo com pré-processamento. Por isso o retry loop (5 tentativas). Se o usuário verificar que está abaixo de aceitável, migrar para 2captcha vira mudança de 1-2 arquivos (já há infra de `mode` em `CaptchaConfig`).
- **Image source via `page.request.get`** pode falhar se a captcha exigir cookie de sessão. Fallback: `page.locator(sel.CAPTCHA_IMG).screenshot()` que sempre funciona pois Playwright já está no contexto.
- **Selector "Pesquisar"** não foi fornecido no HTML pelo usuário — implementação precisa verificar o DOM real ao chegar na página. Risco baixo, mas marcar como ponto de atenção.
- **Tesseract no PATH** — adicionar nota no README sobre `brew install tesseract` (macOS) ou `apt install tesseract-ocr` (Linux).

## Validation
- `python -m compileall app/bots/econsig/` retorna 0
- `python -c "from app.bots.econsig.bot import EconsigBot"` sem erros
- `python -c "from app.services.ocr import tesseract_solve"` sem erros
- Pydantic schema valida com config exemplo

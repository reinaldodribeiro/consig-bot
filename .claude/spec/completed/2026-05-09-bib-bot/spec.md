# Feature: bib-bot
### Status: completed | Phase: CLOSE | Scope: full
### Checkpoint: 2026-05-09T20:00:00Z

## Summary
Implementar BibBot — automação para o sistema BIB Cred (bibcred.com.br).
Consulta contratos de refinanciamento por CPF: faz login, preenche formulário com
seleções em cascata (postbacks ASP.NET), encontra o cliente no popup, aciona
"Atualizar Lista de Contratos" e extrai os dados do grid de operações.

## Entity Info
- Entidade: `BibBot` (nova — não existe no registry)
- Padrão: BaseBot + @register_bot (igual ValorBot)
- Chave de configuração: `sistemas.bib` no config.json

## Boundaries
- `app/bots/bib/` — novo diretório completo
- `config.example.json` — adicionar extras ao bloco bib existente

## Files (~6)
- `app/bots/bib/__init__.py` (create — vazio)
- `app/bots/bib/schema.py` (create)
- `app/bots/bib/selectors.py` (create)
- `app/bots/bib/parsers.py` (create)
- `app/bots/bib/bot.py` (create)
- `config.example.json` (modify — preencher extras do bloco bib)

## Flow do Bot (referência para implementação)

### Autenticação (authenticate)
1. Navegar para `login_url` (extras ou default hardcoded)
2. Verificar se já está logado (`_needs_login`) — se não, preencher e submeter
3. Preencher `#EUsuario_CAMPO` com `system.auth.email` (uppercase automático pelo CSS)
4. Preencher `#ESenha_CAMPO` com `system.auth.password`
5. Clicar `#lnkEntrar` e aguardar `networkidle`
6. Validar login: se ainda na página de login → AuthenticationError

### Por linha (process_row)
1. Navegar para `proposta_url` + aguardar `networkidle`
2. Preencher formulário em cascata (`_fill_form_setup`):
   - select `#cboTipoOperacao_CAMPO` → valor `tipo_operacao` (default "Refinanciamento") + aguardar networkidle
   - select `#cboGrupoConvenio_CAMPO` → valor `grupo_convenio` (default "3" = PREFEITURA) + aguardar networkidle
   - select `#cboOrigem4_CAMPO` → valor `conveniada` (default "000086" = PREF GOIANIA) + aguardar networkidle
   - select `#cboOrigem5_CAMPO` → primeira opção não-vazia (Secretaria) via JS evaluate + aguardar networkidle
3. Formatar CPF: `"XXX.XXX.XXX-XX"` (o campo tem máscara; fill + Tab para triggerar change/postback)
4. Preencher `#txtCPF_CAMPO` + pressionar Tab → aguardar popup iframe aparecer (`#popCliente_frameAjuda`)
5. Dentro do popup frame (`_handle_client_popup`):
   - Aguardar grid `#ctl00_cph_FIJanela1_FIJanelaPanel1_grvHomo` ficar visível
   - Se não há `tr.normal` → cliente não encontrado → retornar NotFoundError
   - Extrair nome do cliente (2ª célula da `tr.normal`)
   - Registrar `page.once("dialog", lambda d: d.accept())` para eventual alert
   - Clicar no `<a>` da 1ª célula da `tr.normal` (código do cliente)
   - Aguardar `networkidle` após postback
6. Aguardar botão `#btAtuListaContratos_txt` ficar visível + clicar
7. Aguardar `networkidle` + verificar grid `#grdOperacoes`
8. Extrair contratos com `parsers.parse_contracts_table(page)` via JS evaluate
9. Retornar BibResult (contratos encontrados ou observacao="Contrato não encontrado")

## Tasks

### Implementation Agent (Wave 1)

- [x] Criar `app/bots/bib/__init__.py` vazio
- [x] Criar `app/bots/bib/schema.py`: `BibInputRow` (cpf+nome, normalize_cpf), `BibContract` (contrato, matricula, taxa_am, qtd_parc_total, qtd_parc_vencidas, qtd_parc_em_aberto, vlr_parcela, saldo_total), `BibResult` (row_index, cpf, nome, contracts, status_consulta, observacao, data_consulta)
- [x] Criar `app/bots/bib/selectors.py`: todos os seletores mapeados conforme seção "Selectors" abaixo
- [x] Criar `app/bots/bib/parsers.py`: `parse_contracts_table(page)` via JS+`tr.normal`+`[id$=]`, `parse_client_name(frame)` via JS, `parse_first_secretaria(page)` via JS evaluate
- [x] Criar `app/bots/bib/bot.py`: `BibBot` com `key="bib"`, `authenticate`, `_needs_login`, `_fill_form_setup`, `_handle_client_popup`, `process_row`, `output_columns`, `expand_result`, `_error_result`
- [x] Atualizar `config.example.json`: adicionar URLs e opções no bloco `sistemas.bib.extras`
- [x] Verificar que `poetry run python -m app` importa o módulo sem erros de sintaxe

## Selectors (para selectors.py)

```
# Login
LOGIN_USER  = "#EUsuario_CAMPO"
LOGIN_PASS  = "#ESenha_CAMPO"
LOGIN_BTN   = "#lnkEntrar"

# Form setup (IDs completos — ASP.NET WebForms)
TIPO_OPERACAO = "#ctl00_Cph_UcPrp_FIJN1_JnDadosIniciais_UcDIni_cboTipoOperacao_CAMPO"
GRUPO_CONVENIO = "#ctl00_Cph_UcPrp_FIJN1_JnDadosIniciais_UcDIni_cboGrupoConvenio_CAMPO"
CONVENIADA     = "#ctl00_Cph_UcPrp_FIJN1_JnDadosIniciais_UcDIni_cboOrigem4_CAMPO"
SECRETARIA     = "#ctl00_Cph_UcPrp_FIJN1_JnDadosIniciais_UcDIni_cboOrigem5_CAMPO"
CPF_INPUT      = "#ctl00_Cph_UcPrp_FIJN1_JnDadosIniciais_UcDIni_txtCPF_CAMPO"

# Popup iframe de cliente
POPUP_FRAME_ID  = "ctl00_Cph_UcPrp_FIJN1_JnDadosIniciais_UcDIni_popCliente_frameAjuda"
POPUP_FRAME_SEL = "#ctl00_Cph_UcPrp_FIJN1_JnDadosIniciais_UcDIni_popCliente_frameAjuda"
CLIENT_GRID     = "#ctl00_cph_FIJanela1_FIJanelaPanel1_grvHomo"
CLIENT_ROW      = "#ctl00_cph_FIJanela1_FIJanelaPanel1_grvHomo tr.normal"
CLIENT_LINK     = "#ctl00_cph_FIJanela1_FIJanelaPanel1_grvHomo tr.normal td:first-child a"

# Ações pós-popup
BTN_ATUALIZAR = "#btAtuListaContratos_txt"

# Grid de contratos
CONTRACTS_GRID = "#ctl00_Cph_UcPrp_FIJN1_JnRefinReneg_UcRefin_FIJN1_JnCR_grdOperacoes"
CONTRACTS_ROWS = "#ctl00_Cph_UcPrp_FIJN1_JnRefinReneg_UcRefin_FIJN1_JnCR_grdOperacoes tr.normal"
```

## Schema de saída (output_columns / expand_result)

Colunas: `CPF, Nome, Contrato, Matrícula, Taxa a.m., Qtd.Parc. Total, Qtd.Parc. Vencidas, Qtd.Parc. Em Aberto, Vlr.Parc., Saldo Total, Status Consulta, Observação, Data Consulta`

Status possíveis: `"ok"`, `"nao_encontrado"`, `"erro"`, `"auth_error"`

Observação quando não encontrado: `"Contrato não encontrado"`

## Extras config.example.json (bloco bib)

```json
"extras": {
  "login_url": "https://www.bibcred.com.br/Funcao.WebAutorizador/Login/AC.UI.LOGIN.aspx",
  "proposta_url": "https://www.bibcred.com.br/Funcao.WebAutorizador/MenuWeb/Cadastro/Proposta/UI.PropostaSintetizada.aspx?Origem3=007374",
  "tipo_operacao": "Refinanciamento",
  "grupo_convenio": "3",
  "conveniada": "000086",
  "secretaria": null
}
```

## Dependencies
- `app/utils/cpf.py` — `normalize_cpf`, `mask_cpf` (já existem)
- `app/utils/dates.py` — `now_str` (já existe)
- `app/core/base_bot.py` — `BaseBot` (já existe)
- `app/core/registry.py` — `@register_bot` (já existe)
- `app/core/browser.py` — `BrowserSession` (já existe)
- `app/core/exceptions.py` — `AuthenticationError`, `NotFoundError`, `ParseError` (já existem)

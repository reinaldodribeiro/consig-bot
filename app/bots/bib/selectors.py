"""Selectors for BIB Cred — ASP.NET WebForms site."""
from __future__ import annotations

# === Login (AC.UI.LOGIN.aspx) ===
LOGIN_USER = "#EUsuario_CAMPO"
LOGIN_PASS = "#ESenha_CAMPO"
LOGIN_BTN  = "#lnkEntrar"

# === Form setup — 4 selects em cascata (cada um dispara __doPostBack) ===
TIPO_OPERACAO  = "#ctl00_Cph_UcPrp_FIJN1_JnDadosIniciais_UcDIni_cboTipoOperacao_CAMPO"
GRUPO_CONVENIO = "#ctl00_Cph_UcPrp_FIJN1_JnDadosIniciais_UcDIni_cboGrupoConvenio_CAMPO"
CONVENIADA     = "#ctl00_Cph_UcPrp_FIJN1_JnDadosIniciais_UcDIni_cboOrigem4_CAMPO"
SECRETARIA     = "#ctl00_Cph_UcPrp_FIJN1_JnDadosIniciais_UcDIni_cboOrigem5_CAMPO"
CPF_INPUT      = "#ctl00_Cph_UcPrp_FIJN1_JnDadosIniciais_UcDIni_txtCPF_CAMPO"

# === Popup iframe de pesquisa de cliente (aparece após preencher CPF) ===
POPUP_FRAME_ID  = "ctl00_Cph_UcPrp_FIJN1_JnDadosIniciais_UcDIni_popCliente_frameAjuda"
POPUP_FRAME_SEL = "#ctl00_Cph_UcPrp_FIJN1_JnDadosIniciais_UcDIni_popCliente_frameAjuda"
CLIENT_GRID     = "#ctl00_cph_FIJanela1_FIJanelaPanel1_grvHomo"
CLIENT_ROW      = "#ctl00_cph_FIJanela1_FIJanelaPanel1_grvHomo tr.normal"
CLIENT_LINK     = "#ctl00_cph_FIJanela1_FIJanelaPanel1_grvHomo tr.normal td:first-child a"

# === Pós-seleção de cliente ===
BTN_ATUALIZAR = "#btAtuListaContratos_txt"

# === Grid de contratos de refinanciamento ===
CONTRACTS_GRID = "#ctl00_Cph_UcPrp_FIJN1_JnRefinReneg_UcRefin_FIJN1_JnCR_grdOperacoes"
CONTRACTS_ROWS = "#ctl00_Cph_UcPrp_FIJN1_JnRefinReneg_UcRefin_FIJN1_JnCR_grdOperacoes tr:not(.header)"

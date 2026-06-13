"""Selectors for Valor Financiamentos. Tune during smoke testing — kept centralized here."""
from __future__ import annotations

# === Login page (index.php) ===
LOGIN_INPUT = "input#login"
SENHA_INPUT = "input#senha"
BTLOGIN = "button.btlogin"

# === Captcha detection (login + interstitials) ===
RECAPTCHA_IFRAME = (
    "iframe[src*='recaptcha'], iframe[title*='reCAPTCHA'], "
    "iframe[src*='captcha'], [class*='captcha'], [id*='captcha']"
)

# === Dashboard sentinel (post-login) ===
DASHBOARD_READY = "body"  # tune: a sidebar or username badge is more reliable

# === Sidebar menu — Consulta Saldo ===
# Multiple fallbacks: by visible text, by role, by attribute hints
MENU_CONSULTA_SALDO = (
    "xpath=//a[normalize-space()='Consulta Saldo'] | "
    "//a[contains(., 'Consulta Saldo')] | "
    "//*[@id='menuConsultaSaldo']"
)

# === Consulta saldo form ===
# CSSENHA_INPUT recebe o CPF (apesar do nome do id, é o campo de consulta).
CSSENHA_INPUT = "input#cssenha"
BTCONSULTASALDO = "button#btconsultasaldo"

# === iframe que carrega o resultado da consulta ===
IFRAME_RESULT = "iframe#rbmcont"
IFRAME_RESULT_NAME = "rbmcont"

# === Result region (dentro do iframe) — tabela OU toast de erro ===
CONTRACTS_TABLE = (
    "table#JTPlatinumGrid2_IntTable, "
    "table.inttable, "
    "table:has(th:has-text('Contrato'))"
)
CONTRACTS_TABLE_OR_TOAST = (
    "table#JTPlatinumGrid2_IntTable, "
    "table.inttable, "
    "table:has(th:has-text('Contrato')), "
    ".toast, .alert, .swal2-popup, .modal-message"
)
CONTRACTS_TABLE_ROWS = f"{CONTRACTS_TABLE} tbody tr"

# === Error toasts / messages ===
ERROR_TOAST = ".toast, .alert, .swal2-popup, .swal-text, .modal-message"
NO_INFO_MESSAGE_TEXT = "Não existe informações"

# === Parcelas inline (tabela na própria tela de resultado, dentro do iframe rbmcont) ===
# Estrutura: #dbrp_parcelas_table_detail > tr[id^="cronograma_"] > td > div.linha > div
# div[0]=Contrato, div[1]=NDoc, div[2]=Vencimento
DBRP_PARCELAS_TABLE = "#dbrp_parcelas_table_detail"
DBRP_PARCELAS_ROWS = '#dbrp_parcelas_table_detail tr[id^="cronograma_"]'

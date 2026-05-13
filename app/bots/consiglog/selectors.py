"""Selectors for ConsigLog (saec.consiglog.com.br) — ASP.NET WebForms."""
from __future__ import annotations

# === Login.aspx (2 passos) ===
LOGIN_USER = "#txtLogin"
LOGIN_NEXT = "input[type='submit'][value='Próxima']"   # passo 1: "Próxima"
LOGIN_PASS = "#txtSenha"
LOGIN_SUBMIT = "input[type='submit'][value='Entrar']"  # passo 2: "Entrar"

# === LoginSelecao.aspx (tabela de convênios) ===
CONVENIO_TABLE = "#gvOrgao"
CONVENIO_ROWS = "#gvOrgao tbody tr"


def convenio_button_xpath(label: str) -> str:
    """Retorna XPath para o botão 'Entrar' (input image) da linha com o label."""
    # normalize-space para tolerar espaços extras
    return (
        f"xpath=//table[@id='gvOrgao']//tr"
        f"[td[normalize-space()='{label}']]"
        f"//input[@type='image']"
    )


# === ConsultaMargem.aspx ===
MATRICULA_INPUT = "#body_matriculaTextBox"
PESQUISAR_BTN = "#body_pesquisarButton"
NOME_INPUT = "#body_clienteTextBox"
CPF_INPUT = "#body_cpf_nascimentoTextBox"

# === Tabela de margens ===
MARGENS_TABLE = "table.grid.grid-detalhe"
MARGEM_HEADER_ROWS = "tr[id^='body_rptMargens_headerservico_']"

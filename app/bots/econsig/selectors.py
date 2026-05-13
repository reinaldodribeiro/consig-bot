"""DOM selectors for the Econsig bot — all UPPER_SNAKE_CASE constants, no logic."""
from __future__ import annotations

LOGIN_USER = "input#username[name='username']"
LOGIN_NEXT_BTN = "button.btn.btn-primary[type='submit']"
LOGIN_PASS = "input[name='senha']"
CAPTCHA_IMG = "img[name='captcha_img']"
CAPTCHA_INPUT = "input#captcha[name='captcha']"
CAPTCHA_REFRESH_BTN = (
    "img[onclick*='captcha' i], img[src*='refresh' i], img[src*='reload' i], "
    "a[onclick*='captcha' i], [title*='Atualizar' i], [alt*='Atualizar' i], "
    "img[name='captcha_img'] + a, img[name='captcha_img'] + img"
)
LOGIN_SUBMIT_BTN = "button#btnOK"
MATRICULA_INPUT = "input#RSE_MATRICULA[name='RSE_MATRICULA']"
# Menu navigation (site rejects direct GET — must go through postData via menu clicks)
MENU_OPERACIONAL_TOGGLE = "a[href='#menuOperacional']"
MENU_CONSULTAR_MARGEM = "a.link-menu[onclick*='consultarMargem']"
PESQUISAR_BTN = "a#btnEnvia, [name='btnEnvia']"
MSG_SUCCESS = "span#idMsgSuccessSession"
MSG_ERROR = "span#idMsgErrorSession"

# Text fragment constants for error classification
CAPTCHA_INVALID_TEXT = "O código informado é inválido"
NOT_FOUND_TEXT_FRAGMENT = "Nenhum registro encontrado"
SERVER_EXCLUDED_TEXT_FRAGMENT = "Servidor não pode fazer novas reservas pois foi excluído"

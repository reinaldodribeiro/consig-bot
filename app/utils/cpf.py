"""CPF helpers: normalize, mask, validate (checksum)."""
from __future__ import annotations

import re

_DIGITS_ONLY = re.compile(r"\D+")


def normalize_cpf(value: str | None) -> str:
    if not value:
        return ""
    return _DIGITS_ONLY.sub("", str(value)).zfill(11)[:11]


def mask_cpf(cpf: str) -> str:
    digits = normalize_cpf(cpf)
    if len(digits) != 11:
        return "***"
    return f"{digits[:3]}.***.***-{digits[-2:]}"


def is_valid_cpf(cpf: str) -> bool:
    digits = normalize_cpf(cpf)
    if len(digits) != 11 or len(set(digits)) == 1:
        return False
    for i in (9, 10):
        s = sum(int(digits[j]) * ((i + 1) - j) for j in range(i))
        check = (s * 10) % 11
        if check == 10:
            check = 0
        if check != int(digits[i]):
            return False
    return True

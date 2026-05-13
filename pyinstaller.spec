# pyinstaller.spec — template para empacotamento futuro do Consig Bot.
# Build (Windows): pyinstaller pyinstaller.spec --clean --noconfirm
# Saida: dist/consig-bot.exe
#
# IMPORTANTE: este template ainda nao foi validado em build real.
# Antes de usar, instale: pip install pyinstaller
# E rode: poetry run playwright install chromium  (o navegador deve estar instalado)
#
# Notas de empacotamento:
#  - `--collect-all playwright` puxa os browsers + drivers internos.
#  - `hiddenimports` inclui submodulos de bots descobertos dinamicamente
#    (importlib.import_module em runtime — PyInstaller nao detecta sozinho).
#  - `entrada/`, `saida/`, `logs/`, `checkpoint/`, `config.json` ficam EXTERNOS
#    ao .exe (lidos via app.utils.paths.get_app_root -> parent of sys.executable).

# -*- mode: python ; coding: utf-8 -*-
import os
from pathlib import Path
from PyInstaller.utils.hooks import collect_all

block_cipher = None
project_root = Path(SPECPATH).resolve() if "SPECPATH" in dir() else Path(".").resolve()

# Discover bot modules dynamically so registry-based bots are bundled
hidden_bots = []
bots_dir = project_root / "app" / "bots"
if bots_dir.exists():
    for child in bots_dir.iterdir():
        if child.is_dir() and (child / "bot.py").exists():
            hidden_bots.append(f"app.bots.{child.name}.bot")

playwright_datas, playwright_binaries, playwright_hidden = collect_all("playwright")
term_datas, term_binaries, term_hidden = collect_all("term_image")
pil_datas, pil_binaries, pil_hidden = collect_all("PIL")

a = Analysis(
    ["main.py"],
    pathex=[str(project_root)],
    binaries=playwright_binaries + term_binaries + pil_binaries,
    datas=playwright_datas + term_datas + pil_datas,
    hiddenimports=[
        "loguru",
        "rich",
        "pydantic",
        "pandas",
        "openpyxl",
        "dotenv",
        *playwright_hidden,
        *term_hidden,
        *pil_hidden,
        *hidden_bots,
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "matplotlib", "scipy", "tkinter", "test", "unittest",
    ],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="consig-bot",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)

# Para distribuicao final, copiar manualmente para o lado do .exe:
#   - config.example.json
#   - executar.bat (ajustado para .\\consig-bot.exe)
#   - pastas vazias: entrada/, saida/, logs/, checkpoint/

# -*- mode: python ; coding: utf-8 -*-
"""
================================================================================
  PYINSTALLER WINDOWS SPECIFICATION - SURA CITAS BOT
  GENERA: dist/SuraCitas.exe (Windows Standalone Executable)
  ENGINEERED BY: SHION
================================================================================
"""

import os
from PyInstaller.utils.hooks import collect_all

datas = []
binaries = []
hiddenimports = [
    'security_shield',
    'audio_alerter',
    'config_manager',
    'sura_engine',
    'app_gui',
    'playwright.async_api',
    'asyncio',
    'tkinter',
    'tkinter.ttk',
    'tkinter.messagebox',
    'tkinter.scrolledtext',
    'winsound'
]

# Recolección integral de metadatos, binarios y librerías de Playwright
tmp_ret = collect_all('playwright')
datas += tmp_ret[0]
binaries += tmp_ret[1]
hiddenimports += tmp_ret[2]

# Resolución robusta de la raíz del proyecto
current_dir = os.path.dirname(os.path.abspath(SPEC))
repo_root = os.path.abspath(os.path.join(current_dir, '..', '..'))
main_script = os.path.join(repo_root, 'main.py')
if not os.path.exists(main_script):
    main_script = 'main.py'

a = Analysis(
    [main_script],
    pathex=[repo_root, '.'],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='SuraCitas',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

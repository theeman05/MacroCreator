# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_submodules

hidden_ui_tabs = collect_submodules('macro_studio.ui.tabs')
hidden_ui_widgets = collect_submodules('macro_studio.ui.widgets')

all_hidden_imports = hidden_ui_tabs + hidden_ui_widgets

a = Analysis(
    ['macro_studio\\main.py'],
    pathex=[],
    binaries=[],
    datas=[('macro_studio/assets', 'assets'), ('macro_studio/ui/templates', 'ui/templates')],
    hiddenimports=hidden_ui_tabs,
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
    [],
    exclude_binaries=True,
    name='MacroStudio',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['macro_studio\\assets\\app_icon.ico'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='MacroStudio',
)

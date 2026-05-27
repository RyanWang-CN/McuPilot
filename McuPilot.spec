# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all, collect_submodules

datas = [('assets', 'assets'), ('core', 'core'), ('skills', 'skills'), ('HIL', 'HIL'), ('RTT', 'RTT'), ('requirements.txt', '.'), ('mcupilot_iconsp.svg', '.'), ('mcupilot_icon.svg', '.')]
binaries = []
hiddenimports = ['webview', 'PIL', 'tkinter', 'clr']
tmp_ret = collect_all('tkinter')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]

# 强制收集 webview 全部子模块（platforms/dom 等由 guilib 动态加载，静态分析不可见）
hiddenimports += collect_submodules('webview')


a = Analysis(
    ['run_setup.py'],
    pathex=[],
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
    [],
    exclude_binaries=True,
    name='McuPilot',
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
    icon=['assets\\mcupilot.ico'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='McuPilot',
)
